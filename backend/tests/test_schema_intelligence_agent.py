import pytest
import json
from unittest.mock import patch, MagicMock

from app.services.agents.nodes.sql import (
    _execute_schema_tool,
    schema_intelligence_node,
)


@pytest.fixture
def mock_authorized_schema():
    return {
        "tables": [
            {
                "name": "customers",
                "columns": [
                    {"name": "customer_id", "type": "INTEGER"},
                    {"name": "name", "type": "VARCHAR"},
                    {"name": "city", "type": "VARCHAR"},
                ],
            },
            {
                "name": "orders",
                "columns": [
                    {"name": "order_id", "type": "INTEGER"},
                    {"name": "customer_id", "type": "INTEGER"},
                    {"name": "total", "type": "NUMERIC"},
                ],
            },
            {
                "name": "payments",
                "columns": [
                    {"name": "payment_id", "type": "INTEGER"},
                    {"name": "amount", "type": "NUMERIC"},
                ],
            },
            {
                "name": "inventory",
                "columns": [
                    {"name": "item_id", "type": "INTEGER"},
                    {"name": "stock", "type": "INTEGER"},
                ],
            },
        ]
    }


def test_execute_schema_tools_directly(mock_authorized_schema):
    tables = mock_authorized_schema["tables"]

    # 1. get_all_table_names
    names_json = _execute_schema_tool("get_all_table_names", {}, tables)
    assert json.loads(names_json) == ["customers", "orders", "payments", "inventory"]

    # 2. get_table_schema
    schema_json = _execute_schema_tool(
        "get_table_schema", {"table_names": ["customers", "orders"]}, tables
    )
    data = json.loads(schema_json)
    assert len(data["tables"]) == 2
    assert {t["name"] for t in data["tables"]} == {"customers", "orders"}

    # 3. get_all_tables_schema
    all_json = _execute_schema_tool("get_all_tables_schema", {}, tables)
    all_data = json.loads(all_json)
    assert len(all_data["tables"]) == 4


@pytest.mark.asyncio
async def test_schema_intelligence_node_react_loop(mock_authorized_schema):
    state = {
        "query": "Show me customers who spent more than ₹10,000.",
        "db_authorized_schema": mock_authorized_schema,
        "db_session_turns": [],
        "context_error": None,
    }

    # Simulate ReAct loop turns via Anthropic mock responses
    # Turn 1: model calls get_all_table_names
    resp_turn1 = MagicMock()
    block_tool1 = MagicMock()
    block_tool1.type = "tool_use"
    block_tool1.name = "get_all_table_names"
    block_tool1.input = {}
    block_tool1.id = "tool_call_1"
    thought1 = MagicMock()
    thought1.text = "I don't know which tables exist. Calling get_all_table_names."
    resp_turn1.content = [thought1, block_tool1]
    resp_turn1.stop_reason = "tool_use"

    # Turn 2: model calls get_table_schema(["customers", "orders"])
    resp_turn2 = MagicMock()
    block_tool2 = MagicMock()
    block_tool2.type = "tool_use"
    block_tool2.name = "get_table_schema"
    block_tool2.input = {"table_names": ["customers", "orders"]}
    block_tool2.id = "tool_call_2"
    thought2 = MagicMock()
    thought2.text = "I probably need customers and orders."
    resp_turn2.content = [thought2, block_tool2]
    resp_turn2.stop_reason = "tool_use"

    # Turn 3: model finishes turn with direct JSON text response (no tool call)
    resp_turn3 = MagicMock()
    final_text = MagicMock()
    final_text.text = json.dumps(
        {
            "selected_tables": ["customers", "orders"],
            "reasoning": "Selected customers and orders to find high spending customers.",
        }
    )
    resp_turn3.content = [final_text]
    resp_turn3.stop_reason = "end_turn"

    responses = [resp_turn1, resp_turn2, resp_turn3]

    mock_client = MagicMock()

    async def mock_create(*args, **kwargs):
        return responses.pop(0)

    mock_client.messages.create = mock_create

    with patch(
        "app.services.rag_service._get_async_anthropic_client", return_value=mock_client
    ):
        result = await schema_intelligence_node(state)

    filtered_tables = result["db_filtered_schema"]["tables"]
    table_names = [t["name"] for t in filtered_tables]

    assert len(filtered_tables) == 2
    assert set(table_names) == {"customers", "orders"}
    assert "payments" not in table_names
    assert "inventory" not in table_names
    assert "progress_tokens" in result
    assert "Schema Intelligence Agent" in result["progress_tokens"][0]


@pytest.mark.asyncio
async def test_schema_intelligence_node_reformat_json(mock_authorized_schema):
    state = {
        "query": "Show me customers who spent more than ₹10,000.",
        "db_authorized_schema": mock_authorized_schema,
        "db_session_turns": [],
        "context_error": None,
    }

    # Turn 1: model returns unparseable text
    resp_turn1 = MagicMock()
    text1 = MagicMock()
    text1.text = "I think you need customers and orders tables."
    resp_turn1.content = [text1]
    resp_turn1.stop_reason = "end_turn"

    # Turn 2 (reformat prompt): model responds with valid JSON
    resp_turn2 = MagicMock()
    text2 = MagicMock()
    text2.text = json.dumps(
        {"selected_tables": ["customers", "orders"], "reasoning": "Reformatted output."}
    )
    resp_turn2.content = [text2]
    resp_turn2.stop_reason = "end_turn"

    responses = [resp_turn1, resp_turn2]
    mock_client = MagicMock()

    async def mock_create(*args, **kwargs):
        return responses.pop(0)

    mock_client.messages.create = mock_create

    with patch(
        "app.services.rag_service._get_async_anthropic_client", return_value=mock_client
    ):
        result = await schema_intelligence_node(state)

    filtered_tables = result["db_filtered_schema"]["tables"]
    assert len(filtered_tables) == 2
    assert {t["name"] for t in filtered_tables} == {"customers", "orders"}

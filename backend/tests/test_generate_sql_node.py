import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.agents.nodes.sql import generate_sql


@pytest.mark.asyncio
async def test_generate_sql_fresh():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text="```sql\nSELECT * FROM users LIMIT 10;\n```")
    ]
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch(
        "app.services.rag_service._get_async_anthropic_client", return_value=mock_client
    ):
        sql = await generate_sql(
            query="show users",
            schema={"tables": ["users"]},
            engine_type="postgresql",
            conversation_history=None,
        )

        assert sql == "SELECT * FROM users LIMIT 10;"
        mock_client.messages.create.assert_called_once()
        kwargs = mock_client.messages.create.call_args.kwargs
        assert "ILIKE" in kwargs["system"]
        assert "postgresql" in kwargs["system"]


@pytest.mark.asyncio
async def test_generate_sql_access_denied_retry():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="SELECT id, name FROM users LIMIT 10;")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch(
        "app.services.rag_service._get_async_anthropic_client", return_value=mock_client
    ):
        sql = await generate_sql(
            query="show users",
            schema={"tables": ["users"]},
            engine_type="mysql",
            conversation_history=[{"question": "hi", "answer": "hello"}],
            failed_sql="SELECT secret_key FROM users;",
            error_message="Access denied for column secret_key",
        )

        assert sql == "SELECT id, name FROM users LIMIT 10;"
        kwargs = mock_client.messages.create.call_args.kwargs
        assert "access denied" in kwargs["messages"][0]["content"].lower()
        assert "LIKE or LOWER()" in kwargs["system"]


@pytest.mark.asyncio
async def test_generate_sql_invalid_sql_raises():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="DELETE FROM users;")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch(
        "app.services.rag_service._get_async_anthropic_client", return_value=mock_client
    ):
        with pytest.raises(ValueError):
            await generate_sql(
                query="delete users",
                schema={"tables": ["users"]},
                engine_type="postgresql",
                conversation_history=None,
            )


@pytest.mark.asyncio
async def test_sql_generation_node():
    from app.services.agents.nodes.sql import sql_generation_node

    state = {
        "query": "select top 10 users",
        "db_filtered_schema": {"tables": ["users"]},
        "sql_generation_attempts": 0,
        "db_connection_engine": "postgresql",
        "db_authorized_cols_by_table": {"users": ["id", "name"]},
        "db_valid_tables": {"users"},
        "db_all_physical_cols_by_table": {"users": ["id", "name"]},
        "db_is_admin": True,
    }

    mock_client = MagicMock()

    block1 = MagicMock()
    block1.type = "tool_use"
    block1.id = "call_1"
    block1.name = "generate_sql"
    block1.input = {}
    resp1 = MagicMock(stop_reason="tool_use", content=[block1])

    block2 = MagicMock()
    block2.type = "tool_use"
    block2.id = "call_2"
    block2.name = "validate_sql"
    block2.input = {"sql": "SELECT id, name FROM users LIMIT 10;"}
    resp2 = MagicMock(stop_reason="tool_use", content=[block2])

    block3 = MagicMock()
    block3.type = "text"
    block3.text = '{"final_sql": "SELECT id, name FROM users LIMIT 10;"}'
    resp3 = MagicMock(stop_reason="end_turn", content=[block3])

    gen_sql_resp = MagicMock()
    gen_sql_resp.content = [MagicMock(text="SELECT id, name FROM users LIMIT 10;")]

    mock_client.messages.create = AsyncMock(
        side_effect=[resp1, gen_sql_resp, resp2, resp3]
    )

    with patch(
        "app.services.rag_service._get_async_anthropic_client", return_value=mock_client
    ):
        res = await sql_generation_node(state)
        assert res["generated_sql"] == "SELECT id, name FROM users LIMIT 10;"
        assert res["sql_generation_attempts"] == 1
        assert res["sql_generation_error"] is None

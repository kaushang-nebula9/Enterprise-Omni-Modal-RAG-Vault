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
    import uuid
    from app.services.agents.nodes.sql import sql_generation_node

    dummy_conn_id = str(uuid.uuid4())
    state = {
        "query": "select top 10 users",
        "db_filtered_schema": {"tables": ["users"]},
        "sql_generation_attempts": 0,
        "db_connection_engine": "postgresql",
        "db_authorized_cols_by_table": {"users": ["id", "name"]},
        "db_valid_tables": {"users"},
        "db_all_physical_cols_by_table": {"users": ["id", "name"]},
        "db_is_admin": True,
        "db_connection_id": dummy_conn_id,
        "db_connection_name": "test_db",
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
    block3.type = "tool_use"
    block3.id = "call_3"
    block3.name = "execute_sql"
    block3.input = {"sql": "SELECT id, name FROM users LIMIT 10;"}
    resp3 = MagicMock(stop_reason="tool_use", content=[block3])

    block4 = MagicMock()
    block4.type = "text"
    block4.text = '{"final_sql": "SELECT id, name FROM users LIMIT 10;", "results": [{"id": 1, "name": "Alice"}], "execution_time_ms": 15}'
    resp4 = MagicMock(stop_reason="end_turn", content=[block4])

    gen_sql_resp = MagicMock()
    gen_sql_resp.content = [MagicMock(text="SELECT id, name FROM users LIMIT 10;")]

    mock_client.messages.create = AsyncMock(
        side_effect=[resp1, gen_sql_resp, resp2, resp3, resp4]
    )

    with (
        patch(
            "app.services.rag_service._get_async_anthropic_client",
            return_value=mock_client,
        ),
        patch("app.services.agents.nodes.sql.get_db_session") as mock_db,
        patch(
            "app.services.database_service.run_query_on_connection",
            return_value=[{"id": 1, "name": "Alice"}],
        ),
    ):
        mock_session = MagicMock()
        mock_db.return_value = mock_session

        res = await sql_generation_node(state)
        assert res["generated_sql"] == "SELECT id, name FROM users LIMIT 10;"
        assert res["sql_generation_attempts"] == 1
        assert res["sql_generation_error"] is None
        assert res["sql_result"].success is True
        assert res["sql_result"].query_results == [{"id": 1, "name": "Alice"}]

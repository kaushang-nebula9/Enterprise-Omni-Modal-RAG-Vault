import pytest

from unittest.mock import patch, MagicMock
from app.services.database_service import (
    resolve_categorical_literals,
    translate_nl_to_sql,
)


def test_resolve_categorical_literals_basic():
    # Schema tables with allowed_values for roles table
    schema_tables = [
        {
            "name": "roles",
            "columns": [
                {"name": "id", "type": "UUID"},
                {
                    "name": "name",
                    "type": "VARCHAR",
                    "allowed_values": ["Tech Lead", "Manager", "Intern"],
                },
                {
                    "name": "department",
                    "type": "VARCHAR",
                    "allowed_values": ["Engineering", "HR"],
                },
            ],
        }
    ]

    # Test case 1: simple rewrite of name 'tech lead' -> 'Tech Lead'
    sql_1 = "SELECT * FROM roles WHERE name ILIKE 'tech lead' AND department = 'hr';"
    rewritten_1 = resolve_categorical_literals(sql_1, schema_tables)
    assert (
        rewritten_1
        == "SELECT * FROM roles WHERE name ILIKE 'Tech Lead' AND department = 'HR';"
    )

    # Test case 2: query with table alias 'r.name' -> 'Tech Lead'
    sql_2 = "SELECT r.id FROM roles r WHERE r.name = 'manager' OR r.department ILIKE 'engineering';"
    rewritten_2 = resolve_categorical_literals(sql_2, schema_tables)
    assert (
        rewritten_2
        == "SELECT r.id FROM roles r WHERE r.name = 'Manager' OR r.department ILIKE 'Engineering';"
    )

    # Test case 3: query with no case-insensitive match (value doesn't exist in allowed_values)
    sql_3 = "SELECT * FROM roles WHERE name = 'unrelated' AND department = 'unknown';"
    rewritten_3 = resolve_categorical_literals(sql_3, schema_tables)
    assert rewritten_3 == sql_3  # Remains unchanged as-is

    # Test case 4: UUID literal should not match since ID has no allowed values
    sql_4 = "SELECT * FROM roles WHERE id = '85c024d0-7db4-48a1-8d0f-c0c457e9ca1d' AND name = 'intern';"
    rewritten_4 = resolve_categorical_literals(sql_4, schema_tables)
    assert (
        rewritten_4
        == "SELECT * FROM roles WHERE id = '85c024d0-7db4-48a1-8d0f-c0c457e9ca1d' AND name = 'Intern';"
    )


@pytest.mark.asyncio
@patch("app.services.database_service._async_anthropic_client")
async def test_prompt_generation_postgresql(mock_anthropic_class):
    mock_resp = MagicMock()
    mock_resp.content = [
        MagicMock(text="SELECT * FROM roles WHERE name ILIKE 'Tech Lead'")
    ]

    # We use mock for both stream and non-stream just in case
    from unittest.mock import AsyncMock

    mock_anthropic_class.messages.create = AsyncMock(return_value=mock_resp)

    schema_data_filtered = {
        "tables": [
            {
                "name": "roles",
                "columns": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR"},
                ],
                "primary_key": [],
                "foreign_keys": [],
            }
        ]
    }

    # Call translation with postgresql
    with patch("app.services.database_service.stream_openrouter_completion") as mock_or:
        # If openrouter is used instead of anthropic (depending on default settings/API keys)
        async def mock_generator(*args, **kwargs):
            yield "text", "SELECT * FROM roles WHERE name ILIKE 'Tech Lead'"
            return

        mock_or.side_effect = mock_generator

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        await translate_nl_to_sql(
            query="How many roles report to tech lead?",
            schema_data_filtered=schema_data_filtered,
            engine_type="postgresql",
            db=mock_db,
            conversation_history=[],
        )

        # Check prompt rules inside system prompt
        # We verify that we pass the appropriate PostgreSQL ILIKE rule
        args, kwargs = (
            mock_anthropic_class.messages.create.call_args
            if mock_anthropic_class.messages.create.called
            else ([], {})
        )
        if not args and not kwargs:
            # Fallback to verify openrouter call args if that was called
            args, kwargs = mock_or.call_args if mock_or.called else ([], {})
            system_prompt = kwargs.get("system_prompt", "")
        else:
            system_prompt = kwargs.get("system", "")

        assert "ILIKE" in system_prompt
        assert "case-insensitive" in system_prompt


@pytest.mark.asyncio
@patch("app.services.database_service._async_anthropic_client")
async def test_prompt_generation_mysql(mock_anthropic_class):
    mock_resp = MagicMock()
    mock_resp.content = [
        MagicMock(text="SELECT * FROM roles WHERE name LIKE 'Tech Lead'")
    ]
    from unittest.mock import AsyncMock

    mock_anthropic_class.messages.create = AsyncMock(return_value=mock_resp)

    schema_data_filtered = {
        "tables": [
            {
                "name": "roles",
                "columns": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR"},
                ],
                "primary_key": [],
                "foreign_keys": [],
            }
        ]
    }

    # Call translation with mysql
    with patch("app.services.database_service.stream_openrouter_completion") as mock_or:

        async def mock_generator(*args, **kwargs):
            yield "text", "SELECT * FROM roles WHERE name LIKE 'Tech Lead'"
            return

        mock_or.side_effect = mock_generator

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        await translate_nl_to_sql(
            query="How many roles report to tech lead?",
            schema_data_filtered=schema_data_filtered,
            engine_type="mysql",
            db=mock_db,
            conversation_history=[],
        )

        args, kwargs = (
            mock_anthropic_class.messages.create.call_args
            if mock_anthropic_class.messages.create.called
            else ([], {})
        )
        if not args and not kwargs:
            args, kwargs = mock_or.call_args if mock_or.called else ([], {})
            system_prompt = kwargs.get("system_prompt", "")
        else:
            system_prompt = kwargs.get("system", "")

        assert "LIKE" in system_prompt or "LOWER" in system_prompt
        assert "case-insensitive" in system_prompt

import pytest
from app.core.utils import call_llm_with_fallback


@pytest.mark.asyncio
async def test_fallback_success_primary():
    primary_config = {
        "id": "model-1",
        "model_name": "primary",
        "display_name": "Primary Model",
    }
    fallback_config = {
        "id": "model-2",
        "model_name": "fallback",
        "display_name": "Fallback Model",
    }

    async def success_fn(cfg):
        return f"Response from {cfg['model_name']}"

    res, was_fallback, fallback_name = await call_llm_with_fallback(
        primary_model_config=primary_config,
        default_model_config=fallback_config,
        call_fn=success_fn,
    )

    assert res == "Response from primary"
    assert was_fallback is False
    assert fallback_name is None


@pytest.mark.asyncio
async def test_fallback_same_model_no_retry():
    primary_config = {
        "id": "model-1",
        "model_name": "primary",
        "display_name": "Primary Model",
    }
    fallback_config = {
        "id": "model-1",
        "model_name": "primary",
        "display_name": "Primary Model",
    }

    async def fail_fn(cfg):
        raise ValueError("API error")

    with pytest.raises(ValueError, match="API error"):
        await call_llm_with_fallback(
            primary_model_config=primary_config,
            default_model_config=fallback_config,
            call_fn=fail_fn,
        )


@pytest.mark.asyncio
async def test_fallback_different_model_success():
    primary_config = {
        "id": "model-1",
        "model_name": "primary",
        "display_name": "Primary Model",
    }
    fallback_config = {
        "id": "model-2",
        "model_name": "fallback",
        "display_name": "Fallback Model",
    }

    async def call_fn(cfg):
        if cfg["id"] == "model-1":
            raise ValueError("Primary API failed")
        return f"Response from {cfg['display_name']}"

    res, was_fallback, fallback_name = await call_llm_with_fallback(
        primary_model_config=primary_config,
        default_model_config=fallback_config,
        call_fn=call_fn,
    )

    assert res == "Response from Fallback Model"
    assert was_fallback is True
    assert fallback_name == "Fallback Model"


@pytest.mark.asyncio
async def test_fallback_different_model_both_fail():
    primary_config = {
        "id": "model-1",
        "model_name": "primary",
        "display_name": "Primary Model",
    }
    fallback_config = {
        "id": "model-2",
        "model_name": "fallback",
        "display_name": "Fallback Model",
    }

    async def call_fn(cfg):
        if cfg["id"] == "model-1":
            raise ValueError("Primary failed")
        raise RuntimeError("Fallback failed")

    with pytest.raises(RuntimeError, match="Fallback failed"):
        await call_llm_with_fallback(
            primary_model_config=primary_config,
            default_model_config=fallback_config,
            call_fn=call_fn,
        )


@pytest.mark.asyncio
async def test_fallback_streaming_success_primary():
    primary_config = {"id": "model-1", "model_name": "primary"}
    fallback_config = {"id": "model-2", "model_name": "fallback"}

    async def stream_fn(cfg):
        async def generator():
            yield "token", "hello"
            yield "token", "world"

        return generator()

    res, was_fallback, fallback_name = await call_llm_with_fallback(
        primary_model_config=primary_config,
        default_model_config=fallback_config,
        call_fn=stream_fn,
    )

    assert was_fallback is False
    assert fallback_name is None

    tokens = []
    async for event_type, val in res:
        tokens.append(val)
    assert tokens == ["hello", "world"]


@pytest.mark.asyncio
async def test_fallback_streaming_fallback_success():
    primary_config = {"id": "model-1", "model_name": "primary"}
    fallback_config = {
        "id": "model-2",
        "model_name": "fallback",
        "display_name": "Fallback",
    }

    async def stream_fn(cfg):
        if cfg["id"] == "model-1":
            # Fail on first yield/anext
            async def generator():
                raise ValueError("Stream connection failed")
                yield "token", "never"

            return generator()
        else:

            async def generator():
                yield "token", "fallback_token"

            return generator()

    res, was_fallback, fallback_name = await call_llm_with_fallback(
        primary_model_config=primary_config,
        default_model_config=fallback_config,
        call_fn=stream_fn,
    )

    assert was_fallback is True
    assert fallback_name == "Fallback"

    tokens = []
    async for event_type, val in res:
        tokens.append(val)
    assert tokens == ["fallback_token"]


@pytest.mark.asyncio
async def test_translate_nl_to_sql_fallback():
    from app.services.database_service import translate_nl_to_sql
    from unittest.mock import MagicMock, AsyncMock, patch

    mock_db = MagicMock()

    # Mock default model retrieval
    primary_model = MagicMock(
        id="model-1", provider_id="openai", model_name="primary-gpt", api_key=""
    )
    fallback_model = MagicMock(
        id="model-2", provider_id="openai", model_name="fallback-gpt", api_key=""
    )

    # Set up mock queries for available models
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        primary_model,  # first db_model lookup
        fallback_model,  # default model query
    ]

    # Mock client completions create call
    # Primary call raises rate limit exception, fallback succeeds
    primary_client = MagicMock()
    primary_client.chat.completions.create = AsyncMock(
        side_effect=ValueError("Quota Exceeded")
    )

    fallback_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="SELECT * FROM roles"))]
    mock_resp.usage = None
    fallback_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    def custom_get_llm_client(cfg):
        if cfg.id == "model-1":
            return primary_client
        return fallback_client

    with patch("app.core.utils.get_llm_client", side_effect=custom_get_llm_client):
        sql = await translate_nl_to_sql(
            query="list roles",
            schema_data_filtered={"tables": []},
            engine_type="postgresql",
            db=mock_db,
            model_id="model-1",
            tenant_id="tenant-123",
        )
        assert sql == "SELECT * FROM roles"

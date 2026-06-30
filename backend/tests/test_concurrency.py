import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
import pytest
from unittest.mock import MagicMock, patch
import uuid

from app.models.enums import FileType, DocumentStatus
from app.services.rag_service import run_rag_pipeline


class MockUser:
    def __init__(self):
        self.id = uuid.uuid4()
        self.tenant_id = uuid.uuid4()
        self.role_id = uuid.uuid4()


class MockDocument:
    def __init__(self, file_type, filename, excel_schema=None):
        self.id = uuid.uuid4()
        self.file_type = file_type
        self.filename = filename
        self.excel_schema = excel_schema
        self.qdrant_collection = "mock_collection"
        self.status = DocumentStatus.ready
        self.file_path = f"/mock/path/{filename}"


class MockEvent:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class MockUsage:
    def __init__(self, input_tokens=10, output_tokens=20):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class MockFinalMessage:
    def __init__(self):
        self.usage = MockUsage()


class MockStream:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def __aiter__(self):
        yield MockEvent("Mocked answer token")

    async def get_final_message(self):
        return MockFinalMessage()


class MockMessages:
    def stream(self, *args, **kwargs):
        return MockStream()


class MockAnthropicClient:
    def __init__(self):
        self.messages = MockMessages()


class MockCrossEncoder:
    def predict(self, pairs):
        return [0.9] * len(pairs)


@pytest.mark.asyncio
async def test_rag_pipeline_concurrency():
    """Verify that Qdrant search and Excel query execution are executed concurrently when both are applicable."""
    user = MockUser()
    db = MagicMock()

    doc_pdf = MockDocument(FileType.pdf, "doc.pdf")
    doc_excel = MockDocument(FileType.excel, "sheet.xlsx", excel_schema={"cols": []})

    docs_query = db.query.return_value.outerjoin.return_value.filter.return_value
    docs_query.distinct.return_value.all.return_value = [doc_pdf, doc_excel]

    # Mock calls
    def mock_embed_text(text):
        return [0.1] * 1024

    def mock_search_vectors(*args, **kwargs):
        time.sleep(0.3)
        return [
            {
                "payload": {
                    "document_id": str(doc_pdf.id),
                    "chunk_text": "Qdrant Chunk",
                    "chunk_index": 0,
                }
            }
        ]

    def mock_execute_excel_query(*args, **kwargs):
        time.sleep(0.3)
        return "Excel Answer"

    mock_client = MockAnthropicClient()

    with (
        patch("app.services.embedding_service.embed_text", side_effect=mock_embed_text),
        patch(
            "app.services.rag_service.search_vectors", side_effect=mock_search_vectors
        ),
        patch(
            "app.services.rag_service.execute_excel_query",
            side_effect=mock_execute_excel_query,
        ),
        patch(
            "app.services.rag_service._get_cross_encoder",
            return_value=MockCrossEncoder(),
        ),
        patch(
            "app.services.rag_service._get_async_anthropic_client",
            return_value=mock_client,
        ),
    ):
        start_time = time.time()

        # Consume the async generator
        events = []
        async for event in run_rag_pipeline("test query", user, db):
            events.append(event)

        end_time = time.time()
        duration = end_time - start_time

        print(f"\nBoth applicable: Duration: {duration:.4f} seconds")

        # Concurrency check: If executed sequentially, it would take >= 0.6 seconds.
        # Concurrently, it should take ~0.3 seconds.
        assert duration < 0.5, (
            f"Expected pipeline to run concurrently, but it took {duration:.4f} seconds"
        )

        # Verify done event contents to be sure it merged properly
        done_event = next(e for e in events if e["type"] == "done")
        assert done_event["answer"] == "Mocked answer token"
        assert len(done_event["citations"]) == 1
        assert done_event["citations"][0]["document_id"] == str(doc_pdf.id)


@pytest.mark.asyncio
async def test_rag_pipeline_only_qdrant():
    """Verify that when no Excel documents with schema are available, Excel pipeline is skipped and only Qdrant runs."""
    user = MockUser()
    db = MagicMock()

    doc_pdf = MockDocument(FileType.pdf, "doc.pdf")

    docs_query = db.query.return_value.outerjoin.return_value.filter.return_value
    docs_query.distinct.return_value.all.return_value = [doc_pdf]

    # Mock calls
    def mock_embed_text(text):
        return [0.1] * 1024

    qdrant_called = False

    def mock_search_vectors(*args, **kwargs):
        nonlocal qdrant_called
        qdrant_called = True
        return [
            {
                "payload": {
                    "document_id": str(doc_pdf.id),
                    "chunk_text": "Qdrant Chunk",
                    "chunk_index": 0,
                }
            }
        ]

    excel_called = False

    def mock_execute_excel_query(*args, **kwargs):
        nonlocal excel_called
        excel_called = True
        return "Excel Answer"

    mock_client = MockAnthropicClient()

    with (
        patch("app.services.embedding_service.embed_text", side_effect=mock_embed_text),
        patch(
            "app.services.rag_service.search_vectors", side_effect=mock_search_vectors
        ),
        patch(
            "app.services.rag_service.execute_excel_query",
            side_effect=mock_execute_excel_query,
        ),
        patch(
            "app.services.rag_service._get_cross_encoder",
            return_value=MockCrossEncoder(),
        ),
        patch(
            "app.services.rag_service._get_async_anthropic_client",
            return_value=mock_client,
        ),
    ):
        events = []
        async for event in run_rag_pipeline("test query", user, db):
            events.append(event)

        assert qdrant_called is True
        assert excel_called is False

        done_event = next(e for e in events if e["type"] == "done")
        assert done_event["answer"] == "Mocked answer token"


@pytest.mark.asyncio
async def test_rag_pipeline_only_excel():
    """Verify that when no non-Excel documents are available, Qdrant is skipped and only Excel pipeline runs."""
    user = MockUser()
    db = MagicMock()

    doc_excel = MockDocument(FileType.excel, "sheet.xlsx", excel_schema={"cols": []})

    docs_query = db.query.return_value.outerjoin.return_value.filter.return_value
    docs_query.distinct.return_value.all.return_value = [doc_excel]

    # Mock calls
    def mock_embed_text(text):
        return [0.1] * 1024

    qdrant_called = False

    def mock_search_vectors(*args, **kwargs):
        nonlocal qdrant_called
        qdrant_called = True
        return []

    excel_called = False

    def mock_execute_excel_query(*args, **kwargs):
        nonlocal excel_called
        excel_called = True
        return "Excel Answer"

    mock_client = MockAnthropicClient()

    with (
        patch("app.services.embedding_service.embed_text", side_effect=mock_embed_text),
        patch(
            "app.services.rag_service.search_vectors", side_effect=mock_search_vectors
        ),
        patch(
            "app.services.rag_service.execute_excel_query",
            side_effect=mock_execute_excel_query,
        ),
        patch(
            "app.services.rag_service._get_cross_encoder",
            return_value=MockCrossEncoder(),
        ),
        patch(
            "app.services.rag_service._get_async_anthropic_client",
            return_value=mock_client,
        ),
    ):
        events = []
        async for event in run_rag_pipeline("test query", user, db):
            events.append(event)

        assert qdrant_called is False
        assert excel_called is True

        done_event = next(e for e in events if e["type"] == "done")
        assert done_event["answer"] == "Mocked answer token"


@pytest.mark.asyncio
async def test_rag_pipeline_gather_exception_handling():
    """Verify that when a branch raises a BaseException, the outer gather catches it safely and sets results to empty."""
    user = MockUser()
    db = MagicMock()

    doc_pdf = MockDocument(FileType.pdf, "doc.pdf")
    doc_excel = MockDocument(FileType.excel, "sheet.xlsx", excel_schema={"cols": []})

    docs_query = db.query.return_value.outerjoin.return_value.filter.return_value
    docs_query.distinct.return_value.all.return_value = [doc_pdf, doc_excel]

    # Mock calls
    def mock_embed_text(text):
        return [0.1] * 1024

    def mock_search_vectors(*args, **kwargs):
        raise BaseException("Critical Qdrant System Failure")

    def mock_execute_excel_query(*args, **kwargs):
        return "Excel Answer"

    mock_client = MockAnthropicClient()

    with (
        patch("app.services.embedding_service.embed_text", side_effect=mock_embed_text),
        patch(
            "app.services.rag_service.search_vectors", side_effect=mock_search_vectors
        ),
        patch(
            "app.services.rag_service.execute_excel_query",
            side_effect=mock_execute_excel_query,
        ),
        patch(
            "app.services.rag_service._get_cross_encoder",
            return_value=MockCrossEncoder(),
        ),
        patch(
            "app.services.rag_service._get_async_anthropic_client",
            return_value=mock_client,
        ),
        patch("app.services.rag_service.logger.error") as mock_log_error,
    ):
        events = []
        async for event in run_rag_pipeline("test query", user, db):
            events.append(event)

        assert mock_log_error.called
        args, kwargs = mock_log_error.call_args
        assert args[0] == "%s branch failed with exception: %s"
        assert args[1] == "qdrant"

        # Verify that Excel results are still processed and Qdrant results are empty
        done_event = next(e for e in events if e["type"] == "done")
        assert done_event["answer"] == "Mocked answer token"
        assert len(done_event["citations"]) == 0


@pytest.mark.asyncio
async def test_rag_pipeline_reranking_logic():
    """Verify that search_vectors is called with limit=15, and cross-encoder re-ranks and truncates results to top 5."""
    user = MockUser()
    db = MagicMock()

    doc_pdf = MockDocument(FileType.pdf, "doc.pdf")
    docs_query = db.query.return_value.outerjoin.return_value.filter.return_value
    docs_query.distinct.return_value.all.return_value = [doc_pdf]

    # 15 dummy hits
    dummy_hits = []
    for i in range(15):
        dummy_hits.append(
            {
                "payload": {
                    "document_id": str(doc_pdf.id),
                    "chunk_text": f"Chunk {i}",
                    "chunk_index": i,
                },
                "score": 0.1 * i,  # RRF score increases with index
            }
        )

    def mock_embed_text(text):
        return [0.1] * 1024

    search_limit_passed = None

    def mock_search_vectors(*args, **kwargs):
        nonlocal search_limit_passed
        search_limit_passed = kwargs.get("limit")
        return list(dummy_hits)  # Return a copy

    class CustomMockCrossEncoder:
        def predict(self, pairs):
            # Let's return scores in reverse order: Chunk 14 gets lowest score, Chunk 0 gets highest
            # pairs is list of (query, chunk_text)
            return [15.0 - float(pair[1].split()[-1]) for pair in pairs]

    mock_client = MockAnthropicClient()

    with (
        patch("app.services.embedding_service.embed_text", side_effect=mock_embed_text),
        patch(
            "app.services.rag_service.search_vectors", side_effect=mock_search_vectors
        ),
        patch(
            "app.services.rag_service._get_cross_encoder",
            return_value=CustomMockCrossEncoder(),
        ),
        patch(
            "app.services.rag_service._get_async_anthropic_client",
            return_value=mock_client,
        ),
    ):
        events = []
        async for event in run_rag_pipeline("test query", user, db):
            events.append(event)

        assert search_limit_passed == 15

        done_event = next(e for e in events if e["type"] == "done")
        assert done_event["answer"] == "Mocked answer token"
        citations = done_event["citations"]

        # Verify truncation
        assert len(citations) == 5

        # Verify sorting: Chunk 0, 1, 2, 3, 4 should be the top ones since their score was (15 - i)
        # i.e. Chunk 0 score is 15.0, Chunk 1 score is 14.0, etc.
        for idx, citation in enumerate(citations):
            assert citation["chunk_index"] == idx


@pytest.mark.asyncio
async def test_rag_pipeline_reranking_fallback():
    """Verify that when cross-encoder fails, the pipeline falls back to original RRF order truncated to top 5."""
    user = MockUser()
    db = MagicMock()

    doc_pdf = MockDocument(FileType.pdf, "doc.pdf")
    docs_query = db.query.return_value.outerjoin.return_value.filter.return_value
    docs_query.distinct.return_value.all.return_value = [doc_pdf]

    # 15 dummy hits
    dummy_hits = []
    for i in range(15):
        dummy_hits.append(
            {
                "payload": {
                    "document_id": str(doc_pdf.id),
                    "chunk_text": f"Chunk {i}",
                    "chunk_index": i,
                },
                "score": 0.1 * i,
            }
        )

    def mock_embed_text(text):
        return [0.1] * 1024

    def mock_search_vectors(*args, **kwargs):
        return list(dummy_hits)

    class ErrorMockCrossEncoder:
        def predict(self, pairs):
            raise RuntimeError("Simulation of model execution failure")

    mock_client = MockAnthropicClient()

    with (
        patch("app.services.embedding_service.embed_text", side_effect=mock_embed_text),
        patch(
            "app.services.rag_service.search_vectors", side_effect=mock_search_vectors
        ),
        patch(
            "app.services.rag_service._get_cross_encoder",
            return_value=ErrorMockCrossEncoder(),
        ),
        patch(
            "app.services.rag_service._get_async_anthropic_client",
            return_value=mock_client,
        ),
        patch("app.services.rag_service.logger.error") as mock_log_error,
    ):
        events = []
        async for event in run_rag_pipeline("test query", user, db):
            events.append(event)

        assert mock_log_error.called
        # Check that error is logged
        args, kwargs = mock_log_error.call_args
        assert "CrossEncoder re-ranking failed" in args[0]

        done_event = next(e for e in events if e["type"] == "done")
        citations = done_event["citations"]

        # Verify truncation
        assert len(citations) == 5

        # Verify it falls back to original order: Chunk 0, 1, 2, 3, 4 (since list was returned in that order)
        for idx, citation in enumerate(citations):
            assert citation["chunk_index"] == idx


@pytest.mark.asyncio
async def test_rag_pipeline_reranking_disabled():
    """Verify that when ENABLE_CROSS_ENCODER_RERANKING is False, the pipeline returns RRF order and does not call _get_cross_encoder."""
    user = MockUser()
    db = MagicMock()

    doc_pdf = MockDocument(FileType.pdf, "doc.pdf")
    docs_query = db.query.return_value.outerjoin.return_value.filter.return_value
    docs_query.distinct.return_value.all.return_value = [doc_pdf]

    # 15 dummy hits
    dummy_hits = []
    for i in range(15):
        dummy_hits.append(
            {
                "payload": {
                    "document_id": str(doc_pdf.id),
                    "chunk_text": f"Chunk {i}",
                    "chunk_index": i,
                },
                "score": 0.1 * i,
            }
        )

    def mock_embed_text(text):
        return [0.1] * 1024

    def mock_search_vectors(*args, **kwargs):
        return list(dummy_hits)

    mock_client = MockAnthropicClient()

    with (
        patch("app.services.embedding_service.embed_text", side_effect=mock_embed_text),
        patch(
            "app.services.rag_service.search_vectors", side_effect=mock_search_vectors
        ),
        patch("app.services.rag_service._get_cross_encoder") as mock_get_cross_encoder,
        patch(
            "app.services.rag_service._get_async_anthropic_client",
            return_value=mock_client,
        ),
        patch("app.core.config.settings.ENABLE_CROSS_ENCODER_RERANKING", False),
    ):
        events = []
        async for event in run_rag_pipeline("test query", user, db):
            events.append(event)

        # _get_cross_encoder should NOT be called
        mock_get_cross_encoder.assert_not_called()

        done_event = next(e for e in events if e["type"] == "done")
        citations = done_event["citations"]

        # Verify truncation to top 5
        assert len(citations) == 5

        # Verify it falls back to original order: Chunk 0, 1, 2, 3, 4 (since list was returned in that order)
        for idx, citation in enumerate(citations):
            assert citation["chunk_index"] == idx

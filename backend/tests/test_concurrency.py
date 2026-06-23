import time
import pytest
import asyncio
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

class MockStream:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    async def __aiter__(self):
        yield MockEvent("Mocked answer token")

class MockMessages:
    def stream(self, *args, **kwargs):
        return MockStream()

class MockAnthropicClient:
    def __init__(self):
        self.messages = MockMessages()

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
        return [{"payload": {"document_id": str(doc_pdf.id), "chunk_text": "Qdrant Chunk", "chunk_index": 0}}]
        
    def mock_execute_excel_query(*args, **kwargs):
        time.sleep(0.3)
        return "Excel Answer"
        
    mock_client = MockAnthropicClient()
    
    with patch("app.services.embedding_service.embed_text", side_effect=mock_embed_text), \
         patch("app.services.rag_service.search_vectors", side_effect=mock_search_vectors), \
         patch("app.services.rag_service.execute_excel_query", side_effect=mock_execute_excel_query), \
         patch("app.services.rag_service._get_async_anthropic_client", return_value=mock_client):
         
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
        assert duration < 0.5, f"Expected pipeline to run concurrently, but it took {duration:.4f} seconds"
        
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
        return [{"payload": {"document_id": str(doc_pdf.id), "chunk_text": "Qdrant Chunk", "chunk_index": 0}}]
        
    excel_called = False
    def mock_execute_excel_query(*args, **kwargs):
        nonlocal excel_called
        excel_called = True
        return "Excel Answer"
        
    mock_client = MockAnthropicClient()
    
    with patch("app.services.embedding_service.embed_text", side_effect=mock_embed_text), \
         patch("app.services.rag_service.search_vectors", side_effect=mock_search_vectors), \
         patch("app.services.rag_service.execute_excel_query", side_effect=mock_execute_excel_query), \
         patch("app.services.rag_service._get_async_anthropic_client", return_value=mock_client):
         
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
    
    with patch("app.services.embedding_service.embed_text", side_effect=mock_embed_text), \
         patch("app.services.rag_service.search_vectors", side_effect=mock_search_vectors), \
         patch("app.services.rag_service.execute_excel_query", side_effect=mock_execute_excel_query), \
         patch("app.services.rag_service._get_async_anthropic_client", return_value=mock_client):
         
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
    
    with patch("app.services.embedding_service.embed_text", side_effect=mock_embed_text), \
         patch("app.services.rag_service.search_vectors", side_effect=mock_search_vectors), \
         patch("app.services.rag_service.execute_excel_query", side_effect=mock_execute_excel_query), \
         patch("app.services.rag_service._get_async_anthropic_client", return_value=mock_client), \
         patch("app.services.rag_service.logger.error") as mock_log_error:
         
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

from unittest.mock import MagicMock, patch
import pytest
from app.services.qdrant_service import (
    search_vectors,
    get_sparse_model,
    generate_sparse_vector,
)


def test_get_sparse_model_disabled():
    with patch("app.core.config.settings.ENABLE_SPARSE_SEARCH", False):
        with pytest.raises(RuntimeError, match="Sparse search is disabled"):
            get_sparse_model()


def test_generate_sparse_vector_disabled():
    with patch("app.core.config.settings.ENABLE_SPARSE_SEARCH", False):
        result = generate_sparse_vector("hello")
        assert result == {"indices": [], "values": []}


def test_search_vectors_disabled():
    mock_client = MagicMock()
    mock_points = MagicMock()
    mock_points.points = []
    mock_client.query_points.return_value = mock_points

    with (
        patch("app.services.qdrant_service._get_client", return_value=mock_client),
        patch("app.core.config.settings.ENABLE_SPARSE_SEARCH", False),
    ):
        results = search_vectors(
            collection_name="test_col",
            query_text="hello",
            query_vector=[0.1] * 3072,
            role_ids=["role1"],
            limit=5,
        )

        assert results == []
        mock_client.query_points.assert_called_once()
        # Verify it was called with query and using="dense"
        kwargs = mock_client.query_points.call_args[1]
        assert kwargs["query"] == [0.1] * 3072
        assert kwargs["using"] == "dense"
        assert "prefetch" not in kwargs


def test_search_vectors_enabled():
    mock_client = MagicMock()
    mock_points = MagicMock()
    mock_points.points = []
    mock_client.query_points.return_value = mock_points

    mock_sparse_model = MagicMock()
    mock_embedding = MagicMock()
    mock_embedding.indices = MagicMock(tolist=lambda: [1, 2])
    mock_embedding.values = MagicMock(tolist=lambda: [0.5, 0.6])
    mock_sparse_model.embed.return_value = [mock_embedding]

    with (
        patch("app.services.qdrant_service._get_client", return_value=mock_client),
        patch(
            "app.services.qdrant_service.get_sparse_model",
            return_value=mock_sparse_model,
        ),
        patch("app.core.config.settings.ENABLE_SPARSE_SEARCH", True),
    ):
        results = search_vectors(
            collection_name="test_col",
            query_text="hello",
            query_vector=[0.1] * 3072,
            role_ids=["role1"],
            limit=5,
        )

        assert results == []
        mock_client.query_points.assert_called_once()
        # Verify it was called with prefetch and FusionQuery
        kwargs = mock_client.query_points.call_args[1]
        assert "prefetch" in kwargs
        assert kwargs.get("using") is None

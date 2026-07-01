"""
Qdrant vector database service for managing tenant collections and document vectors.
"""

import logging
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    FilterSelector,
    SparseVectorParams,
    Modifier,
    Prefetch,
    FusionQuery,
    Fusion,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# VECTOR_SIZE = (
#     1024  # BAAI/bge-large-en-v1.5 output dimension (sentence-transformers, active)
# )
VECTOR_SIZE = 3072  # gemini-embedding-2 output dimension

_sparse_model: Optional["SparseTextEmbedding"] = None  # noqa: F821


def get_sparse_model() -> Optional["SparseTextEmbedding"]:  # noqa: F821
    global _sparse_model
    if not settings.ENABLE_SPARSE_SEARCH:
        raise RuntimeError("Sparse search is disabled via configuration.")
    if _sparse_model is None:
        from fastembed import SparseTextEmbedding

        _sparse_model = SparseTextEmbedding("Qdrant/bm25")
    return _sparse_model


def generate_sparse_vector(text: str) -> dict:
    if not settings.ENABLE_SPARSE_SEARCH:
        return {"indices": [], "values": []}
    model = get_sparse_model()
    embeddings = list(model.embed([text]))
    embedding = embeddings[0]
    return {"indices": embedding.indices.tolist(), "values": embedding.values.tolist()}


def _get_client() -> QdrantClient:
    """Initialise and return a Qdrant client using settings."""
    return QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )


def get_or_create_tenant_collection(tenant_id: str) -> str:
    """
    Return the collection name for a tenant, creating it if it does not exist.

    Collection name format: tenant_{tenant_id}
    Uses cosine distance and 3072-dimensional vectors.
    """
    collection_name = f"tenant_{tenant_id}"
    client = _get_client()

    existing = [c.name for c in client.get_collections().collections]
    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.COSINE,
                )
            },
            sparse_vectors_config={"sparse": SparseVectorParams(modifier=Modifier.IDF)},
        )

        # Create indexes for fields we use in Filters
        from qdrant_client.models import PayloadSchemaType

        client.create_payload_index(
            collection_name=collection_name,
            field_name="role_ids",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        client.create_payload_index(
            collection_name=collection_name,
            field_name="document_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        logger.info("Created Qdrant collection and indexes: %s", collection_name)
    else:
        logger.debug("Qdrant collection already exists: %s", collection_name)

    return collection_name


def upsert_vectors(collection_name: str, points: list[dict]) -> None:
    """
    Upsert a list of vector points into the given collection.

    Each point dict must contain:
      - id: UUID string
      - dense_vector: list[float]
      - sparse_vector: dict with 'indices' and 'values'
      - payload: dict
    """
    client = _get_client()
    qdrant_points = [
        PointStruct(
            id=p["id"],
            vector={"dense": p["dense_vector"], "sparse": p["sparse_vector"]},
            payload=p["payload"],
        )
        for p in points
    ]
    client.upsert(collection_name=collection_name, points=qdrant_points)
    logger.debug("Upserted %d vectors into %s", len(qdrant_points), collection_name)


def delete_document_vectors(collection_name: str, document_id: str) -> None:
    """
    Delete all vectors in the collection whose payload document_id matches.
    """
    client = _get_client()
    client.delete(
        collection_name=collection_name,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            )
        ),
    )
    logger.info("Deleted vectors for document %s from %s", document_id, collection_name)


def search_vectors(
    collection_name: str,
    query_text: str,
    query_vector: list[float],
    role_ids: list[str],
    limit: int = 5,
    document_id: Optional[str] = None,
) -> list[dict]:
    """
    Perform a semantic search with a role-based access filter using Hybrid Search.

    Only returns results where the payload role_ids contains at least one
    of the user's role_ids (MatchAny).
    """
    client = _get_client()

    must_conditions = [
        FieldCondition(
            key="role_ids",
            match=MatchAny(any=role_ids),
        )
    ]
    if document_id:
        must_conditions.append(
            FieldCondition(
                key="document_id",
                match=MatchValue(value=document_id),
            )
        )

    role_filter = Filter(must=must_conditions)

    if not settings.ENABLE_SPARSE_SEARCH:
        results = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            using="dense",
            query_filter=role_filter,
            limit=limit,
            with_payload=True,
        ).points
    else:
        # Generate sparse vector for query
        sparse_query = generate_sparse_vector(query_text)

        results = client.query_points(
            collection_name=collection_name,
            prefetch=[
                Prefetch(
                    query=query_vector, using="dense", filter=role_filter, limit=20
                ),
                Prefetch(
                    query=sparse_query, using="sparse", filter=role_filter, limit=20
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=limit,
            with_payload=True,
        ).points
    return [{"payload": hit.payload, "score": hit.score} for hit in results]


def update_document_payload(
    collection_name: str, document_id: str, payload: dict
) -> None:
    """
    Set/overwrite specific payload fields on all vectors matching the document_id.
    Used to update role_ids after access policy changes.
    """
    client = _get_client()
    client.set_payload(
        collection_name=collection_name,
        payload=payload,
        points=Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=document_id),
                )
            ]
        ),
    )
    logger.info("Updated payload for document %s in %s", document_id, collection_name)

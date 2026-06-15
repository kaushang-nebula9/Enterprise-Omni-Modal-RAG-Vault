"""
Qdrant vector database service for managing tenant collections and document vectors.
"""
import logging
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
    SetPayload,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

VECTOR_SIZE = 3072  # gemini-embedding-2-preview output dimension


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
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )
        logger.info("Created Qdrant collection: %s", collection_name)
    else:
        logger.debug("Qdrant collection already exists: %s", collection_name)

    return collection_name


def upsert_vectors(collection_name: str, points: list[dict]) -> None:
    """
    Upsert a list of vector points into the given collection.

    Each point dict must contain:
      - id: UUID string
      - vector: list[float]
      - payload: dict
    """
    client = _get_client()
    qdrant_points = [
        PointStruct(
            id=p["id"],
            vector=p["vector"],
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
    query_vector: list[float],
    role_ids: list[str],
    limit: int = 5,
) -> list[dict]:
    """
    Perform a semantic search with a role-based access filter.

    Only returns results where the payload role_ids contains at least one
    of the user's role_ids (MatchAny).
    """
    client = _get_client()
    results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="role_ids",
                    match=MatchAny(any=role_ids),
                )
            ]
        ),
        limit=limit,
        with_payload=True,
    )
    return [{"payload": hit.payload, "score": hit.score} for hit in results]


def update_document_payload(collection_name: str, document_id: str, payload: dict) -> None:
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

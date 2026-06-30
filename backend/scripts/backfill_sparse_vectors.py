import os
import sys
import logging

# Ensure the backend directory is in the sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from qdrant_client import QdrantClient

from app.db.session import SessionLocal

# Import all models to ensure they are registered in SQLAlchemy mapper
from app.models.document import Document

from app.models.enums import DocumentStatus, FileType
from app.core.config import settings
from app.services import qdrant_service
from app.tasks.document_tasks import process_document_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill")


def run_backfill():
    db: Session = SessionLocal()
    qdrant_client = QdrantClient(
        url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY
    )

    try:
        # Fetch all documents where status = ready and file_type != excel
        documents = (
            db.query(Document)
            .filter(
                Document.status == DocumentStatus.ready,
                Document.file_type != FileType.excel,
            )
            .all()
        )

        # Group documents by tenant
        tenant_docs = {}
        for doc in documents:
            tenant_id = str(doc.tenant_id)
            if tenant_id not in tenant_docs:
                tenant_docs[tenant_id] = []
            tenant_docs[tenant_id].append(doc)

        tenant_count = len(tenant_docs)
        total_count = 0

        for tenant_id, docs in tenant_docs.items():
            collection_name = f"tenant_{tenant_id}"

            # Delete existing collection
            try:
                qdrant_client.delete_collection(collection_name=collection_name)
                logger.info(f"Deleted Qdrant collection: {collection_name}")
            except Exception as e:
                logger.warning(f"Could not delete collection {collection_name}: {e}")

            # Recreate it using updated get_or_create_tenant_collection
            qdrant_service.get_or_create_tenant_collection(tenant_id)
            logger.info(f"Recreated Qdrant collection: {collection_name}")

            for doc in docs:
                print("#################")
                print(
                    f"Queued document for reprocessing: {doc.filename} (tenant: {tenant_id})\n"
                )

                try:
                    process_document_task.delay(str(doc.id))
                    total_count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to queue document {doc.filename} ({doc.id}): {e}",
                        exc_info=True,
                    )

        print("#################")
        print(
            f"Backfill complete. Queued {total_count} documents for reprocessing across {tenant_count} tenants.\n"
        )

    finally:
        db.close()


if __name__ == "__main__":
    run_backfill()

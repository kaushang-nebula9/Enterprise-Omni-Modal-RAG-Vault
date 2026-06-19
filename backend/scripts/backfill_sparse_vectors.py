import os
import sys
import logging

# Ensure the backend directory is in the sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from qdrant_client import QdrantClient

from app.db.session import SessionLocal

# Import all models to ensure they are registered in SQLAlchemy mapper
from app.models.tenant import Tenant
from app.models.user import User
from app.models.role import Role
from app.models.document import Document
from app.models.document_access_policy import DocumentAccessPolicy
from app.models.invite_token import InviteToken
from app.models.otp_verification import OTPVerification
from app.models.query_session import QuerySession
from app.models.query_message import QueryMessage
from app.models.query_citation import QueryCitation
from app.models.refresh_token import RefreshToken

from app.models.enums import DocumentStatus, FileType
from app.core.config import settings
from app.services import qdrant_service
from app.services.document_processor import process_document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill")

def run_backfill():
    db: Session = SessionLocal()
    qdrant_client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    
    try:
        # Fetch all documents where status = ready and file_type != excel
        documents = (
            db.query(Document)
            .filter(
                Document.status == DocumentStatus.ready,
                Document.file_type != FileType.excel
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
                print(f"Reprocessing document: {doc.filename} (tenant: {tenant_id})\n")
                
                try:
                    process_document(str(doc.id), db)
                    total_count += 1
                except Exception as e:
                    logger.error(f"Failed to reprocess document {doc.filename} ({doc.id}): {e}", exc_info=True)
                    
        print("#################")
        print(f"Backfill complete. Reprocessed {total_count} documents across {tenant_count} tenants.\n")
        
    finally:
        db.close()

if __name__ == "__main__":
    run_backfill()

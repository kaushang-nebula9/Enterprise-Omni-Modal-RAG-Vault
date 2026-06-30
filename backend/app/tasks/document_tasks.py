from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.document_processor import process_document

# Import ALL models so SQLAlchemy's mapper can resolve every string-based
# relationship (e.g. relationship('Tenant') on User) before any query runs.
# The Celery worker process does not go through FastAPI's startup sequence,
# so models are only loaded on-demand — without these imports the mapper
# raises InvalidRequestError when it first tries to configure itself.
import app.models.tenant  # noqa: F401
import app.models.user  # noqa: F401
import app.models.role  # noqa: F401
import app.models.document  # noqa: F401
import app.models.document_access_policy  # noqa: F401
import app.models.invite_token  # noqa: F401
import app.models.otp_verification  # noqa: F401
import app.models.query_session  # noqa: F401
import app.models.query_message  # noqa: F401
import app.models.query_citation  # noqa: F401
import app.models.refresh_token  # noqa: F401


@celery_app.task(
    name="process_document_task", bind=True, max_retries=2, default_retry_delay=30
)
def process_document_task(self, document_id: str):
    db = SessionLocal()
    try:
        process_document(document_id, db)
    except Exception as exc:
        print("#################")
        print(
            f"Celery task failed for document {document_id}, retrying. Error: {str(exc)}\n"
        )
        raise self.retry(exc=exc)
    finally:
        db.close()

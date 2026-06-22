# Enterprise OmniModal RAG Vault

A multi-tenant RAG system with role-based access control.

## Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL
- Redis (for Celery task queue)
- A Qdrant instance (cloud or local)

### Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
.\venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in the values.

### Running Locally

You need **two terminals** to run the full backend:

```bash
# Terminal 1 - FastAPI server
cd backend
python run.py
```

```bash
# Terminal 2 - Celery worker
cd backend
celery -A app.celery_app worker --loglevel=info --pool=solo
```

The FastAPI server handles HTTP requests and enqueues document processing tasks.
The Celery worker picks up those tasks from Redis and runs the ingestion pipeline
(text extraction, chunking, embedding, Qdrant upsert) in a separate process.

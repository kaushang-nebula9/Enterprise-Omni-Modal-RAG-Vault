from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router

import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="Enterprise OmniModal RAG Vault API")
app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
def startup_event():
    logger.info("Application starting up...")
    logger.info(
        "Configuration - ENABLE_CROSS_ENCODER_RERANKING: %s",
        settings.ENABLE_CROSS_ENCODER_RERANKING,
    )
    logger.info(
        "Configuration - ENABLE_SPARSE_SEARCH: %s", settings.ENABLE_SPARSE_SEARCH
    )


origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "https://enterprise-omni-modal-rag-vault.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"status": "Enterprise RAG Vault API is running"}


@app.get("/api/providers")
def get_providers():
    from app.core.utils import PROVIDER_REGISTRY

    return PROVIDER_REGISTRY

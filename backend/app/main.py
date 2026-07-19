from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.api.reports import router as reports_router
from app.api.collections import router as collections_router
from app.api.conversations import router as conversations_router

import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="Enterprise OmniModal RAG Vault API")
app.include_router(api_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api")
app.include_router(collections_router, prefix="/api")
app.include_router(conversations_router, prefix="/api")


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
    import os

    os.makedirs(settings.REPORTS_DIR, exist_ok=True)
    logger.info(
        "Ensured reports directory exists at: %s", os.path.abspath(settings.REPORTS_DIR)
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

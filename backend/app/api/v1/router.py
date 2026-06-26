from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.roles import router as roles_router
from app.api.v1.admin import router as admin_router
from app.api.v1.documents import router as documents_router
from app.api.v1.chat import router as chat_router
from app.api.v1.personal_documents import router as personal_documents_router
from app.api.v1.departments import router as departments_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.evaluations import router as evaluations_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(roles_router, prefix="/roles", tags=["roles"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(documents_router, prefix="/documents", tags=["documents"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(personal_documents_router, prefix="/personal-documents", tags=["personal_documents"])
api_router.include_router(departments_router, prefix="/departments", tags=["departments"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(evaluations_router, prefix="/evaluations", tags=["evaluations"])


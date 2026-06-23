from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session, joinedload
from app.db.session import get_db
from app.core.dependencies import require_admin
from app.models.user import User
from app.models.tenant import Tenant
from app.models.document import Document
from app.models.role import Role
from app.models.refresh_token import RefreshToken
from app.schemas.auth import UserResponse
from app.schemas.admin import (
    AdminStatsResponse,
    UpdateMemberRequest,
    UpdateOrganisationRequest,
    TenantResponse
)
from app.schemas.auth import MessageResponse
import re
import random
from uuid import UUID

router = APIRouter()

@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_stats(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Returns total documents, members, and custom roles for the admin's tenant."""
    total_documents = db.query(Document).filter(Document.tenant_id == current_admin.tenant_id).count()
    total_members = db.query(User).filter(User.tenant_id == current_admin.tenant_id).count()
    # Excluding default roles (Admin, Member) from the roles count
    total_roles = db.query(Role).filter(
        Role.tenant_id == current_admin.tenant_id,
        Role.is_default == False
    ).count()

    return AdminStatsResponse(
        total_documents=total_documents,
        total_members=total_members,
        total_roles=total_roles
    )

@router.get("/members", response_model=list[UserResponse])
def get_admin_members(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Returns all users belonging to the admin's tenant."""
    users = db.query(User).options(joinedload(User.role).joinedload(Role.department)).filter(
        User.tenant_id == current_admin.tenant_id
    ).all()
    return users

@router.patch("/members/{user_id}", response_model=UserResponse)
def update_member(
    user_id: UUID,
    request: UpdateMemberRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update a member's role or active status."""
    target_user = db.query(User).options(joinedload(User.role).joinedload(Role.department)).filter(
        User.id == user_id,
        User.tenant_id == current_admin.tenant_id
    ).first()

    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target_user.id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot modify your own account from here")

    if target_user.role.is_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot modify another admin's account")

    if request.role_id is not None:
        new_role = db.query(Role).filter(
            Role.id == request.role_id,
            Role.tenant_id == current_admin.tenant_id
        ).first()
        if not new_role:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
        target_user.role_id = request.role_id

    if request.is_active is not None:
        target_user.is_active = request.is_active
        if not request.is_active:
            db.query(RefreshToken).filter(RefreshToken.user_id == target_user.id).update({RefreshToken.is_revoked: True})

    db.commit()
    db.refresh(target_user)
    # Re-fetch to ensure role relationship is eager-loaded
    target_user = db.query(User).options(joinedload(User.role)).filter(User.id == target_user.id).first()
    return target_user

@router.delete("/members/{user_id}", response_model=MessageResponse)
def delete_member(
    user_id: UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a user record."""
    target_user = db.query(User).options(joinedload(User.role)).filter(
        User.id == user_id,
        User.tenant_id == current_admin.tenant_id
    ).first()

    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target_user.id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account")

    if target_user.role.is_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete another admin's account")

    db.delete(target_user)
    db.commit()

    return MessageResponse(message="Member removed successfully")

@router.get("/organisation", response_model=TenantResponse)
def get_organisation(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Returns the tenant details."""
    tenant = db.query(Tenant).filter(Tenant.id == current_admin.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant

@router.patch("/organisation", response_model=TenantResponse)
def update_organisation(
    request: UpdateOrganisationRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update the tenant's name and/or website."""
    tenant = db.query(Tenant).filter(Tenant.id == current_admin.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if request.name is not None:
        tenant.name = request.name
        base_slug = re.sub(r'[^a-z0-9\-]', '', request.name.lower().replace(" ", "-"))
        slug = base_slug or "tenant"
        # Only check unique if it changed
        if slug != tenant.slug:
            while db.query(Tenant).filter(Tenant.slug == slug).first():
                slug = f"{base_slug}-{random.randint(1000, 9999)}"
            tenant.slug = slug

    if request.website is not None:
        # Convert HttpUrl to string
        tenant.website = str(request.website)

    db.commit()
    db.refresh(tenant)
    return tenant

@router.delete("/organisation", response_model=MessageResponse)
def delete_organisation(
    response: Response,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Deletes the entire tenant record and cascades all related data."""
    tenant = db.query(Tenant).filter(Tenant.id == current_admin.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    db.delete(tenant)
    db.commit()

    # Revoke cookies
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    return MessageResponse(message="Organisation deleted successfully")

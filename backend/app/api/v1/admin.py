from venv import logger
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
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
    TenantResponse,
    UsageSummaryResponse,
)
from app.schemas.auth import MessageResponse
from app.services.billing_service import calculate_tenant_monthly_cost
from app.services.audit_log_service import log_audit_event
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogListResponse
from datetime import datetime
import re
import random
from uuid import UUID

router = APIRouter()


@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_stats(
    current_admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    """Returns total documents, members, and custom roles for the admin's tenant."""
    total_documents = (
        db.query(Document).filter(Document.tenant_id == current_admin.tenant_id).count()
    )
    total_members = (
        db.query(User).filter(User.tenant_id == current_admin.tenant_id).count()
    )
    # Excluding default roles (Admin, Member) from the roles count
    total_roles = (
        db.query(Role)
        .filter(Role.tenant_id == current_admin.tenant_id, Role.is_default == False)
        .count()
    )

    return AdminStatsResponse(
        total_documents=total_documents,
        total_members=total_members,
        total_roles=total_roles,
    )


@router.get("/members", response_model=list[UserResponse])
def get_admin_members(
    current_admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    """Returns all users belonging to the admin's tenant."""
    users = (
        db.query(User)
        .options(joinedload(User.role).joinedload(Role.department))
        .filter(User.tenant_id == current_admin.tenant_id)
        .all()
    )
    return users


@router.patch("/members/{user_id}", response_model=UserResponse)
def update_member(
    user_id: UUID,
    request: UpdateMemberRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a member's role or active status."""
    target_user = (
        db.query(User)
        .options(joinedload(User.role).joinedload(Role.department))
        .filter(User.id == user_id, User.tenant_id == current_admin.tenant_id)
        .first()
    )

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if target_user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot modify your own account from here",
        )

    if target_user.role.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot modify another admin's account",
        )

    role_changed = False
    new_role = None
    old_role_name = "unknown"
    old_role_id = None
    if request.role_id is not None:
        new_role = (
            db.query(Role)
            .filter(
                Role.id == request.role_id, Role.tenant_id == current_admin.tenant_id
            )
            .first()
        )
        if not new_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role"
            )
        role_changed = target_user.role_id != request.role_id
        if role_changed:
            old_role_id = target_user.role_id
            old_role_name = target_user.role.name if target_user.role else "unknown"
        target_user.role_id = request.role_id

    if request.is_active is not None:
        target_user.is_active = request.is_active
        if not request.is_active:
            db.query(RefreshToken).filter(
                RefreshToken.user_id == target_user.id
            ).update({RefreshToken.is_revoked: True})

    db.commit()

    if role_changed and new_role:
        log_audit_event(
            db=db,
            tenant_id=current_admin.tenant_id,
            actor_user_id=current_admin.id,
            action="employee.role_changed",
            description=f"Changed role of employee '{target_user.full_name}' ({target_user.email}) from '{old_role_name}' to '{new_role.name}'",
            metadata={
                "user_id": str(target_user.id),
                "email": target_user.email,
                "old_role_id": str(old_role_id) if old_role_id else None,
                "new_role_id": str(new_role.id),
                "old_role_name": old_role_name,
                "new_role_name": new_role.name,
            },
        )

    if role_changed and new_role:
        from app.services.notification_service import create_notification
        from app.models.enums import NotificationType

        create_notification(
            db=db,
            user_id=target_user.id,
            tenant_id=target_user.tenant_id,
            type=NotificationType.role_assigned,
            message=f"You have been assigned the role: {new_role.name}",
            related_role_id=new_role.id,
        )

    db.refresh(target_user)
    # Re-fetch to ensure role relationship is eager-loaded
    target_user = (
        db.query(User)
        .options(joinedload(User.role))
        .filter(User.id == target_user.id)
        .first()
    )
    return target_user


@router.delete("/members/{user_id}", response_model=MessageResponse)
def delete_member(
    user_id: UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a user record."""
    target_user = (
        db.query(User)
        .options(joinedload(User.role))
        .filter(User.id == user_id, User.tenant_id == current_admin.tenant_id)
        .first()
    )

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if target_user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    if target_user.role.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete another admin's account",
        )

    db.delete(target_user)
    db.commit()

    return MessageResponse(message="Member removed successfully")


@router.get("/organisation", response_model=TenantResponse)
def get_organisation(
    current_admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    """Returns the tenant details."""
    tenant = db.query(Tenant).filter(Tenant.id == current_admin.tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    # Calculate estimated usage dynamically
    estimated_usage = calculate_tenant_monthly_cost(db, tenant.id)
    tenant.estimated_usage_this_month = estimated_usage
    return tenant


@router.patch("/organisation", response_model=TenantResponse)
def update_organisation(
    request: UpdateOrganisationRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update the tenant's name, website, and/or monthly budget limit."""
    tenant = db.query(Tenant).filter(Tenant.id == current_admin.tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    if request.name is not None:
        tenant.name = request.name
        base_slug = re.sub(r"[^a-z0-9\-]", "", request.name.lower().replace(" ", "-"))
        slug = base_slug or "tenant"
        # Only check unique if it changed
        if slug != tenant.slug:
            while db.query(Tenant).filter(Tenant.slug == slug).first():
                slug = f"{base_slug}-{random.randint(1000, 9999)}"
            tenant.slug = slug

    if request.website is not None:
        # Convert HttpUrl to string
        tenant.website = str(request.website)

    budget_limit_changed = False
    old_budget_limit = tenant.monthly_budget_limit
    if "monthly_budget_limit" in request.model_fields_set:
        budget_limit_changed = old_budget_limit != request.monthly_budget_limit
        tenant.monthly_budget_limit = request.monthly_budget_limit
        # Trigger budget check task in background since limit was updated
        try:
            import sys

            if "pytest" not in sys.modules:
                from app.tasks.billing_tasks import check_tenant_budgets_task

                check_tenant_budgets_task.delay()
        except Exception as task_exc:
            logger.error(
                "Failed to trigger check_tenant_budgets_task after budget update: %s",
                task_exc,
            )

    default_model_changed = False
    old_default_model_id = tenant.default_model_id
    if "default_model_id" in request.model_fields_set:
        if request.default_model_id is not None:
            # Verify it exists and is active
            model_exists = (
                db.query(AvailableModel)
                .filter(
                    AvailableModel.id == request.default_model_id,
                    AvailableModel.is_active == True,
                )
                .first()
            )
            if not model_exists:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or inactive default model",
                )
        default_model_changed = old_default_model_id != request.default_model_id
        tenant.default_model_id = request.default_model_id

    db.commit()
    db.refresh(tenant)

    if budget_limit_changed:
        limit_desc = (
            f"${tenant.monthly_budget_limit:.2f}"
            if tenant.monthly_budget_limit is not None
            else "no limit"
        )
        log_audit_event(
            db=db,
            tenant_id=tenant.id,
            actor_user_id=current_admin.id,
            action="budget_limit.updated",
            description=f"Changed monthly budget limit to {limit_desc}",
            metadata={
                "old_limit": old_budget_limit,
                "new_limit": tenant.monthly_budget_limit,
            },
        )

    if default_model_changed:
        model_name = "None"
        if tenant.default_model_id:
            model_exists = (
                db.query(AvailableModel)
                .filter(AvailableModel.id == tenant.default_model_id)
                .first()
            )
            if model_exists:
                model_name = model_exists.display_name
        log_audit_event(
            db=db,
            tenant_id=tenant.id,
            actor_user_id=current_admin.id,
            action="default_model.updated",
            description=f"Changed default model to {model_name}",
            metadata={
                "old_model_id": str(old_default_model_id)
                if old_default_model_id
                else None,
                "new_model_id": str(tenant.default_model_id)
                if tenant.default_model_id
                else None,
            },
        )

    # Attach estimated usage before returning
    estimated_usage = calculate_tenant_monthly_cost(db, tenant.id)
    tenant.estimated_usage_this_month = estimated_usage
    return tenant


@router.delete("/organisation", response_model=MessageResponse)
def delete_organisation(
    response: Response,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Deletes the entire tenant record and cascades all related data."""
    tenant = db.query(Tenant).filter(Tenant.id == current_admin.tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    db.delete(tenant)
    db.commit()

    # Revoke cookies
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    return MessageResponse(message="Organisation deleted successfully")


from app.models.available_model import AvailableModel
from app.schemas.chat import ModelResponse
from app.schemas.admin import ModelCreateRequest, ModelUpdateRequest


@router.get("/models", response_model=list[ModelResponse])
def admin_get_models(
    current_admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    """
    Returns all models (active and inactive) for management.
    """
    models = db.query(AvailableModel).order_by(AvailableModel.created_at.asc()).all()
    return models


@router.post(
    "/models", response_model=ModelResponse, status_code=status.HTTP_201_CREATED
)
def admin_create_model(
    request: ModelCreateRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new available model configuration.
    """
    new_model = AvailableModel(
        display_name=request.display_name,
        provider=request.provider,
        model_string=request.model_string,
        is_active=request.is_active,
        input_price_per_million=request.input_price_per_million,
        output_price_per_million=request.output_price_per_million,
    )
    db.add(new_model)
    db.commit()
    db.refresh(new_model)
    return new_model


@router.patch("/models/{model_id}", response_model=ModelResponse)
def admin_update_model(
    model_id: UUID,
    request: ModelUpdateRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Update an available model configuration.
    """
    db_model = db.query(AvailableModel).filter(AvailableModel.id == model_id).first()
    if not db_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Model not found"
        )

    if request.display_name is not None:
        db_model.display_name = request.display_name
    if request.provider is not None:
        db_model.provider = request.provider
    if request.model_string is not None:
        db_model.model_string = request.model_string
    if request.is_active is not None:
        db_model.is_active = request.is_active
    if "input_price_per_million" in request.model_fields_set:
        db_model.input_price_per_million = request.input_price_per_million
    if "output_price_per_million" in request.model_fields_set:
        db_model.output_price_per_million = request.output_price_per_million

    db.commit()
    db.refresh(db_model)
    return db_model


@router.delete("/models/{model_id}", response_model=MessageResponse)
def admin_delete_model(
    model_id: UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Delete an available model configuration.
    """
    db_model = db.query(AvailableModel).filter(AvailableModel.id == model_id).first()
    if not db_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Model not found"
        )

    db.delete(db_model)
    db.commit()
    return MessageResponse(message="Model deleted successfully")


from datetime import date, timedelta
from sqlalchemy import cast, Date, func, case, and_
from app.models.usage_log import UsageLog
from app.models.department import Department
from app.schemas.admin import (
    UsageSummaryItem,
    DashboardOverviewResponse,
    DocumentInsightsResponse,
    DocumentTypeCount,
    RecentDocumentItem,
)


@router.get("/usage", response_model=UsageSummaryResponse)
def get_usage_summary(
    start_date: date | None = None,
    end_date: date | None = None,
    provider: str | None = None,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Returns daily aggregates of token usage and request count for the admin's tenant.
    """
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=6)

    # Use appropriate date extraction expression depending on DB dialect (SQLite vs PostgreSQL)
    if db.bind.dialect.name == "sqlite":
        date_expr = func.date(UsageLog.created_at)
    else:
        date_expr = cast(UsageLog.created_at, Date)

    query = db.query(
        date_expr.label("day"),
        func.count(UsageLog.id).label("request_count"),
        func.sum(UsageLog.input_tokens + UsageLog.output_tokens).label("total_tokens"),
        func.sum(
            case((UsageLog.provider == "anthropic", UsageLog.input_tokens), else_=0)
        ).label("claude_input_tokens"),
        func.sum(
            case((UsageLog.provider == "anthropic", UsageLog.output_tokens), else_=0)
        ).label("claude_output_tokens"),
        func.sum(
            case((UsageLog.provider == "openrouter", UsageLog.input_tokens), else_=0)
        ).label("openrouter_input_tokens"),
        func.sum(
            case((UsageLog.provider == "openrouter", UsageLog.output_tokens), else_=0)
        ).label("openrouter_output_tokens"),
        func.sum(
            case(
                (
                    and_(
                        UsageLog.provider == "anthropic",
                        func.lower(UsageLog.model_string).like("%haiku%"),
                    ),
                    UsageLog.input_tokens,
                ),
                else_=0,
            )
        ).label("claude_haiku_input_tokens"),
        func.sum(
            case(
                (
                    and_(
                        UsageLog.provider == "anthropic",
                        func.lower(UsageLog.model_string).like("%haiku%"),
                    ),
                    UsageLog.output_tokens,
                ),
                else_=0,
            )
        ).label("claude_haiku_output_tokens"),
        func.sum(
            case(
                (
                    and_(
                        UsageLog.provider == "anthropic",
                        func.lower(UsageLog.model_string).like("%sonnet%"),
                    ),
                    UsageLog.input_tokens,
                ),
                else_=0,
            )
        ).label("claude_sonnet_input_tokens"),
        func.sum(
            case(
                (
                    and_(
                        UsageLog.provider == "anthropic",
                        func.lower(UsageLog.model_string).like("%sonnet%"),
                    ),
                    UsageLog.output_tokens,
                ),
                else_=0,
            )
        ).label("claude_sonnet_output_tokens"),
        func.sum(
            case(
                (
                    and_(
                        UsageLog.provider == "anthropic",
                        func.lower(UsageLog.model_string).like("%opus%"),
                    ),
                    UsageLog.input_tokens,
                ),
                else_=0,
            )
        ).label("claude_opus_input_tokens"),
        func.sum(
            case(
                (
                    and_(
                        UsageLog.provider == "anthropic",
                        func.lower(UsageLog.model_string).like("%opus%"),
                    ),
                    UsageLog.output_tokens,
                ),
                else_=0,
            )
        ).label("claude_opus_output_tokens"),
        func.sum(
            case(
                (
                    and_(
                        UsageLog.provider == "openrouter",
                        func.lower(UsageLog.model_string).like("%llama%"),
                    ),
                    UsageLog.input_tokens,
                ),
                else_=0,
            )
        ).label("openrouter_llama_input_tokens"),
        func.sum(
            case(
                (
                    and_(
                        UsageLog.provider == "openrouter",
                        func.lower(UsageLog.model_string).like("%llama%"),
                    ),
                    UsageLog.output_tokens,
                ),
                else_=0,
            )
        ).label("openrouter_llama_output_tokens"),
        func.sum(
            case(
                (
                    and_(
                        UsageLog.provider == "openrouter",
                        func.lower(UsageLog.model_string).like("%gemma%"),
                    ),
                    UsageLog.input_tokens,
                ),
                else_=0,
            )
        ).label("openrouter_gemma_input_tokens"),
        func.sum(
            case(
                (
                    and_(
                        UsageLog.provider == "openrouter",
                        func.lower(UsageLog.model_string).like("%gemma%"),
                    ),
                    UsageLog.output_tokens,
                ),
                else_=0,
            )
        ).label("openrouter_gemma_output_tokens"),
        func.sum(
            case(
                (
                    and_(
                        UsageLog.provider == "openrouter",
                        func.lower(UsageLog.model_string).like("%nemotron%"),
                    ),
                    UsageLog.input_tokens,
                ),
                else_=0,
            )
        ).label("openrouter_nemotron_input_tokens"),
        func.sum(
            case(
                (
                    and_(
                        UsageLog.provider == "openrouter",
                        func.lower(UsageLog.model_string).like("%nemotron%"),
                    ),
                    UsageLog.output_tokens,
                ),
                else_=0,
            )
        ).label("openrouter_nemotron_output_tokens"),
        func.sum(
            case(
                (
                    and_(
                        UsageLog.provider == "openrouter",
                        func.lower(UsageLog.model_string).like("%gpt-oss%"),
                    ),
                    UsageLog.input_tokens,
                ),
                else_=0,
            )
        ).label("openrouter_gpt_input_tokens"),
        func.sum(
            case(
                (
                    and_(
                        UsageLog.provider == "openrouter",
                        func.lower(UsageLog.model_string).like("%gpt-oss%"),
                    ),
                    UsageLog.output_tokens,
                ),
                else_=0,
            )
        ).label("openrouter_gpt_output_tokens"),
        func.sum(
            case(
                (
                    and_(
                        UsageLog.provider == "openrouter",
                        func.lower(UsageLog.model_string).like("%cohere%")
                        | func.lower(UsageLog.model_string).like("%north-mini-code%"),
                    ),
                    UsageLog.input_tokens,
                ),
                else_=0,
            )
        ).label("openrouter_cohere_input_tokens"),
        func.sum(
            case(
                (
                    and_(
                        UsageLog.provider == "openrouter",
                        func.lower(UsageLog.model_string).like("%cohere%")
                        | func.lower(UsageLog.model_string).like("%north-mini-code%"),
                    ),
                    UsageLog.output_tokens,
                ),
                else_=0,
            )
        ).label("openrouter_cohere_output_tokens"),
    ).filter(
        UsageLog.tenant_id == current_admin.tenant_id,
        date_expr >= start_date,
        date_expr <= end_date,
    )

    if provider:
        query = query.filter(UsageLog.provider == provider)

    results = query.group_by(date_expr).order_by(date_expr.asc()).all()

    usage_items = []
    for row in results:
        day_val = row.day
        if isinstance(day_val, str):
            day_val = date.fromisoformat(day_val)
        usage_items.append(
            UsageSummaryItem(
                date=day_val,
                request_count=row.request_count,
                total_tokens=int(row.total_tokens)
                if row.total_tokens is not None
                else 0,
                claude_input_tokens=int(row.claude_input_tokens)
                if row.claude_input_tokens is not None
                else 0,
                claude_output_tokens=int(row.claude_output_tokens)
                if row.claude_output_tokens is not None
                else 0,
                openrouter_input_tokens=int(row.openrouter_input_tokens)
                if row.openrouter_input_tokens is not None
                else 0,
                openrouter_output_tokens=int(row.openrouter_output_tokens)
                if row.openrouter_output_tokens is not None
                else 0,
                claude_haiku_input_tokens=int(row.claude_haiku_input_tokens)
                if row.claude_haiku_input_tokens is not None
                else 0,
                claude_haiku_output_tokens=int(row.claude_haiku_output_tokens)
                if row.claude_haiku_output_tokens is not None
                else 0,
                claude_sonnet_input_tokens=int(row.claude_sonnet_input_tokens)
                if row.claude_sonnet_input_tokens is not None
                else 0,
                claude_sonnet_output_tokens=int(row.claude_sonnet_output_tokens)
                if row.claude_sonnet_output_tokens is not None
                else 0,
                claude_opus_input_tokens=int(row.claude_opus_input_tokens)
                if row.claude_opus_input_tokens is not None
                else 0,
                claude_opus_output_tokens=int(row.claude_opus_output_tokens)
                if row.claude_opus_output_tokens is not None
                else 0,
                openrouter_llama_input_tokens=int(row.openrouter_llama_input_tokens)
                if row.openrouter_llama_input_tokens is not None
                else 0,
                openrouter_llama_output_tokens=int(row.openrouter_llama_output_tokens)
                if row.openrouter_llama_output_tokens is not None
                else 0,
                openrouter_gemma_input_tokens=int(row.openrouter_gemma_input_tokens)
                if row.openrouter_gemma_input_tokens is not None
                else 0,
                openrouter_gemma_output_tokens=int(row.openrouter_gemma_output_tokens)
                if row.openrouter_gemma_output_tokens is not None
                else 0,
                openrouter_nemotron_input_tokens=int(
                    row.openrouter_nemotron_input_tokens
                )
                if row.openrouter_nemotron_input_tokens is not None
                else 0,
                openrouter_nemotron_output_tokens=int(
                    row.openrouter_nemotron_output_tokens
                )
                if row.openrouter_nemotron_output_tokens is not None
                else 0,
                openrouter_gpt_input_tokens=int(row.openrouter_gpt_input_tokens)
                if row.openrouter_gpt_input_tokens is not None
                else 0,
                openrouter_gpt_output_tokens=int(row.openrouter_gpt_output_tokens)
                if row.openrouter_gpt_output_tokens is not None
                else 0,
                openrouter_cohere_input_tokens=int(row.openrouter_cohere_input_tokens)
                if row.openrouter_cohere_input_tokens is not None
                else 0,
                openrouter_cohere_output_tokens=int(row.openrouter_cohere_output_tokens)
                if row.openrouter_cohere_output_tokens is not None
                else 0,
            )
        )

    return UsageSummaryResponse(usage=usage_items)


@router.get("/dashboard-overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    current_admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    """
    Returns counts for departments, documents, roles, and members for the admin's tenant.
    """
    department_count = (
        db.query(Department)
        .filter(Department.tenant_id == current_admin.tenant_id)
        .count()
    )
    document_count = (
        db.query(Document).filter(Document.tenant_id == current_admin.tenant_id).count()
    )
    role_count = (
        db.query(Role).filter(Role.tenant_id == current_admin.tenant_id).count()
    )
    member_count = (
        db.query(User).filter(User.tenant_id == current_admin.tenant_id).count()
    )

    return DashboardOverviewResponse(
        department_count=department_count,
        document_count=document_count,
        role_count=role_count,
        member_count=member_count,
    )


@router.get("/document-insights", response_model=DocumentInsightsResponse)
def get_document_insights(
    current_admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    """
    Returns document type distribution and details of the 3 most recently uploaded documents.
    """
    # 1. Distribution
    dist_raw = (
        db.query(Document.file_type, func.count(Document.id).label("count"))
        .filter(Document.tenant_id == current_admin.tenant_id)
        .group_by(Document.file_type)
        .all()
    )

    distribution = [
        DocumentTypeCount(file_type=row.file_type.value, count=row.count)
        for row in dist_raw
    ]

    # 2. Recent documents
    recent_raw = (
        db.query(Document)
        .options(joinedload(Document.uploader))
        .filter(Document.tenant_id == current_admin.tenant_id)
        .order_by(Document.uploaded_at.desc())
        .limit(3)
        .all()
    )

    recent_documents = [
        RecentDocumentItem(
            filename=doc.filename,
            file_type=doc.file_type.value,
            uploaded_by=doc.uploader.full_name if doc.uploader else "Unknown",
            uploaded_at=doc.uploaded_at,
            status=doc.status.value,
        )
        for doc in recent_raw
    ]

    return DocumentInsightsResponse(
        distribution=distribution, recent_documents=recent_documents
    )


@router.get("/audit-log", response_model=AuditLogListResponse)
def get_audit_logs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Returns a paginated list of audit logs for the admin's tenant.
    Can be filtered by action type and date range.
    """
    query = db.query(AuditLog).filter(AuditLog.tenant_id == current_admin.tenant_id)

    if action:
        query = query.filter(AuditLog.action == action)

    if start_date:
        start_dt = datetime.combine(start_date, datetime.min.time())
        query = query.filter(AuditLog.created_at >= start_dt)

    if end_date:
        end_dt = datetime.combine(end_date, datetime.max.time())
        query = query.filter(AuditLog.created_at <= end_dt)

    total = query.count()

    logs = (
        query.options(joinedload(AuditLog.actor))
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        {
            "id": log.id,
            "tenant_id": log.tenant_id,
            "actor_user_id": log.actor_user_id,
            "actor_name": log.actor.full_name if log.actor else "System",
            "action": log.action,
            "description": log.description,
            "metadata": log.metadata_,
            "created_at": log.created_at,
        }
        for log in logs
    ]

    return {"items": items, "total": total, "limit": limit, "offset": offset}

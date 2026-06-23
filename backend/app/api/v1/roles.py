import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.user import User
from app.models.role import Role
from app.schemas.role import CreateRoleRequest, UpdateRoleRequest, RoleResponse
from app.services.role_service import check_role_cycle

router = APIRouter()

@router.get("", response_model=list[RoleResponse])
def get_roles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Protected route to get all roles belonging to the current user's tenant."""
    roles = db.query(Role).filter(Role.tenant_id == current_user.tenant_id).all()
    return roles

def _validate_parent_role(
    parent_role_id: uuid.UUID | None,
    tenant_id: uuid.UUID,
    db: Session,
) -> None:
    """Validate that the parent role exists and belongs to the same tenant."""
    if parent_role_id is not None:
        parent_role = db.query(Role).filter(
            Role.id == parent_role_id,
            Role.tenant_id == tenant_id
        ).first()
        if not parent_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent role not found in this organisation"
            )

def _validate_department(
    department_id: uuid.UUID | None,
    tenant_id: uuid.UUID,
    db: Session,
) -> None:
    """Validate that the department exists and belongs to the same tenant."""
    if department_id is not None:
        from app.models.department import Department
        dept = db.query(Department).filter(
            Department.id == department_id,
            Department.tenant_id == tenant_id
        ).first()
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department not found in this organisation"
            )

@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    request: CreateRoleRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Protected route (admin only) to create a custom role."""
    existing_role = db.query(Role).filter(
        Role.tenant_id == current_admin.tenant_id,
        Role.name == request.name
    ).first()
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A role with this name already exists"
        )

    # Validate parent_role_id and department_id if provided
    _validate_parent_role(request.parent_role_id, current_admin.tenant_id, db)
    _validate_department(request.department_id, current_admin.tenant_id, db)

    new_role = Role(
        tenant_id=current_admin.tenant_id,
        name=request.name,
        is_admin=False,
        is_default=False,
        parent_role_id=request.parent_role_id,
        department_id=request.department_id,
    )
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    return new_role

@router.patch("/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: uuid.UUID,
    request: UpdateRoleRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Protected route (admin only) to update a role's name and parent."""
    role = db.query(Role).filter(
        Role.id == role_id,
        Role.tenant_id == current_admin.tenant_id
    ).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    # Check uniqueness of the new name
    duplicate_role = db.query(Role).filter(
        Role.tenant_id == current_admin.tenant_id,
        Role.name == request.name,
        Role.id != role_id
    ).first()
    if duplicate_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A role with this name already exists"
        )

    # Validate parent_role_id and department_id if provided
    _validate_parent_role(request.parent_role_id, current_admin.tenant_id, db)
    _validate_department(request.department_id, current_admin.tenant_id, db)

    if request.parent_role_id is not None:
        # Cycle detection: reject if the role being edited appears in the
        # proposed parent's ancestor chain.
        if check_role_cycle(role_id, request.parent_role_id, db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot set this parent role — it would create a circular hierarchy"
            )

    role.name = request.name
    role.parent_role_id = request.parent_role_id
    role.department_id = request.department_id
    db.commit()
    db.refresh(role)
    return role

@router.delete("/{role_id}")
def delete_role(
    role_id: uuid.UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Protected route (admin only) to delete a custom role."""
    role = db.query(Role).filter(
        Role.id == role_id,
        Role.tenant_id == current_admin.tenant_id
    ).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    if role.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Default roles cannot be deleted"
        )

    # Check if any users are assigned this role
    user_exists = db.query(User).filter(User.role_id == role_id).first()
    if user_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a role that has users assigned to it. Please reassign those users first."
        )

    db.delete(role)
    db.commit()
    return {"message": "Role deleted successfully"}


import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.user import User
from app.models.department import Department
from app.schemas.department import (
    CreateDepartmentRequest,
    UpdateDepartmentRequest,
    DepartmentResponse,
)
from app.services.audit_log_service import log_audit_event

router = APIRouter()


@router.get("", response_model=list[DepartmentResponse])
def get_departments(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get all departments for the current user's organisation."""
    departments = (
        db.query(Department)
        .filter(Department.tenant_id == current_user.tenant_id)
        .all()
    )
    return departments


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    request: CreateDepartmentRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new department in the admin's organisation."""
    existing = (
        db.query(Department)
        .filter(
            Department.tenant_id == current_admin.tenant_id,
            Department.name == request.name,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A department with this name already exists",
        )

    dept = Department(tenant_id=current_admin.tenant_id, name=request.name)
    db.add(dept)
    db.commit()
    db.refresh(dept)

    log_audit_event(
        db=db,
        tenant_id=current_admin.tenant_id,
        actor_user_id=current_admin.id,
        action="department.created",
        description=f"Created department '{dept.name}'",
        metadata={"department_id": str(dept.id), "name": dept.name},
    )

    return dept


@router.patch("/{department_id}", response_model=DepartmentResponse)
def update_department(
    department_id: uuid.UUID,
    request: UpdateDepartmentRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a department's name in the admin's organisation."""
    dept = (
        db.query(Department)
        .filter(
            Department.id == department_id,
            Department.tenant_id == current_admin.tenant_id,
        )
        .first()
    )
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
        )

    existing = (
        db.query(Department)
        .filter(
            Department.tenant_id == current_admin.tenant_id,
            Department.name == request.name,
            Department.id != department_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A department with this name already exists",
        )

    old_name = dept.name
    dept.name = request.name
    db.commit()
    db.refresh(dept)

    log_audit_event(
        db=db,
        tenant_id=current_admin.tenant_id,
        actor_user_id=current_admin.id,
        action="department.updated",
        description=f"Updated department name from '{old_name}' to '{dept.name}'",
        metadata={
            "department_id": str(dept.id),
            "old_name": old_name,
            "new_name": dept.name,
        },
    )

    return dept


@router.delete("/{department_id}")
def delete_department(
    department_id: uuid.UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a department from the admin's organisation."""
    dept = (
        db.query(Department)
        .filter(
            Department.id == department_id,
            Department.tenant_id == current_admin.tenant_id,
        )
        .first()
    )
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
        )

    db.delete(dept)
    db.commit()
    return {"message": "Department deleted successfully"}

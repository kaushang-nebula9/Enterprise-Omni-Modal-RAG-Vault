import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.user import User
from app.models.role import Role
from app.schemas.role import (
    CreateRoleRequest,
    UpdateRoleRequest,
    RoleResponse,
    RoleTreeNode,
)
from app.services.role_service import check_role_cycle
from app.services.audit_log_service import log_audit_event

router = APIRouter()


@router.get("", response_model=list[RoleResponse])
def get_roles(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Protected route to get all roles belonging to the current user's tenant."""
    roles = db.query(Role).filter(Role.tenant_id == current_user.tenant_id).all()
    return roles


@router.get("/tree", response_model=list[RoleTreeNode])
def get_roles_tree(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Return all roles for the tenant as a nested tree structure.

    Each root-level node is a role with no parent (or an orphaned role whose
    parent no longer exists in this tenant). Each node includes:
      - id, name, parent_role_id, is_admin, is_default
      - descendant_count: total number of roles anywhere below it in the tree
      - children: direct child roles (recursively nested)
    """
    all_roles = db.query(Role).filter(Role.tenant_id == current_user.tenant_id).all()

    # Build a lookup by id for fast access
    role_by_id: dict[uuid.UUID, Role] = {r.id: r for r in all_roles}
    valid_ids: set[uuid.UUID] = set(role_by_id.keys())

    # descendant_count[role_id] accumulates as we walk up each role's ancestor chain
    descendant_count: dict[uuid.UUID, int] = {r.id: 0 for r in all_roles}

    for role in all_roles:
        # Walk up from this role to the root, incrementing each ancestor's count
        visited: set[uuid.UUID] = set()
        current_id: uuid.UUID | None = role.parent_role_id
        depth = 0
        while current_id is not None and depth < 50:
            if current_id not in valid_ids:
                break  # orphan edge – stop here
            if current_id in visited:
                break  # cycle guard
            visited.add(current_id)
            descendant_count[current_id] += 1
            parent_role = role_by_id[current_id]
            current_id = parent_role.parent_role_id
            depth += 1

    # Build the tree: collect direct children for each role
    children_map: dict[uuid.UUID, list[RoleTreeNode]] = {r.id: [] for r in all_roles}

    # Determine which roles are effective roots:
    # - roles with no parent_role_id, OR
    # - roles whose parent_role_id points to a role outside this tenant (orphan)
    root_nodes: list[RoleTreeNode] = []

    def build_node(role: Role) -> RoleTreeNode:
        return RoleTreeNode(
            id=role.id,
            name=role.name,
            parent_role_id=role.parent_role_id,
            is_admin=role.is_admin,
            is_default=role.is_default,
            descendant_count=descendant_count[role.id],
            children=children_map[role.id],
        )

    # Two-pass: first create all nodes, then attach children
    nodes: dict[uuid.UUID, RoleTreeNode] = {r.id: build_node(r) for r in all_roles}

    for role in all_roles:
        parent_id = role.parent_role_id
        if parent_id is None or parent_id not in valid_ids:
            # True root or orphan — treat as root
            root_nodes.append(nodes[role.id])
        else:
            nodes[parent_id].children.append(nodes[role.id])

    return root_nodes


def _validate_parent_role(
    parent_role_id: uuid.UUID | None,
    tenant_id: uuid.UUID,
    db: Session,
) -> None:
    """Validate that the parent role exists and belongs to the same tenant."""
    if parent_role_id is not None:
        parent_role = (
            db.query(Role)
            .filter(Role.id == parent_role_id, Role.tenant_id == tenant_id)
            .first()
        )
        if not parent_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent role not found in this organisation",
            )


def _validate_department(
    department_id: uuid.UUID | None,
    tenant_id: uuid.UUID,
    db: Session,
) -> None:
    """Validate that the department exists and belongs to the same tenant."""
    if department_id is not None:
        from app.models.department import Department

        dept = (
            db.query(Department)
            .filter(Department.id == department_id, Department.tenant_id == tenant_id)
            .first()
        )
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department not found in this organisation",
            )


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    request: CreateRoleRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Protected route (admin only) to create a custom role."""
    existing_role = (
        db.query(Role)
        .filter(Role.tenant_id == current_admin.tenant_id, Role.name == request.name)
        .first()
    )
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A role with this name already exists",
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

    log_audit_event(
        db=db,
        tenant_id=current_admin.tenant_id,
        actor_user_id=current_admin.id,
        action="role.created",
        description=f"Created role '{new_role.name}'",
        metadata={
            "role_id": str(new_role.id),
            "name": new_role.name,
            "parent_role_id": str(new_role.parent_role_id)
            if new_role.parent_role_id
            else None,
        },
    )

    return new_role


@router.patch("/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: uuid.UUID,
    request: UpdateRoleRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Protected route (admin only) to update a role's name and parent."""
    role = (
        db.query(Role)
        .filter(Role.id == role_id, Role.tenant_id == current_admin.tenant_id)
        .first()
    )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )

    # Check uniqueness of the new name
    duplicate_role = (
        db.query(Role)
        .filter(
            Role.tenant_id == current_admin.tenant_id,
            Role.name == request.name,
            Role.id != role_id,
        )
        .first()
    )
    if duplicate_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A role with this name already exists",
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
                detail="Cannot set this parent role — it would create a circular hierarchy",
            )

    # Track department changes
    old_dept_id = role.department_id
    dept_changed = (
        request.department_id is not None and request.department_id != old_dept_id
    )

    # Track parent changes
    old_parent_id = role.parent_role_id
    parent_changed = old_parent_id != request.parent_role_id
    old_name = role.name

    role.name = request.name
    role.parent_role_id = request.parent_role_id
    role.department_id = request.department_id
    db.commit()

    if parent_changed:
        old_parent_name = "None"
        if old_parent_id:
            old_parent = db.query(Role).filter(Role.id == old_parent_id).first()
            if old_parent:
                old_parent_name = old_parent.name
        new_parent_name = "None"
        if role.parent_role_id:
            new_parent = db.query(Role).filter(Role.id == role.parent_role_id).first()
            if new_parent:
                new_parent_name = new_parent.name

        log_audit_event(
            db=db,
            tenant_id=current_admin.tenant_id,
            actor_user_id=current_admin.id,
            action="role.parent_changed",
            description=f"Changed parent of role '{role.name}' from '{old_parent_name}' to '{new_parent_name}'",
            metadata={
                "role_id": str(role.id),
                "name": role.name,
                "old_parent_role_id": str(old_parent_id) if old_parent_id else None,
                "new_parent_role_id": str(role.parent_role_id)
                if role.parent_role_id
                else None,
                "old_parent_name": old_parent_name,
                "new_parent_name": new_parent_name,
            },
        )
    else:
        log_audit_event(
            db=db,
            tenant_id=current_admin.tenant_id,
            actor_user_id=current_admin.id,
            action="role.updated",
            description=f"Updated role '{role.name}'",
            metadata={
                "role_id": str(role.id),
                "old_name": old_name,
                "new_name": role.name,
                "old_department_id": str(old_dept_id) if old_dept_id else None,
                "new_department_id": str(role.department_id)
                if role.department_id
                else None,
            },
        )

    if dept_changed and request.department_id:
        from app.models.department import Department
        from app.services.notification_service import create_notification
        from app.models.enums import NotificationType

        dept = (
            db.query(Department).filter(Department.id == request.department_id).first()
        )
        dept_name = dept.name if dept else "unknown department"

        role_users = db.query(User).filter(User.role_id == role.id).all()
        for u in role_users:
            create_notification(
                db=db,
                user_id=u.id,
                tenant_id=u.tenant_id,
                type=NotificationType.department_added,
                message=f"Your role '{role.name}' has been added to department: {dept_name}",
                related_role_id=role.id,
                related_department_id=request.department_id,
            )

    db.refresh(role)
    return role


@router.delete("/{role_id}")
def delete_role(
    role_id: uuid.UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Protected route (admin only) to delete a custom role."""
    role = (
        db.query(Role)
        .filter(Role.id == role_id, Role.tenant_id == current_admin.tenant_id)
        .first()
    )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )

    if role.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Default roles cannot be deleted",
        )

    # Check if any users are assigned this role
    user_exists = db.query(User).filter(User.role_id == role_id).first()
    if user_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a role that has users assigned to it. Please reassign those users first.",
        )

    role_name = role.name
    role_id = role.id

    db.delete(role)
    db.commit()

    log_audit_event(
        db=db,
        tenant_id=current_admin.tenant_id,
        actor_user_id=current_admin.id,
        action="role.deleted",
        description=f"Deleted role '{role_name}'",
        metadata={"role_id": str(role_id), "name": role_name},
    )

    return {"message": "Role deleted successfully"}

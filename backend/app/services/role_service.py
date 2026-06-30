"""
Role hierarchy service — ancestor traversal and cycle detection.
"""

import uuid
from sqlalchemy.orm import Session
from app.models.role import Role

MAX_HIERARCHY_DEPTH = 50


def get_role_ancestors(role_id: uuid.UUID, db: Session) -> list[Role]:
    """
    Walk up the role hierarchy via parent_role_id and return all ancestor roles
    (parent, grandparent, etc.) up to the root.

    A max-depth safety limit prevents infinite loops in case of data corruption.
    """
    ancestors: list[Role] = []
    visited: set[uuid.UUID] = {role_id}
    current_role = db.query(Role).filter(Role.id == role_id).first()

    if not current_role or current_role.parent_role_id is None:
        return ancestors

    next_parent_id = current_role.parent_role_id

    for _ in range(MAX_HIERARCHY_DEPTH):
        if next_parent_id is None:
            break

        if next_parent_id in visited:
            # Data corruption: cycle detected — stop traversal
            break

        parent = db.query(Role).filter(Role.id == next_parent_id).first()
        if parent is None:
            break

        ancestors.append(parent)
        visited.add(parent.id)
        next_parent_id = parent.parent_role_id

    return ancestors


def check_role_cycle(
    role_id: uuid.UUID,
    proposed_parent_id: uuid.UUID | None,
    db: Session,
) -> bool:
    """
    Return True if setting role_id's parent to proposed_parent_id would create
    a cycle in the hierarchy.

    The check walks up from proposed_parent_id. If it encounters role_id
    anywhere in the ancestor chain, a cycle would be formed.
    """
    if proposed_parent_id is None:
        return False

    if proposed_parent_id == role_id:
        return True

    visited: set[uuid.UUID] = set()
    current_id: uuid.UUID | None = proposed_parent_id

    for _ in range(MAX_HIERARCHY_DEPTH):
        if current_id is None:
            break

        if current_id in visited:
            # Already a cycle in the data — report True to be safe
            return True

        if current_id == role_id:
            return True

        visited.add(current_id)
        parent = db.query(Role).filter(Role.id == current_id).first()
        if parent is None:
            break
        current_id = parent.parent_role_id

    return False

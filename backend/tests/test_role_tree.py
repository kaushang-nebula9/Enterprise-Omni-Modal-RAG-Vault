"""
Pure-logic unit tests for the role hierarchy tree building algorithm.

These tests replicate the algorithm from GET /api/v1/roles/tree but operate
on plain dataclasses so they need no DB, no SQLAlchemy, no Celery, and run
in any environment.

Tests cover:
  - Flat list: all roots, zero descendant counts
  - Linear chain: correct descendant counts per level
  - Branching: correct counts across multiple subtrees
  - Orphaned role: surfaces as a root node
  - Cycle guard: does not infinite-loop
  - Tenant isolation: only same-tenant roles included
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uuid
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Minimal in-memory role representation (mirrors app.models.role.Role fields)
# ---------------------------------------------------------------------------

@dataclass
class FakeRole:
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    parent_role_id: Optional[uuid.UUID] = None
    is_admin: bool = False
    is_default: bool = False


# ---------------------------------------------------------------------------
# Algorithm under test (copied verbatim from app/api/v1/roles.py get_roles_tree)
# ---------------------------------------------------------------------------

def build_tree(all_roles: list[FakeRole]):
    """
    Returns (descendant_count, children_map, root_ids).

      descendant_count : dict[uuid.UUID, int]
      children_map     : dict[uuid.UUID, list[uuid.UUID]]
      root_ids         : list[uuid.UUID]   (order is insertion-stable)
    """
    role_by_id: dict[uuid.UUID, FakeRole] = {r.id: r for r in all_roles}
    valid_ids: set[uuid.UUID] = set(role_by_id.keys())

    # Walk up each role's ancestor chain, incrementing each ancestor's count
    descendant_count: dict[uuid.UUID, int] = {r.id: 0 for r in all_roles}

    for role in all_roles:
        visited: set[uuid.UUID] = set()
        current_id = role.parent_role_id
        depth = 0
        while current_id is not None and depth < 50:
            if current_id not in valid_ids:
                break  # orphan edge
            if current_id in visited:
                break  # cycle guard
            visited.add(current_id)
            descendant_count[current_id] += 1
            current_id = role_by_id[current_id].parent_role_id
            depth += 1

    children_map: dict[uuid.UUID, list[uuid.UUID]] = {r.id: [] for r in all_roles}
    root_ids: list[uuid.UUID] = []

    for role in all_roles:
        parent_id = role.parent_role_id
        if parent_id is None or parent_id not in valid_ids:
            root_ids.append(role.id)
        else:
            children_map[parent_id].append(role.id)

    return descendant_count, children_map, root_ids


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_role(tenant_id, name, parent_id=None) -> FakeRole:
    return FakeRole(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        parent_role_id=parent_id,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_flat_list_no_parents():
    """Three unrelated roles → all are roots with descendant_count 0."""
    tid = uuid.uuid4()
    r1 = make_role(tid, "Alpha")
    r2 = make_role(tid, "Beta")
    r3 = make_role(tid, "Gamma")

    dcnt, children_map, root_ids = build_tree([r1, r2, r3])

    assert set(root_ids) == {r1.id, r2.id, r3.id}
    assert dcnt[r1.id] == 0
    assert dcnt[r2.id] == 0
    assert dcnt[r3.id] == 0
    assert children_map[r1.id] == []


def test_linear_chain_descendant_counts():
    """CEO → VP → Manager → Developer: counts should be 3, 2, 1, 0."""
    tid = uuid.uuid4()
    ceo = make_role(tid, "CEO")
    vp = make_role(tid, "VP", parent_id=ceo.id)
    mgr = make_role(tid, "Manager", parent_id=vp.id)
    dev = make_role(tid, "Developer", parent_id=mgr.id)

    dcnt, children_map, root_ids = build_tree([ceo, vp, mgr, dev])

    assert root_ids == [ceo.id]
    assert dcnt[ceo.id] == 3
    assert dcnt[vp.id] == 2
    assert dcnt[mgr.id] == 1
    assert dcnt[dev.id] == 0
    assert children_map[ceo.id] == [vp.id]
    assert children_map[vp.id] == [mgr.id]
    assert children_map[mgr.id] == [dev.id]


def test_branching_descendant_counts():
    """CEO has two VP children, each with one leaf child → CEO has 4 descendants."""
    tid = uuid.uuid4()
    ceo = make_role(tid, "CEO")
    vp_e = make_role(tid, "VP-Eng", parent_id=ceo.id)
    vp_s = make_role(tid, "VP-Sales", parent_id=ceo.id)
    eng = make_role(tid, "Engineer", parent_id=vp_e.id)
    sales = make_role(tid, "Salesperson", parent_id=vp_s.id)

    dcnt, children_map, root_ids = build_tree([ceo, vp_e, vp_s, eng, sales])

    assert root_ids == [ceo.id]
    assert dcnt[ceo.id] == 4
    assert dcnt[vp_e.id] == 1
    assert dcnt[vp_s.id] == 1
    assert dcnt[eng.id] == 0
    assert dcnt[sales.id] == 0
    assert set(children_map[ceo.id]) == {vp_e.id, vp_s.id}


def test_orphaned_role_becomes_root():
    """A role whose parent_role_id is not in the tenant appears as a root node."""
    tid = uuid.uuid4()
    ghost_id = uuid.uuid4()  # never inserted
    orphan = FakeRole(id=uuid.uuid4(), tenant_id=tid, name="Orphan", parent_role_id=ghost_id)
    real_root = make_role(tid, "RealRoot")

    dcnt, children_map, root_ids = build_tree([orphan, real_root])

    assert orphan.id in root_ids
    assert real_root.id in root_ids
    assert dcnt[orphan.id] == 0
    # orphan is not a child of anything
    assert orphan.id not in children_map[real_root.id]


def test_cycle_guard_does_not_infinite_loop():
    """An artificial cycle (A → B → A) must not cause an infinite loop."""
    tid = uuid.uuid4()
    role_a = FakeRole(id=uuid.uuid4(), tenant_id=tid, name="A", parent_role_id=None)
    role_b = FakeRole(id=uuid.uuid4(), tenant_id=tid, name="B", parent_role_id=role_a.id)
    # Force cycle: A's parent is now B
    role_a.parent_role_id = role_b.id

    dcnt, _, _ = build_tree([role_a, role_b])

    # All counts must be finite (bounded by depth=50)
    assert all(v <= 50 for v in dcnt.values())


def test_single_role_is_root_with_zero_descendants():
    """A single role is its own root with descendant_count == 0."""
    tid = uuid.uuid4()
    solo = make_role(tid, "Solo")

    dcnt, children_map, root_ids = build_tree([solo])

    assert root_ids == [solo.id]
    assert dcnt[solo.id] == 0
    assert children_map[solo.id] == []


def test_tenant_isolation_different_roles():
    """
    build_tree only operates on the list it receives.
    If called with only tenant A's roles, tenant B's roles never appear.
    """
    tid_a = uuid.uuid4()
    tid_b = uuid.uuid4()
    r_a = make_role(tid_a, "RoleA")
    r_b = make_role(tid_b, "RoleB")

    # Simulate the DB filter: each call only gets its own tenant's roles
    _, _, root_ids_a = build_tree([r_a])
    _, _, root_ids_b = build_tree([r_b])

    assert root_ids_a == [r_a.id]
    assert root_ids_b == [r_b.id]
    assert r_b.id not in root_ids_a
    assert r_a.id not in root_ids_b

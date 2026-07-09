import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.external_database import DatabaseAccessPolicy
from app.services.database_service import (
    get_user_authorized_columns_for_table,
    check_sql_authorized_columns,
)


def test_get_user_authorized_columns_for_table():
    # 1. Full DB scope, no column restrictions
    p1 = DatabaseAccessPolicy(table_name=None, columns=None)
    cols = get_user_authorized_columns_for_table([p1], "users", ["id", "name", "email"])
    assert cols == {"id", "name", "email"}

    # 2. Full DB scope with column restrictions
    p2 = DatabaseAccessPolicy(
        table_name=None, columns=["users.id", "users.email", "posts.title"]
    )
    cols = get_user_authorized_columns_for_table([p2], "users", ["id", "name", "email"])
    assert cols == {"id", "email"}

    # 3. Table specific scope, no column restrictions
    p3 = DatabaseAccessPolicy(table_name="users", columns=None)
    cols = get_user_authorized_columns_for_table([p3], "users", ["id", "name", "email"])
    assert cols == {"id", "name", "email"}

    # 4. Table specific scope with column restrictions
    p4 = DatabaseAccessPolicy(table_name="users", columns=["id", "email"])
    cols = get_user_authorized_columns_for_table([p4], "users", ["id", "name", "email"])
    assert cols == {"id", "email"}

    # 5. Multiple policies (union)
    p5 = DatabaseAccessPolicy(table_name="users", columns=["id"])
    p6 = DatabaseAccessPolicy(table_name="users", columns=["email"])
    cols = get_user_authorized_columns_for_table(
        [p5, p6], "users", ["id", "name", "email"]
    )
    assert cols == {"id", "email"}

    # 6. No matching policies
    cols = get_user_authorized_columns_for_table([], "users", ["id", "name"])
    assert cols == set()


def test_check_sql_authorized_columns_success():
    authorized_cols = {
        "users": {"id", "email", "name"},
        "posts": {"id", "title", "user_id"},
    }
    valid_tables = {"users", "posts"}

    # Simple SELECT
    check_sql_authorized_columns(
        "SELECT id, email FROM users",
        "postgresql",
        authorized_cols,
        valid_tables,
    )

    # Qualified SELECT with alias
    check_sql_authorized_columns(
        "SELECT u.id, p.title FROM users u JOIN posts p ON u.id = p.user_id",
        "postgresql",
        authorized_cols,
        valid_tables,
    )

    # Case-insensitive checks
    check_sql_authorized_columns(
        "select ID, Email from USERS",
        "postgresql",
        authorized_cols,
        valid_tables,
    )


def test_check_sql_authorized_columns_failures():
    authorized_cols = {
        "users": {"id", "email"},
        "posts": {"id", "title"},
    }
    valid_tables = {"users", "posts"}

    # Unauthorized column select
    with pytest.raises(
        ValueError, match="Column 'password' on table 'users' is unauthorized"
    ):
        check_sql_authorized_columns(
            "SELECT id, password FROM users",
            "postgresql",
            authorized_cols,
            valid_tables,
        )

    # Unauthorized column in join/where
    with pytest.raises(
        ValueError, match="Column 'secret' on table 'posts' is unauthorized"
    ):
        check_sql_authorized_columns(
            "SELECT u.id FROM users u JOIN posts p ON u.id = p.id WHERE p.secret = '123'",
            "postgresql",
            authorized_cols,
            valid_tables,
        )

    # Unauthorized table access
    with pytest.raises(ValueError, match="Table 'secrets' is unauthorized"):
        check_sql_authorized_columns(
            "SELECT * FROM secrets",
            "postgresql",
            authorized_cols,
            valid_tables,
        )

import base64
import logging
import uuid
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.external_database import (
    ExternalDatabaseConnection,
    DatabaseAccessPolicy,
)
from app.models.user import User
from app.models.enums import DatabaseEngine
from app.models.available_model import AvailableModel
from anthropic import AsyncAnthropic
from app.services.openrouter_service import stream_openrouter_completion

logger = logging.getLogger(__name__)


# --- Model ---
_async_anthropic_client: AsyncAnthropic | None = None


def _get_async_anthropic_client() -> AsyncAnthropic:
    """Lazily initialise and return the AsyncAnthropic client."""
    global _async_anthropic_client
    if _async_anthropic_client is None:
        _async_anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _async_anthropic_client


# --- Encryption Helpers ---


def _get_encryption_key() -> bytes:
    """
    Get or derive the 32-byte URL-safe base64 encryption key.
    """
    if settings.DATABASE_ENCRYPTION_KEY:
        try:
            # Check if it's already a valid Fernet key
            key = settings.DATABASE_ENCRYPTION_KEY.encode()
            Fernet(key)
            return key
        except Exception:
            pass

    # Derive key from SECRET_KEY
    salt = b"rag_vault_salt_db_enc"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    derived = kdf.derive(settings.SECRET_KEY.encode())
    return base64.urlsafe_b64encode(derived)


def encrypt_password(password: str) -> str:
    """
    Encrypt a plaintext password using Fernet symmetric encryption.
    """
    key = _get_encryption_key()
    fernet = Fernet(key)
    return fernet.encrypt(password.encode()).decode()


def decrypt_password(encrypted_password: str) -> str:
    """
    Decrypt an encrypted password using Fernet symmetric encryption.
    """
    key = _get_encryption_key()
    fernet = Fernet(key)
    return fernet.decrypt(encrypted_password.encode()).decode()


# --- Connection Helpers ---


def get_connection_url(
    engine_type: str,
    host: str,
    port: int,
    database_name: str,
    username: str,
    password_decrypted: str,
    ssl_mode: Optional[str] = None,
) -> str:
    """
    Constructs the SQLAlchemy connection URL based on engine and parameters.
    """
    from urllib.parse import quote_plus

    pwd_escaped = quote_plus(password_decrypted)
    user_escaped = quote_plus(username)
    host_escaped = quote_plus(host)
    db_escaped = quote_plus(database_name)

    if engine_type == DatabaseEngine.postgresql:
        ssl_part = f"?sslmode={ssl_mode}" if ssl_mode else ""
        return f"postgresql://{user_escaped}:{pwd_escaped}@{host_escaped}:{port}/{db_escaped}{ssl_part}"
    elif engine_type == DatabaseEngine.mysql:
        # SSL mode mappings for PyMySQL
        ssl_part = ""
        if ssl_mode:
            if ssl_mode.lower() in ("require", "required"):
                ssl_part = "?ssl=true"
            elif ssl_mode.lower() in ("verify-ca", "verify-full"):
                ssl_part = "?ssl_verify_cert=true"
        return f"mysql+pymysql://{user_escaped}:{pwd_escaped}@{host_escaped}:{port}/{db_escaped}{ssl_part}"
    else:
        raise ValueError(f"Unsupported database engine: {engine_type}")


def test_connection_live(
    engine_type: str,
    host: str,
    port: int,
    database_name: str,
    username: str,
    password_decrypted: str,
    ssl_mode: Optional[str] = None,
) -> None:
    """
    Tests reachability and credentials by running a live connection and selecting 1.
    """
    url = get_connection_url(
        engine_type=engine_type,
        host=host,
        port=port,
        database_name=database_name,
        username=username,
        password_decrypted=password_decrypted,
        ssl_mode=ssl_mode,
    )

    # Fast timeouts for interactive testing
    connect_args = {}
    if engine_type == DatabaseEngine.postgresql:
        connect_args = {"connect_timeout": 5}
    elif engine_type == DatabaseEngine.mysql:
        connect_args = {"connect_timeout": 5}

    engine = create_engine(url, connect_args=connect_args)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    finally:
        engine.dispose()


# --- Introspection Helpers ---


def introspect_schema_live(
    engine_type: str,
    host: str,
    port: int,
    database_name: str,
    username: str,
    password_decrypted: str,
    ssl_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Connects to the database and reflects its schema.
    Returns:
        Dict representation of tables, columns, PKs, and FKs.
    """

    print("=" * 80)
    print("[START] Starting schema introspection")
    print(f"[INFO] Engine      : {engine_type}")
    print(f"[INFO] Host        : {host}")
    print(f"[INFO] Port        : {port}")
    print(f"[INFO] Database    : {database_name}")
    print(f"[INFO] Username    : {username}")
    print(f"[INFO] SSL Mode    : {ssl_mode}")

    print("[STEP] Building connection URL...")
    url = get_connection_url(
        engine_type=engine_type,
        host=host,
        port=port,
        database_name=database_name,
        username=username,
        password_decrypted=password_decrypted,
        ssl_mode=ssl_mode,
    )
    print("[SUCCESS] Connection URL built.")

    print("[STEP] Creating SQLAlchemy engine...")
    engine = create_engine(url)
    print("[SUCCESS] Engine created.")

    try:
        print("[STEP] Creating inspector...")
        inspector = inspect(engine)
        print("[SUCCESS] Inspector created.")

        schema_data = {"tables": []}

        print("[STEP] Detecting default schema...")
        default_schema = inspector.default_schema_name
        schemas = [default_schema] if default_schema else [None]
        print(f"[INFO] Schemas to inspect: {schemas}")

        for schema in schemas:
            print(f"\n{'-' * 60}")
            print(f"[STEP] Inspecting schema: {schema}")

            try:
                table_names = inspector.get_table_names(schema=schema)
                print(f"[SUCCESS] Found {len(table_names)} tables.")
                print(f"[TABLES] {table_names}")
            except Exception as e:
                print(f"[ERROR] Failed to fetch tables for schema '{schema}'")
                print(e)
                raise

            for table_name in table_names:
                print(f"\n[STEP] Processing table: {table_name}")

                # Columns
                try:
                    print("  [STEP] Fetching columns...")
                    columns = inspector.get_columns(table_name, schema=schema)
                    print(f"  [SUCCESS] Retrieved {len(columns)} columns.")
                except Exception as e:
                    print(f"  [ERROR] Failed fetching columns for table '{table_name}'")
                    print(e)
                    raise

                columns_info = []
                for col in columns:
                    print(f"    [COLUMN] {col['name']} ({col['type']})")
                    columns_info.append(
                        {
                            "name": col["name"],
                            "type": str(col["type"]),
                            "nullable": col.get("nullable", True),
                        }
                    )

                # Primary Key
                try:
                    print("  [STEP] Fetching primary key...")

                    pk_constraint = inspector.get_pk_constraint(
                        table_name, schema=schema
                    )

                    pk = pk_constraint.get("constrained_columns", [])

                    print(f"  [SUCCESS] Primary Key: {pk}")

                except Exception as e:
                    print(f"  [ERROR] Failed fetching primary key for '{table_name}'")
                    print(e)
                    raise

                # Foreign Keys
                try:
                    print("  [STEP] Fetching foreign keys...")
                    fks = inspector.get_foreign_keys(table_name, schema=schema)
                    print(f"  [SUCCESS] Found {len(fks)} foreign keys.")
                except Exception as e:
                    print(f"  [ERROR] Failed fetching foreign keys for '{table_name}'")
                    print(e)
                    raise

                fks_info = []
                for fk in fks:
                    print(
                        f"    [FK] {fk['constrained_columns']} -> "
                        f"{fk['referred_table']}.{fk['referred_columns']}"
                    )
                    fks_info.append(
                        {
                            "constrained_columns": fk["constrained_columns"],
                            "referred_table": fk["referred_table"],
                            "referred_columns": fk["referred_columns"],
                        }
                    )

                    schema_data["tables"].append(
                        {
                            "schema": schema,
                            "name": table_name,
                            "columns": columns_info,
                            "primary_key": pk,
                            "foreign_keys": fks_info,
                        }
                    )

                print(f"[SUCCESS] Finished processing table: {table_name}")

        print("=" * 80)
        print("[DONE] Schema introspection complete.")
        print(f"[INFO] Total tables processed: {len(schema_data['tables'])}")

        return schema_data

    except Exception as e:
        print("=" * 80)
        print("[FATAL] Schema introspection failed!")
        print(type(e).__name__)
        print(str(e))
        raise

    finally:
        print("[STEP] Disposing SQLAlchemy engine...")
        engine.dispose()
        print("[DONE] Engine disposed.")


# --- Access Policy Utilities ---


def check_user_db_access(db: Session, user: User, connection_id: uuid.UUID) -> bool:
    """
    Returns True if user has access to at least some parts of the database.
    """
    if user.role.is_admin:
        return True

    policy_count = (
        db.query(DatabaseAccessPolicy)
        .filter(
            DatabaseAccessPolicy.connection_id == connection_id,
            DatabaseAccessPolicy.role_id == user.role_id,
        )
        .count()
    )
    return policy_count > 0


def get_user_authorized_tables(
    db: Session, user: User, connection_id: uuid.UUID, all_tables: List[str]
) -> List[str]:
    """
    Returns a list of table names the user is authorized to query.
    If the user has database-level access (table_name IS NULL), they can access all tables.
    Otherwise, access is unioned across all matching policies.
    """
    if user.role.is_admin:
        return all_tables

    policies = (
        db.query(DatabaseAccessPolicy)
        .filter(
            DatabaseAccessPolicy.connection_id == connection_id,
            DatabaseAccessPolicy.role_id == user.role_id,
        )
        .all()
    )

    authorized_tables = set()
    for policy in policies:
        if policy.table_name is None:
            # Grant for entire database
            return all_tables
        authorized_tables.add(policy.table_name)

    return list(authorized_tables)


def _recalculate_policy_inheritance(
    db: Session,
    connection_id: uuid.UUID,
    role_id: uuid.UUID,
    table_name: Optional[str] = None,
) -> None:
    """
    Recalculates access policies dynamically. When direct/dept grants are assigned,
    we create explicit rows for ancestor roles or department members.
    Similar to `_create_policies_with_inheritance` in documents.
    """
    pass  # Managed explicitly in API endpoints to stay simple and identical to documents access creation.


# --- Query Generator & Execution Layer ---


async def translate_nl_to_sql(
    query: str,
    schema_data_filtered: Dict[str, Any],
    engine_type: str,
    db: Session,
    model_id: Optional[uuid.UUID] = None,
) -> str:
    """
    Uses the LLM model to translate natural language into a clean, single SQL statement.
    """

    # Build schema description
    schema_desc = []
    for tbl in schema_data_filtered.get("tables", []):
        cols = ", ".join([f"{c['name']} ({c['type']})" for c in tbl["columns"]])
        pk = f", Primary Key: {tbl['primary_key']}" if tbl["primary_key"] else ""
        fks = ""
        if tbl["foreign_keys"]:
            fk_strings = [
                f"{fk['constrained_columns']} -> {fk['referred_table']}({fk['referred_columns']})"
                for fk in tbl["foreign_keys"]
            ]
            fks = f", Foreign Keys: [{', '.join(fk_strings)}]"
        schema_desc.append(f"Table: {tbl['name']} [{cols}{pk}{fks}]")

    schema_str = "\n".join(schema_desc)

    system_prompt = (
        "You are an expert SQL translation assistant. Your task is to translate the user's natural language question "
        "into a valid, executable SQL query for the given database schema. Follow these strict rules:\n"
        "1. Output ONLY the raw SQL query. Do not wrap it in markdown code blocks, do not add comments, and do not write any introductory or explanatory text.\n"
        f"2. Use {engine_type} SQL syntax.\n"
        "3. Pay attention to case-sensitivity and quote identifiers correctly if needed (e.g. backticks for MySQL, double quotes for PostgreSQL).\n"
        "4. Only query the tables and columns listed in the schema. Do not invent columns.\n"
        "5. ALWAYS add a LIMIT or TOP clause of 100 to prevent returning too many rows, unless the query is an aggregation (COUNT, SUM, AVG).\n"
        "6. Do NOT output any write queries (INSERT, UPDATE, DELETE, DROP, ALTER). The query must be purely read-only (SELECT)."
    )

    prompt = f"""Database Schema (Engine: {engine_type}):
{schema_str}

User Question: {query}

SQL Query:"""

    selected_model_string = "claude-haiku-4-5-20251001"
    selected_provider = "anthropic"

    if model_id:
        db_model = (
            db.query(AvailableModel).filter(AvailableModel.id == model_id).first()
        )
        if db_model:
            selected_model_string = db_model.model_string
            selected_provider = db_model.provider

    if selected_provider == "anthropic":
        client = _get_async_anthropic_client()
        response = await client.messages.create(
            model=selected_model_string,
            max_tokens=2048,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        sql = response.content[0].text.strip()
    elif selected_provider == "openrouter":
        # Simple non-stream fallback
        sql = ""
        async for chunk_type, data in stream_openrouter_completion(
            model_string=selected_model_string,
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        ):
            if chunk_type == "text":
                sql += data
        sql = sql.strip()
    else:
        raise ValueError(f"Unsupported provider: {selected_provider}")

    # Remove any markdown formatting wraps
    cleaned_sql = sql.strip().strip("`").strip()
    if cleaned_sql.lower().startswith("```sql"):
        cleaned_sql = cleaned_sql[6:]
    elif cleaned_sql.lower().startswith("```"):
        cleaned_sql = cleaned_sql[3:]
    if cleaned_sql.endswith("```"):
        cleaned_sql = cleaned_sql[:-3]
    cleaned_sql = cleaned_sql.strip()

    # Verify if it looks like a valid read-only SQL query (SELECT / WITH)
    # Remove leading comments
    lines = cleaned_sql.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped_line = line.strip()
        if (
            stripped_line
            and not stripped_line.startswith("--")
            and not stripped_line.startswith("/*")
            and not stripped_line.startswith("#")
        ):
            cleaned_lines.append(stripped_line)

    first_non_comment_line = cleaned_lines[0].lower() if cleaned_lines else ""
    if not (
        first_non_comment_line.startswith("select")
        or first_non_comment_line.startswith("with")
    ):
        raise ValueError(sql)

    return cleaned_sql


def run_query_on_connection(
    connection: ExternalDatabaseConnection,
    sql_query: str,
    schema_cache_tables: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Executes the query on the database. Checks for schema drift and enforces bounds.
    """
    password_decrypted = decrypt_password(connection.password)
    url = get_connection_url(
        engine_type=connection.engine,
        host=connection.host,
        port=connection.port,
        database_name=connection.database_name,
        username=connection.username,
        password_decrypted=password_decrypted,
        ssl_mode=connection.ssl_mode,
    )

    # Compile the cache of valid schema objects for drift checking
    # valid_tables = {tbl["name"].lower() for tbl in schema_cache_tables}
    valid_columns = {}
    for tbl in schema_cache_tables:
        valid_columns[tbl["name"].lower()] = {
            col["name"].lower() for col in tbl["columns"]
        }

    # Read-only configuration & execution bounds
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            # Enforce read-only transaction if supported
            if connection.engine == DatabaseEngine.postgresql:
                conn.execute(text("SET TRANSACTION READ ONLY"))

            # SQL sanity validation: prevent modification queries
            sql_upper = sql_query.upper().strip()
            if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
                raise ValueError("Only read-only SELECT queries are allowed.")

            try:
                result = conn.execute(text(sql_query))

                # Fetch maximum of 100 rows to enforce safety bounds
                rows = result.fetchmany(100)

                output = []
                # Handle empty/non-result-returning queries safely
                if result.returns_rows:
                    keys = list(result.keys())
                    for row in rows:
                        output.append(dict(zip(keys, row)))
                return output

            except Exception as e:
                err_str = str(e).lower()
                # Check for table or column missing/undefined (schema drift indicator)
                # PostgreSQL errors: 'relation "..." does not exist' or 'column "..." does not exist'
                # MySQL errors: "table '...' doesn't exist" or "unknown column '...' in 'field list'"
                is_drift = False
                if "relation" in err_str and "does not exist" in err_str:
                    is_drift = True
                elif "column" in err_str and "does not exist" in err_str:
                    is_drift = True
                elif "table" in err_str and "exist" in err_str:
                    is_drift = True
                elif "column" in err_str and "field list" in err_str:
                    is_drift = True
                elif "unknown column" in err_str:
                    is_drift = True

                if is_drift:
                    raise ValueError(
                        f"Database execution failed due to a detected schema mismatch (drift): {str(e)}. "
                        "Please request an Administrator to 'Refresh Schema' for this database."
                    )
                raise e
    finally:
        engine.dispose()

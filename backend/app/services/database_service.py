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

        # Query custom enum types and allowed values directly from database catalogs
        enums_lookup = {}
        if engine_type == DatabaseEngine.postgresql:
            try:
                pg_query = """
                SELECT 
                    ns.nspname AS schema_name,
                    t.relname AS table_name,
                    a.attname AS column_name,
                    e.enumlabel AS enum_value
                FROM pg_attribute a
                JOIN pg_class t ON a.attrelid = t.oid
                JOIN pg_namespace ns ON t.relnamespace = ns.oid
                JOIN pg_type tp ON a.atttypid = tp.oid
                JOIN pg_enum e ON tp.oid = e.enumtypid
                WHERE a.attnum > 0 AND NOT a.attisdropped
                ORDER BY ns.nspname, t.relname, a.attname, e.enumsortorder;
                """
                with engine.connect() as conn:
                    pg_res = conn.execute(text(pg_query)).fetchall()
                    for s_name, t_name, c_name, e_val in pg_res:
                        key = (
                            s_name.lower() if s_name else None,
                            t_name.lower(),
                            c_name.lower(),
                        )
                        if key not in enums_lookup:
                            enums_lookup[key] = []
                        enums_lookup[key].append(e_val)
            except Exception as enum_err:
                print(
                    f"[WARNING] Failed to fetch Postgres enums from catalog: {enum_err}"
                )
            print(f"[INFO] Found {len(enums_lookup)} enum columns in Postgres.")
            print(f"[INFO] Enum lookup keys: {list(enums_lookup.keys())[:5]} ...")

        elif engine_type == DatabaseEngine.mysql:
            try:
                mysql_query = """
                SELECT 
                    table_schema AS schema_name,
                    table_name AS table_name,
                    column_name AS column_name,
                    column_type AS column_type
                FROM information_schema.columns
                WHERE data_type = 'enum' AND table_schema = DATABASE();
                """
                import re

                with engine.connect() as conn:
                    mysql_res = conn.execute(text(mysql_query)).fetchall()
                    for s_name, t_name, c_name, col_type in mysql_res:
                        vals = re.findall(r"'([^']*)'", col_type)
                        if vals:
                            key = (
                                s_name.lower() if s_name else None,
                                t_name.lower(),
                                c_name.lower(),
                            )
                            enums_lookup[key] = vals
            except Exception as enum_err:
                print(
                    f"[WARNING] Failed to fetch MySQL enums from information_schema: {enum_err}"
                )

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
                    col_item = {
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": col.get("nullable", True),
                    }
                    lookup_schema = schema.lower() if schema else None
                    key1 = (lookup_schema, table_name.lower(), col["name"].lower())
                    key2 = (None, table_name.lower(), col["name"].lower())
                    allowed_vals = enums_lookup.get(key1) or enums_lookup.get(key2)
                    if allowed_vals:
                        col_item["allowed_values"] = allowed_vals
                    columns_info.append(col_item)

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


def format_query_results_for_prompt(
    results: Optional[List[Dict[str, Any]]], threshold: int = 20
) -> str:
    """
    Formats SQL query results for inclusion in prompt. If the results list is empty
    or None, returns a message. If the size of the result set exceeds `threshold`,
    returns a bounded summary (row count + first 3 rows).
    """
    import json

    if not results:
        return "No results returned."
    if not isinstance(results, list):
        return str(results)

    total_rows = len(results)
    if total_rows <= threshold:
        return json.dumps(results, indent=2, default=str)

    # Bounded summary: row count + first 3 rows
    summary_rows = results[:3]
    return (
        f"Total rows: {total_rows} (showing first 3 rows as summary)\n"
        f"{json.dumps(summary_rows, indent=2, default=str)}"
    )


async def translate_nl_to_sql(
    query: str,
    schema_data_filtered: Dict[str, Any],
    engine_type: str,
    db: Session,
    model_id: Optional[uuid.UUID] = None,
    failed_sql: Optional[str] = None,
    error_message: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Uses the LLM model to translate natural language into a clean, single SQL statement.
    """

    # Build schema description
    schema_desc = []
    for tbl in schema_data_filtered.get("tables", []):
        cols_list = []
        for c in tbl["columns"]:
            c_str = f"{c['name']} ({c['type']})"
            if "allowed_values" in c:
                c_str += f" [allowed values: {c['allowed_values']}]"
            cols_list.append(c_str)
        cols = ", ".join(cols_list)
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

    history_str = ""
    if conversation_history:
        history_parts = []
        for idx, turn in enumerate(conversation_history, 1):
            part = f"--- Turn {idx} ---\nQuestion: {turn['question']}\n"
            if turn.get("generated_sql"):
                part += f"Generated SQL: {turn['generated_sql']}\n"
            if turn.get("query_results") is not None:
                formatted_results = format_query_results_for_prompt(
                    turn["query_results"], settings.SQL_RESULT_SUMMARY_THRESHOLD
                )
                part += f"SQL Results:\n{formatted_results}\n"
            if turn.get("answer"):
                part += f"Answer: {turn['answer']}\n"
            history_parts.append(part)
        history_str = (
            "\nPrior Conversation Context:\n" + "\n".join(history_parts) + "\n"
        )

    rule_9 = (
        "9. For equality filters against TEXT/VARCHAR columns, ALWAYS use the case-insensitive ILIKE operator instead of the standard = operator (e.g. col ILIKE 'value'). Do not apply this to non-text columns (like IDs, numbers, booleans, or dates)."
        if engine_type == "postgresql"
        else "9. For equality filters against TEXT/VARCHAR columns, ALWAYS use case-insensitive comparison. Since MySQL LIKE is case-insensitive by default under standard collations, you can use col LIKE 'value' or LOWER(col) = LOWER('value'). Do not apply this to non-text columns (like IDs, numbers, booleans, or dates)."
    )

    if failed_sql and error_message:
        system_prompt = (
            "You are an expert SQL translation assistant. You previously generated a SQL query that failed with a database error.\n"
            "Your task is to correct the SQL query based on the database error message and user's original question. Follow these strict rules:\n"
            "1. Output ONLY the raw SQL query. Do not wrap it in markdown code blocks, do not add comments, and do not write any introductory or explanatory text.\n"
            f"2. Use {engine_type} SQL syntax.\n"
            "3. Pay attention to case-sensitivity and quote identifiers correctly if needed (e.g. backticks for MySQL, double quotes for PostgreSQL).\n"
            "4. Only query the tables and columns listed in the schema. Do not invent columns.\n"
            "5. ALWAYS add a LIMIT or TOP clause of 100 to prevent returning too many rows, unless the query is an aggregation (COUNT, SUM, AVG).\n"
            "6. Do NOT output any write queries (INSERT, UPDATE, DELETE, DROP, ALTER). The query must be purely read-only (SELECT).\n"
            "7. Use the 'Prior Conversation Context' to resolve references (such as pronouns 'he', 'she', 'it', or referring phrases like 'that document', 'the same region', 'last quarter') to concrete values or conditions in the generated SQL query.\n"
            "8. If a reference in the question cannot be resolved using the conversation context, or if there is no context and the question is too ambiguous to generate a query for, you MUST return exactly: 'I cannot generate a SQL query, this is ambiguous'\n"
            f"{rule_9}"
        )

        prompt = f"""Database Schema (Engine: {engine_type}):
{schema_str}
{history_str}
User Question: {query}

Previously Generated SQL:
{failed_sql}

Database Error Message:
{error_message}

Please correct the SQL query to fix the value/literal mismatch or enum issue reported in the error message. Ensure the SQL is completely valid and follows all rules.

SQL Query:"""
    else:
        system_prompt = (
            "You are an expert SQL translation assistant. Your task is to translate the user's natural language question "
            "into a valid, executable SQL query for the given database schema. Follow these strict rules:\n"
            "1. Output ONLY the raw SQL query. Do not wrap it in markdown code blocks, do not add comments, and do not write any introductory or explanatory text.\n"
            f"2. Use {engine_type} SQL syntax.\n"
            "3. Pay attention to case-sensitivity and quote identifiers correctly if needed (e.g. backticks for MySQL, double quotes for PostgreSQL).\n"
            "4. Only query the tables and columns listed in the schema. Do not invent columns.\n"
            "5. ALWAYS add a LIMIT or TOP clause of 100 to prevent returning too many rows, unless the query is an aggregation (COUNT, SUM, AVG).\n"
            "6. Do NOT output any write queries (INSERT, UPDATE, DELETE, DROP, ALTER). The query must be purely read-only (SELECT).\n"
            "7. Use the 'Prior Conversation Context' to resolve references (such as pronouns 'he', 'she', 'it', or referring phrases like 'that document', 'the same region', 'last quarter') to concrete values or conditions in the generated SQL query.\n"
            "8. If a reference in the question cannot be resolved using the conversation context, or if there is no context and the question is too ambiguous to generate a query for, you MUST return exactly: 'I cannot generate a SQL query, this is ambiguous'\n"
            f"{rule_9}"
        )

        prompt = f"""Database Schema (Engine: {engine_type}):
{schema_str}
{history_str}
User Question: {query}

SQL Query:"""

    db_model = None
    if model_id:
        db_model = (
            db.query(AvailableModel)
            .filter(AvailableModel.id == model_id, AvailableModel.is_active)
            .first()
        )

    if not db_model:
        from app.models.enums import ModelProvider

        db_model = (
            db.query(AvailableModel)
            .filter(
                AvailableModel.is_active,
                AvailableModel.provider == ModelProvider.anthropic,
            )
            .order_by(AvailableModel.created_at.asc())
            .first()
        )
        if not db_model:
            db_model = (
                db.query(AvailableModel)
                .filter(AvailableModel.is_active)
                .order_by(AvailableModel.created_at.asc())
                .first()
            )

    if db_model:
        selected_model_string = db_model.model_string
        selected_provider = db_model.provider
    else:
        selected_model_string = "claude-haiku-4-5-20251001"
        selected_provider = "anthropic"

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


def resolve_categorical_literals(
    sql_query: str, schema_tables: List[Dict[str, Any]]
) -> str:
    """
    Case-insensitively resolves single-quoted literal values in the SQL query against
    allowed_values cached in the schema tables.
    If the column is an enum:
        - If matched, rewrites the filter to: col = 'CanonicalValue'
        - If fallback, rewrites the filter to: col::text ILIKE '%value%'
    If the column is a non-enum TEXT/VARCHAR:
        - Leaves the case-insensitive ILIKE/LOWER operator intact.
    """
    import re

    # 1. Build a map of column names and their allowed values
    # To be precise, identify which tables are mentioned in the query
    mentioned_tables = []
    sql_lower = sql_query.lower()
    for tbl in schema_tables:
        tname = tbl.get("name", "").lower()
        if tname and tname in re.split(r"\b", sql_lower):
            mentioned_tables.append(tbl)

    if not mentioned_tables:
        mentioned_tables = schema_tables

    column_allowed_vals = {}
    for tbl in mentioned_tables:
        tname = tbl.get("name", "").lower()
        for col in tbl.get("columns", []):
            cname = col.get("name", "").lower()
            if "allowed_values" in col and col["allowed_values"]:
                # Map both direct column name and fully-qualified column name
                column_allowed_vals[cname] = (col["allowed_values"], col.get("name"))
                if tname:
                    column_allowed_vals[f"{tname}.{cname}"] = (
                        col["allowed_values"],
                        col.get("name"),
                    )

    if not column_allowed_vals:
        return sql_query

    # Regexes to detect operators immediately preceding the literal
    op_regex = re.compile(r"\b([a-zA-Z0-9_\.]+)\s+(ILIKE|LIKE|=)\s*$", re.IGNORECASE)
    lower_op_regex = re.compile(
        r"\bLOWER\s*\(\s*([a-zA-Z0-9_\.]+)\s*\)\s*=\s*LOWER\s*\(\s*$", re.IGNORECASE
    )

    # 2. Find all string literals in the query
    literal_regex = re.compile(r"'((?:''|[^'])*)'")

    matches = list(literal_regex.finditer(sql_query))
    if not matches:
        return sql_query

    replacements = []
    for match in matches:
        start_idx, end_idx = match.span()
        literal_val = match.group(1)
        unescaped_val = literal_val.replace("''", "'")

        before_text = sql_query[:start_idx]

        # Try to match preceding operator patterns
        op_match = op_regex.search(before_text)
        lower_match = lower_op_regex.search(before_text)

        target_col_token = None
        target_allowed_vals = None
        target_col_display_name = None
        filter_start_idx = None

        if op_match:
            target_col_token = op_match.group(1)
            filter_start_idx = op_match.start(1)
        elif lower_match:
            target_col_token = lower_match.group(1)
            filter_start_idx = lower_match.start()  # Start of LOWER(col)

        if target_col_token:
            lookup_key = target_col_token.lower()
            if "." in lookup_key:
                lookup_key = lookup_key.split(".")[-1]

            if lookup_key in column_allowed_vals:
                target_allowed_vals, target_col_display_name = column_allowed_vals[
                    lookup_key
                ]

        # Safety fallback scanning if regex didn't find the column operator
        if not target_allowed_vals:
            before_text_lower = before_text.lower()
            tokens = re.split(r"[^a-zA-Z0-9_\.]+", before_text_lower)
            tokens = [t for t in tokens if t]
            for t in reversed(tokens):
                lookup_key = t
                if "." in t:
                    lookup_key = t.split(".")[-1]
                if lookup_key in column_allowed_vals:
                    target_allowed_vals, target_col_display_name = column_allowed_vals[
                        lookup_key
                    ]
                    target_col_token = t
                    filter_start_idx = before_text_lower.rfind(t)
                    break

        if target_allowed_vals:
            matched_canonical = None
            for val in target_allowed_vals:
                if isinstance(val, str) and val.lower() == unescaped_val.lower():
                    matched_canonical = val
                    break

            if matched_canonical is not None:
                # Canonical rewrite: use plain =
                escaped_canonical = matched_canonical.replace("'", "''")
                replacement_text = f"{target_col_token} = '{escaped_canonical}'"

                # If we have filter_start_idx, replace from operator start to literal end
                if filter_start_idx is not None and filter_start_idx >= 0:
                    replacements.append((filter_start_idx, end_idx, replacement_text))
                else:
                    replacements.append((start_idx, end_idx, f"'{escaped_canonical}'"))

                logger.info(
                    f"SQL Casing Rewrite (Enum Match): column '{target_col_display_name}', "
                    f"original literal '{literal_val}', resolved literal '{escaped_canonical}'"
                )
            else:
                # Fallback rewrite: cast to text and use ILIKE
                escaped_literal = unescaped_val.replace("'", "''")
                replacement_text = (
                    f"{target_col_token}::text ILIKE '%{escaped_literal}%'"
                )

                if filter_start_idx is not None and filter_start_idx >= 0:
                    replacements.append((filter_start_idx, end_idx, replacement_text))

                logger.info(
                    f"SQL Casing Rewrite (Enum Fallback): column '{target_col_display_name}', "
                    f"original literal '{literal_val}', casting enum to text ILIKE"
                )

    if replacements:
        replacements.sort(key=lambda x: x[0], reverse=True)
        sql_list = list(sql_query)
        for start, end, rep_str in replacements:
            sql_list[start:end] = list(rep_str)
        return "".join(sql_list)

    return sql_query


def run_query_on_connection(
    connection: ExternalDatabaseConnection,
    sql_query: str,
    schema_cache_tables: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Executes the query on the database. Checks for schema drift and enforces bounds.
    """
    try:
        sql_query = resolve_categorical_literals(sql_query, schema_cache_tables)
    except Exception as exc:
        logger.error(f"Error during categorical literal resolution: {exc}")

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

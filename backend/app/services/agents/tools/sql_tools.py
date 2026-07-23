from typing import Optional
import uuid
import time
import json
from app.models.external_database import (
    ExternalDatabaseConnection,
)
from app.services import database_service
import app.services.rag_service as rag_service

logger = rag_service.logger


SCHEMA_INTELLIGENCE_TOOLS = [
    {
        "name": "get_all_table_names",
        "description": "Returns only the names of every table the user is authorized to access. Contains no column details. Very cheap.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_table_schema",
        "description": "Returns the complete schema (columns, types, keys) only for the specified table names.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of table names to get schema for, e.g. ['orders', 'customers']",
                }
            },
            "required": ["table_names"],
        },
    },
    {
        "name": "get_all_tables_schema",
        "description": "Returns the complete schema of every authorized table. This is expensive and should only be used if selective exploration is insufficient.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


SQL_GENERATION_TOOLS = [
    {
        "name": "generate_sql",
        "description": (
            "Generates a SQL query from the user's natural language question using the provided schema. "
            "Pass failed_sql and error_message if a previous attempt failed, so the model can correct it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "failed_sql": {
                    "type": "string",
                    "description": "The previously generated SQL that failed. Omit on first attempt.",
                },
                "error_message": {
                    "type": "string",
                    "description": "The error from the previous attempt. Omit on first attempt.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "validate_sql",
        "description": (
            "Validates whether the generated SQL only accesses tables and columns the user is authorized to query. "
            "Always call this after generate_sql before proceeding."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The SQL query to validate.",
                }
            },
            "required": ["sql"],
        },
    },
    {
        "name": "execute_sql",
        "description": (
            "Executes the validated SQL query against the database and returns the results. "
            "Only call this after validate_sql has confirmed the SQL is authorized. "
            "If execution fails, use the error to call generate_sql again with the failed SQL and error message."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The validated SQL query to execute.",
                }
            },
            "required": ["sql"],
        },
    },
]


async def generate_sql(
    query: str,
    schema: dict,
    engine_type: str,
    conversation_history: Optional[list],
    failed_sql: Optional[str] = None,
    error_message: Optional[str] = None,
) -> str:
    # Conditional rule for case-insensitive comparison based on the database engine type
    rule_case = (
        "9. For equality filters against TEXT/VARCHAR columns, ALWAYS use ILIKE instead of = (e.g. col ILIKE 'value'). Do not apply to non-text columns."
        if engine_type == "postgresql"
        else "9. For equality filters against TEXT/VARCHAR columns, use case-insensitive comparison via LIKE or LOWER(). Do not apply to non-text columns."
    )

    schema_str = json.dumps(schema)
    history_str = (
        f"\nPrior Conversation Context:\n{json.dumps(conversation_history)}\n"
        if conversation_history
        else ""
    )

    # If access is denied, instruct the model to find an alternative query using only authorized tables/columns.
    if failed_sql and error_message and "access denied" in error_message.lower():
        system_prompt = (
            "You are an expert SQL translation assistant. You previously generated a SQL query that accessed an unauthorized table or column (Access Denied).\n"
            "Your task is to correct the SQL query by looking for an alternative path or query structure using other tables or columns in the schema that are authorized to answer the question.\n"
            "Follow these strict rules:\n"
            "1. Output ONLY the raw SQL query. Do not wrap it in markdown code blocks, do not add comments, and do not write any introductory or explanatory text.\n"
            f"2. Use {engine_type} SQL syntax.\n"
            "3. Pay attention to case-sensitivity and quote identifiers correctly if needed (e.g. backticks for MySQL, double quotes for PostgreSQL).\n"
            "4. Only query the tables and columns listed in the schema. Do not invent columns.\n"
            "5. ALWAYS add a LIMIT or TOP clause of 100 to prevent returning too many rows, unless the query is an aggregation (COUNT, SUM, AVG).\n"
            "6. Do NOT output any write queries (INSERT, UPDATE, DELETE, DROP, ALTER). The query must be purely read-only (SELECT).\n"
            "7. Use the 'Prior Conversation Context' to resolve references to concrete values or conditions in the SQL query. If no context exists, treat the question as standalone and generate the best possible query from the schema alone.\n"
            "8. You MUST NOT return any workaround (such as returning dummy/constant values, placeholder fields, or inventing columns not present in the schema). You must strictly return what's being asked. If there is no alternative way to answer the question using only the allowed tables and columns, you must output 'I cannot generate a SQL query, this is ambiguous'.\n"
            f"{rule_case}\n"
            "10. When filtering on a column that has allowed_values listed in the schema, you MUST use the exact canonical value from that list. Do not guess, infer, or change the casing of enum values."
        )

        prompt = f"""Database Schema (Engine: {engine_type}):
        {schema_str}
        {history_str}
        User Question: {query}

        Previously Generated SQL:
        {failed_sql}

        Database Error Message:
        {error_message}

        The previously generated query failed because it accessed an unauthorized table or column. Please find another way to query the database using other authorized tables or columns to answer the question. Do NOT use any unauthorized columns or tables mentioned in the error message. Do NOT return any workarounds (e.g. using dummy/constant values, placeholder fields, or inventing columns). You must strictly return what is asked. If there is no other way to answer the question, output "I cannot generate a SQL query, this is ambiguous".

        SQL Query:"""

        # Instruct the model to correct the SQL query based on the error message and user's original question.
    elif failed_sql:
        system_prompt = (
            "You are an expert SQL translation assistant. You previously generated a SQL query that failed with a database error.\n"
            "Your task is to correct the SQL query based on the database error message and user's original question. Follow these strict rules:\n"
            "1. Output ONLY the raw SQL query. Do not wrap it in markdown code blocks, do not add comments, and do not write any introductory or explanatory text.\n"
            f"2. Use {engine_type} SQL syntax.\n"
            "3. Pay attention to case-sensitivity and quote identifiers correctly if needed (e.g. backticks for MySQL, double quotes for PostgreSQL).\n"
            "4. Only query the tables and columns listed in the schema. Do not invent columns.\n"
            "5. ALWAYS add a LIMIT or TOP clause of 100 to prevent returning too many rows, unless the query is an aggregation (COUNT, SUM, AVG).\n"
            "6. Do NOT output any write queries (INSERT, UPDATE, DELETE, DROP, ALTER). The query must be purely read-only (SELECT).\n"
            "7. Use the 'Prior Conversation Context' to resolve references (pronouns like 'he', 'she', 'it', or phrases like 'that document', 'the same region', 'last quarter') to concrete values or conditions in the SQL query. If no context exists, treat the question as standalone and generate the best possible query from the schema alone.\n"
            "8. Only return 'I cannot generate a SQL query, this is ambiguous' as an absolute last resort - specifically when the question refers to something that has multiple equally valid interpretations AND the schema provides no way to distinguish between them, AND there is no conversation context to resolve it. A question that is broad or open-ended (e.g. 'show me costs', 'which is the worst performing') is NOT ambiguous - map it to the most natural columns in the schema and generate a query. When in doubt, generate a query.\n"
            f"{rule_case}\n"
            "10. When filtering on a column that has allowed_values listed in the schema, you MUST use the exact canonical value from that list. Do not guess, infer, or change the casing of enum values."
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
        # General system prompt
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
            "7. Use the 'Prior Conversation Context' to resolve references (pronouns like 'he', 'she', 'it', or phrases like 'that document', 'the same region', 'last quarter') to concrete values or conditions in the SQL query. If no context exists, treat the question as standalone and generate the best possible query from the schema alone.\n"
            "8. Only return 'I cannot generate a SQL query, this is ambiguous' as an absolute last resort - specifically when the question refers to something that has multiple equally valid interpretations AND the schema provides no way to distinguish between them, AND there is no conversation context to resolve it. A question that is broad or open-ended (e.g. 'show me costs', 'which is the worst performing') is NOT ambiguous - map it to the most natural columns in the schema and generate a query. When in doubt, generate a query.\n"
            f"{rule_case}\n"
            "10. When filtering on a column that has allowed_values listed in the schema, you MUST use the exact canonical value from that list because the database requires exact matches. Do not guess, infer, or change the casing of enum values."
        )

        prompt = f"""Database Schema (Engine: {engine_type}):
        {schema_str}
        {history_str}
        User Question: {query}

        SQL Query:"""

    # Call the LLM to generate SQL
    print(f"[SQL Generation] Prompting LLM with query: {query}")
    client = rag_service._get_async_anthropic_client()
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        temperature=0,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    sql = response.content[0].text.strip()

    print(f"[SQL Generation] LLM Response: {sql}")

    # SQL clearing: remove code block markers, comments, and ensure it starts with SELECT or WITH
    cleaned_sql = sql.strip()
    if cleaned_sql.lower().startswith("```sql"):
        cleaned_sql = cleaned_sql[6:]
    elif cleaned_sql.lower().startswith("```"):
        cleaned_sql = cleaned_sql[3:]
    if cleaned_sql.endswith("```"):
        cleaned_sql = cleaned_sql[:-3]
    cleaned_sql = cleaned_sql.strip()

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
        print(f"[SQL Generation] Invalid SQL generated: {sql}")
        raise ValueError(sql)

    print(f"[SQL Generation] Cleaned SQL: {cleaned_sql}")
    return cleaned_sql


# TOOLS
def _execute_schema_tool(
    tool_name: str, tool_args: dict, authorized_tables: list[dict]
) -> str:
    # returns the names of all authorized tables
    if tool_name == "get_all_table_names":
        names = []
        for table in authorized_tables:
            if "name" in table:
                names.append(table["name"])
        return json.dumps(names)

    # returns the schema for the specified table names
    elif tool_name == "get_table_schema":
        table_names = tool_args.get("table_names", [])
        if isinstance(table_names, str):
            table_names = [table_names]
        requested_set = {str(name).lower() for name in table_names}
        matched = [
            t for t in authorized_tables if t.get("name", "").lower() in requested_set
        ]
        return json.dumps({"tables": matched}, default=str)

    # returns the schema for all authorized tables
    elif tool_name == "get_all_tables_schema":
        return json.dumps({"tables": authorized_tables}, default=str)
    else:
        return f"Unknown tool: {tool_name}"


def validate_sql(
    sql: str,
    engine_type: str,
    authorized_cols_by_table: dict,
    valid_tables: set,
    all_physical_cols_by_table: dict,
) -> str:
    try:
        database_service.check_sql_authorized_columns(
            sql_query=sql,
            engine_type=engine_type,
            authorized_cols_by_table=authorized_cols_by_table,
            valid_tables=valid_tables,
            all_physical_cols_by_table=all_physical_cols_by_table,
        )
        return json.dumps({"valid": True, "reason": ""})
    except Exception as exc:
        return json.dumps({"valid": False, "reason": str(exc)})


def execute_sql(sql: str, connection_id: str, db) -> str:
    try:
        # Convert connection_id string to UUID
        conn_uuid = (
            uuid.UUID(connection_id)
            if isinstance(connection_id, str)
            else connection_id
        )

        # Fetch the database connection record
        connection = (
            db.query(ExternalDatabaseConnection)
            .filter(ExternalDatabaseConnection.id == conn_uuid)
            .first()
        )

        # Execute the SQL query and measure execution time
        start_time = time.perf_counter()
        query_results = database_service.run_query_on_connection(
            connection=connection,
            sql_query=sql,
        )
        execution_time_ms = int((time.perf_counter() - start_time) * 1000)
        print(
            f"[SQL Agent] Execution succeeded. Rows: {len(query_results)}, Time: {execution_time_ms}ms"
        )

        # Return success response with results and metadata
        return json.dumps(
            {
                "success": True,
                "rows": query_results,
                "row_count": len(query_results),
                "execution_time_ms": execution_time_ms,
            },
            default=str,
        )

    except Exception as exc:
        print(f"[SQL Agent] Execution failed: {exc}")
        return json.dumps({"success": False, "error": str(exc)})


validate_sql = validate_sql
execute_sql = execute_sql

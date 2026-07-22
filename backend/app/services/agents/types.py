from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Literal
import uuid

from typing import TypedDict, Annotated
import operator


class AgentState(TypedDict):
    # --- Input fields (set once at graph entry, never modified) ---
    query: str
    user_id: str
    tenant_id: str
    database_id: Optional[str]
    document_id: Optional[str]
    conversation_history: str
    model_id: Optional[str]
    session_id: Optional[str]
    command_instruction: Optional[str]
    compare_document_ids: Optional[list[str]]
    is_compare_mode: bool
    is_summarize_mode: bool

    # --- Orchestrator output ---
    invoke_sql: bool
    invoke_rag: bool
    mode: Literal["db_only", "doc_only", "cross_source"]
    orchestrator_reasoning: str

    # --- Progress messages streamed to user ---
    # Uses add_messages reducer so each node appends rather than overwrites
    progress_tokens: Annotated[list[str], operator.add]

    # --- Agent results ---
    sql_result: Optional[SQLAgentResult]
    rag_result: Optional[RAGAgentResult]

    # --- Context gathering (set once, never recomputed) ---
    db_user_id: Optional[str]
    db_connection_id: Optional[str]
    db_authorized_schema: Optional[dict]
    db_session_turns: Optional[list]
    db_authorized_cols_by_table: Optional[dict]
    db_all_physical_cols_by_table: Optional[dict]
    db_valid_tables: Optional[set]
    db_connection_engine: Optional[str]
    db_connection_name: Optional[str]
    context_error: Optional[str]

    # --- Query understanding ---
    query_plan: Optional[dict]

    # --- Schema selection ---
    db_filtered_schema: Optional[dict]

    # --- SQL generation ---
    generated_sql: Optional[str]
    previous_sql: Optional[str]
    sql_generation_attempts: int
    sql_generation_error: Optional[str]

    # --- Execution ---
    sql_execution_result: Optional[list]
    sql_execution_error: Optional[str]
    sql_execution_attempts: int

    # --- Result judge ---
    sql_sufficient: bool
    sql_judge_reasoning: Optional[str]
    sql_fix_instruction: Optional[str]
    sql_result_attempts: int

    # --- Retry tracking ---
    rag_attempts: int
    rag_max_attempts: int

    # --- Judge verdicts (set by judge nodes) ---
    rag_sufficient: bool
    rag_judge_reasoning: str
    rag_fix_instruction: str

    # --- Fusion output ---
    final_answer: str
    citations: list[dict]
    follow_up_questions: list[str]
    chart_spec: Optional[dict]
    query_results: Optional[list[dict]]
    model_string: Optional[str]
    resolved_model: Optional[str]
    resolved_model_id: Optional[str]
    was_fallback: bool
    fallback_model_name: Optional[str]
    execution_time_ms: int


# --- Agent result types ---


@dataclass
class SQLAgentResult:
    success: bool
    sql_query: Optional[str] = None
    query_results: Optional[list[dict]] = None
    formatted_results: Optional[str] = None
    connection_name: Optional[str] = None
    connection_id: Optional[uuid.UUID] = None
    execution_time_ms: int = 0
    confidence: float = 0.0  # 0.0 to 1.0
    reasoning: str = ""  # agent's own explanation of its output quality
    attempts: int = 1  # how many ReAct iterations were needed
    error: Optional[str] = None


@dataclass
class RAGAgentResult:
    success: bool
    qdrant_results: list[dict] = field(default_factory=list)
    excel_results: list[dict] = field(default_factory=list)
    context_block: str = "No relevant context found."
    doc_id_to_filename: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    reasoning: str = ""
    attempts: int = 1
    reformulated_query: Optional[str] = (
        None  # if agent reformulated the query during retry
    )


if __name__ == "__main__":
    state = AgentState(
        query="test",
        user_id="test",
        tenant_id="test",
        database_id=None,
        document_id=None,
        conversation_history="",
        model_id=None,
        session_id=None,
        command_instruction=None,
        compare_document_ids=None,
        is_compare_mode=False,
        is_summarize_mode=False,
        invoke_sql=False,
        invoke_rag=False,
        mode="doc_only",
        orchestrator_reasoning="",
        progress_tokens=[],
        sql_result=None,
        rag_result=None,
        db_user_id=None,
        db_connection_id=None,
        db_authorized_schema=None,
        db_session_turns=None,
        db_authorized_cols_by_table=None,
        db_all_physical_cols_by_table=None,
        db_valid_tables=None,
        db_connection_engine=None,
        db_connection_name=None,
        context_error=None,
        query_plan=None,
        db_filtered_schema=None,
        generated_sql=None,
        previous_sql=None,
        sql_generation_attempts=0,
        sql_generation_error=None,
        sql_execution_result=None,
        sql_execution_error=None,
        sql_execution_attempts=0,
        sql_sufficient=False,
        sql_judge_reasoning=None,
        sql_fix_instruction=None,
        sql_result_attempts=0,
        rag_attempts=0,
        rag_max_attempts=3,
        rag_sufficient=False,
        rag_judge_reasoning="",
        rag_fix_instruction="",
        final_answer="",
        citations=[],
        follow_up_questions=[],
        chart_spec=None,
        query_results=None,
        model_string=None,
        resolved_model=None,
        resolved_model_id=None,
        was_fallback=False,
        fallback_model_name=None,
        execution_time_ms=0,
    )
    print("AgentState OK")
    print("LangGraph import OK")

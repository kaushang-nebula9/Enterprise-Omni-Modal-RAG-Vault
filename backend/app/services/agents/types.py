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

    # --- Retry tracking ---
    sql_attempts: int
    sql_max_attempts: int
    rag_attempts: int
    rag_max_attempts: int

    # --- Judge verdicts (set by judge nodes) ---
    sql_sufficient: bool
    sql_judge_reasoning: str
    sql_fix_instruction: str
    rag_sufficient: bool
    rag_judge_reasoning: str
    rag_fix_instruction: str

    # --- Fusion output ---
    final_answer: str
    citations: list[dict]
    follow_up_questions: list[str]
    chart_spec: Optional[dict]
    generated_sql: Optional[str]
    query_results: Optional[list[dict]]
    model_string: Optional[str]
    resolved_model: Optional[str]
    resolved_model_id: Optional[str]
    was_fallback: bool
    fallback_model_name: Optional[str]
    execution_time_ms: int
    db_connection_id: Optional[str]


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
        sql_attempts=0,
        sql_max_attempts=3,
        rag_attempts=0,
        rag_max_attempts=3,
        sql_sufficient=False,
        sql_judge_reasoning="",
        sql_fix_instruction="",
        rag_sufficient=False,
        rag_judge_reasoning="",
        rag_fix_instruction="",
        final_answer="",
        citations=[],
        follow_up_questions=[],
        chart_spec=None,
        generated_sql=None,
        query_results=None,
        model_string=None,
        resolved_model=None,
        resolved_model_id=None,
        was_fallback=False,
        fallback_model_name=None,
        execution_time_ms=0,
        db_connection_id=None,
    )
    print("AgentState OK")
    print("LangGraph import OK")

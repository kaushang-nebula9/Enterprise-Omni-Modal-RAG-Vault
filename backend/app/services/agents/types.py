from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Literal
import uuid


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


@dataclass
class ExcelAgentResult:
    success: bool
    results: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""
    attempts: int = 1
    error: Optional[str] = None


@dataclass
class FusionAgentResult:
    success: bool
    answer: str = ""
    citations: list[dict] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)
    generated_sql: Optional[str] = None
    query_results: Optional[list[dict]] = None
    chart_spec: Optional[dict] = None
    model_string: Optional[str] = None
    resolved_model: Optional[str] = None
    resolved_model_id: Optional[uuid.UUID] = None
    was_fallback: bool = False
    fallback_model_name: Optional[str] = None
    execution_time_ms: int = 0
    db_connection_id: Optional[uuid.UUID] = None


# --- Orchestrator types ---


@dataclass
class OrchestratorPlan:
    mode: Literal["db_only", "doc_only", "cross_source"]
    invoke_sql: bool
    invoke_rag: bool
    invoke_excel: bool
    reasoning: str  # LLM's explanation of why it chose this plan
    parallel: bool = True  # whether SQL and RAG should run in parallel


@dataclass
class AgentObservation:
    agent_name: str  # "sql", "rag", "excel"
    result: SQLAgentResult | RAGAgentResult | ExcelAgentResult
    sufficient: bool  # orchestrator's judgment: is this result good enough?
    reinvoke: bool = False  # should this agent be re-invoked?
    reinvoke_instruction: str = ""  # what to do differently on re-invocation


# --- Fusion input ---


@dataclass
class FusionInput:
    query: str
    conversation_history: str
    command_instruction: Optional[str]
    model_id: Optional[uuid.UUID]
    sql_result: Optional[SQLAgentResult]
    rag_result: Optional[RAGAgentResult]
    mode: Literal["db_only", "doc_only", "cross_source"]
    database_id: Optional[uuid.UUID] = None
    document_id: Optional[uuid.UUID] = None

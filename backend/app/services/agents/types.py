from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Literal
import uuid


@dataclass
class SQLAgentResult:
    success: bool
    sql_query: Optional[str] = None
    query_results: Optional[list[dict]] = None
    formatted_results: Optional[str] = None
    connection_name: Optional[str] = None
    connection_id: Optional[uuid.UUID] = None
    execution_time_ms: int = 0
    error: Optional[str] = None


@dataclass
class RAGAgentResult:
    success: bool
    qdrant_results: list[dict] = field(default_factory=list)
    excel_results: list[dict] = field(default_factory=list)
    context_block: str = "No relevant context found."
    doc_id_to_filename: dict[str, str] = field(default_factory=dict)


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

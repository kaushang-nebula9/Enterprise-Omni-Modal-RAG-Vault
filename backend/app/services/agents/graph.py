from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.services.agents.types import AgentState
from app.services.agents.nodes.orchestrator import orchestrator_node
from app.services.agents.nodes.sql import (
    schema_selection_node,
    sql_generation_node,
    sql_execution_node,
    sql_result_judge_node,
)
from app.services.agents.nodes.rag import rag_node, rag_judge_node
from app.services.agents.nodes.fusion import fusion_node


def route_after_orchestrator(state: AgentState) -> list[str]:
    """
    After orchestrator decides the plan, route to the correct agent nodes.
    Returns a list of node names to invoke next (parallel execution if multiple).
    """
    next_nodes = []
    if state["invoke_sql"]:
        next_nodes.append("sql_node")
    if state["invoke_rag"]:
        next_nodes.append("rag_node")
    if not next_nodes:
        # Safety fallback - should never happen but route to fusion if no agents selected
        next_nodes.append("fusion_node")
    print(f"[Graph] Routing after orchestrator to: {next_nodes}")
    return next_nodes


def route_after_sql_generation(state: AgentState) -> str:
    if state.get("sql_generation_error"):
        attempts = state["sql_generation_attempts"]
        if attempts >= 2:
            print("[Graph] SQL generation: max attempts reached. Routing to END.")
            return "sql_failed"
        print("[Graph] SQL generation: validation error. Retrying.")
        return "sql_retry"
    return "sql_execute"


def route_after_sql_execution(state: AgentState) -> str:
    if state.get("sql_execution_error"):
        attempts = state["sql_generation_attempts"]
        if attempts >= 2:
            print("[Graph] SQL execution: max attempts reached.")
            return "sql_failed"
        print("[Graph] SQL execution: error. Retrying generation.")
        return "sql_retry"
    return "sql_judge"


def route_after_sql_result_judge(state: AgentState) -> str:
    sufficient = state["sql_sufficient"]
    attempts = state["sql_result_attempts"]
    if sufficient:
        print("[Graph] SQL result judge: sufficient. Proceeding to fusion.")
        return "sql_done"
    elif attempts >= 1:
        print("[Graph] SQL result judge: max attempts reached. Proceeding anyway.")
        return "sql_done"
    else:
        print("[Graph] SQL result judge: insufficient. Retrying generation.")
        return "sql_retry"


def route_after_rag_judge(state: AgentState) -> str:
    """
    After RAG judge evaluates the result, decide whether to retry RAG or proceed.
    """
    attempts = state["rag_attempts"]
    max_attempts = state["rag_max_attempts"]
    sufficient = state["rag_sufficient"]

    if sufficient:
        print("[Graph] RAG judge: sufficient=True. Proceeding to fusion check.")
        return "rag_done"
    elif attempts >= max_attempts:
        print(
            f"[Graph] RAG judge: max attempts ({max_attempts}) reached. Proceeding anyway."
        )
        return "rag_done"
    else:
        print(
            f"[Graph] RAG judge: sufficient=False. Retrying RAG (attempt {attempts + 1}/{max_attempts})."
        )
        return "rag_retry"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Add all nodes
    graph.add_node("orchestrator_node", orchestrator_node)
    graph.add_node("schema_selection_node", schema_selection_node)
    graph.add_node("sql_generation_node", sql_generation_node)
    graph.add_node("sql_execution_node", sql_execution_node)
    graph.add_node("sql_result_judge_node", sql_result_judge_node)
    graph.add_node("rag_node", rag_node)
    graph.add_node("rag_judge_node", rag_judge_node)
    graph.add_node("fusion_node", fusion_node)

    # Entry point
    graph.add_edge(START, "orchestrator_node")

    # SQL path
    graph.add_conditional_edges(
        "orchestrator_node",
        route_after_orchestrator,
        {
            "sql_node": "schema_selection_node",
            "rag_node": "rag_node",
            "fusion_node": "fusion_node",
        },
    )

    graph.add_edge("schema_selection_node", "sql_generation_node")

    graph.add_conditional_edges(
        "sql_generation_node",
        route_after_sql_generation,
        {
            "sql_retry": "sql_generation_node",
            "sql_execute": "sql_execution_node",
            "sql_failed": "fusion_node",
        },
    )

    graph.add_conditional_edges(
        "sql_execution_node",
        route_after_sql_execution,
        {
            "sql_retry": "sql_generation_node",
            "sql_judge": "sql_result_judge_node",
            "sql_failed": "fusion_node",
        },
    )

    graph.add_conditional_edges(
        "sql_result_judge_node",
        route_after_sql_result_judge,
        {
            "sql_done": "fusion_node",
            "sql_retry": "sql_generation_node",
        },
    )

    # RAG path: rag_node -> rag_judge_node -> retry or done
    graph.add_edge("rag_node", "rag_judge_node")
    graph.add_conditional_edges(
        "rag_judge_node",
        route_after_rag_judge,
        {
            "rag_retry": "rag_node",
            "rag_done": "fusion_node",
        },
    )

    # Fusion -> END
    graph.add_edge("fusion_node", END)

    return graph


# Compile once at module level - reused across all requests
memory = MemorySaver()
rag_graph = build_graph().compile(checkpointer=memory)

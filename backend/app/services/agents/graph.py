from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.services.agents.types import AgentState
from app.services.agents.nodes.orchestrator import orchestrator_node
from app.services.agents.nodes.sql import sql_node, sql_judge_node
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


def route_after_sql_judge(state: AgentState) -> str:
    """
    After SQL judge evaluates the result, decide whether to retry SQL or proceed.
    """
    attempts = state["sql_attempts"]
    max_attempts = state["sql_max_attempts"]
    sufficient = state["sql_sufficient"]

    if sufficient:
        print("[Graph] SQL judge: sufficient=True. Proceeding to fusion check.")
        return "sql_done"
    elif attempts >= max_attempts:
        print(
            "[Graph] SQL judge: max attempts ({max_attempts}) reached. Proceeding anyway."
        )
        return "sql_done"
    else:
        print(
            "[Graph] SQL judge: sufficient=False. Retrying SQL (attempt {attempts + 1}/{max_attempts})."
        )
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
            "[Graph] RAG judge: max attempts ({max_attempts}) reached. Proceeding anyway."
        )
        return "rag_done"
    else:
        print(
            "[Graph] RAG judge: sufficient=False. Retrying RAG (attempt {attempts + 1}/{max_attempts})."
        )
        return "rag_retry"


def route_to_fusion(state: AgentState) -> str:
    """
    After both agents complete (or whichever were invoked), check if we are
    ready to proceed to fusion. Both invoked agents must be done before fusion runs.
    SQL and RAG run in parallel - this node is reached by each independently.
    LangGraph will call this after each parallel branch completes.
    Only proceed to fusion when all required agents are done.
    """
    sql_done = (not state["invoke_sql"]) or (
        state["sql_attempts"] > 0
        and (
            state["sql_sufficient"]
            or state["sql_attempts"] >= state["sql_max_attempts"]
        )
    )
    rag_done = (not state["invoke_rag"]) or (
        state["rag_attempts"] > 0
        and (
            state["rag_sufficient"]
            or state["rag_attempts"] >= state["rag_max_attempts"]
        )
    )

    if sql_done and rag_done:
        print("[Graph] All required agents complete. Routing to fusion.")
        return "fusion_node"
    else:
        print("[Graph] Waiting for agents. sql_done={sql_done}, rag_done={rag_done}")
        return END


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Add all nodes
    graph.add_node("orchestrator_node", orchestrator_node)
    graph.add_node("sql_node", sql_node)
    graph.add_node("sql_judge_node", sql_judge_node)
    graph.add_node("rag_node", rag_node)
    graph.add_node("rag_judge_node", rag_judge_node)
    graph.add_node("fusion_node", fusion_node)

    # Entry point
    graph.add_edge(START, "orchestrator_node")

    # After orchestrator - fan out to SQL and/or RAG in parallel
    graph.add_conditional_edges(
        "orchestrator_node",
        route_after_orchestrator,
        {
            "sql_node": "sql_node",
            "rag_node": "rag_node",
            "fusion_node": "fusion_node",
        },
    )

    # SQL path: sql_node -> sql_judge_node -> retry or done
    graph.add_edge("sql_node", "sql_judge_node")
    graph.add_conditional_edges(
        "sql_judge_node",
        route_after_sql_judge,
        {
            "sql_retry": "sql_node",
            "sql_done": "fusion_node",
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

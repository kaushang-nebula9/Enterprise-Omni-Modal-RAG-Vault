# Orchestrator node - LLM reasoning about which agents to invoke

import json
import re
from app.services.agents.types import AgentState
from app.services.rag_service import _get_async_anthropic_client


async def orchestrator_node(state: AgentState) -> dict:
    orchestrator_system = (
        "You are an intelligent query orchestrator for a multi-agent RAG system. "
        "You have access to two data sources:\n"
        "1. An external database (queried via SQL) - available when database_id is provided\n"
        "2. Documents and files (queried via semantic search) - available when document_id is provided\n\n"
        "Given the user's query and available sources, decide which agents to invoke.\n"
        "Respond ONLY with a JSON object in this exact format with no other text:\n"
        "{\n"
        '  "invoke_sql": true/false,\n'
        '  "invoke_rag": true/false,\n'
        '  "mode": "db_only" | "doc_only" | "cross_source",\n'
        '  "reasoning": "one sentence explaining your decision"\n'
        "}\n\n"
        "Rules:\n"
        "- If only database_id is available, always set invoke_sql=true, invoke_rag=false, mode=db_only\n"
        "- If only document_id is available, always set invoke_sql=false, invoke_rag=true, mode=doc_only\n"
        "- If both are available, reason about whether the query needs one or both sources\n"
        "- Set mode=cross_source only if the query explicitly requires information from both sources simultaneously\n"
        "- Set mode=db_only if the query is clearly about structured/tabular data even if document_id is available\n"
        "- Set mode=doc_only if the query is clearly about document content even if database_id is available\n"
        "- When in doubt with both sources available, prefer cross_source"
    )

    db_str = (
        f"YES (database_id={state['database_id']})" if state["database_id"] else "NO"
    )
    doc_str = (
        f"YES (document_id={state['document_id']})" if state["document_id"] else "NO"
    )

    orchestrator_prompt = f"""User Query: {state["query"]}

Available Sources:
- Database: {db_str}
- Documents/Files: {doc_str}

Conversation History (last 2 exchanges):
{state["conversation_history"][-500:] if state["conversation_history"] else "None"}

Decide which agents to invoke to best answer this query."""

    print(f"[Orchestrator] Query: {state['query'][:100]}")
    print(
        f"[Orchestrator] database_id={state['database_id']}, document_id={state['document_id']}"
    )

    # Safe default based on available sources
    if state["database_id"] and state["document_id"]:
        fallback = {
            "invoke_sql": True,
            "invoke_rag": True,
            "mode": "cross_source",
            "reasoning": "Fallback: both sources available",
        }
    elif state["database_id"]:
        fallback = {
            "invoke_sql": True,
            "invoke_rag": False,
            "mode": "db_only",
            "reasoning": "Fallback: only database available",
        }
    else:
        fallback = {
            "invoke_sql": False,
            "invoke_rag": True,
            "mode": "doc_only",
            "reasoning": "Fallback: only documents available",
        }

    plan = fallback
    try:
        client = _get_async_anthropic_client()
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=orchestrator_system,
            messages=[{"role": "user", "content": orchestrator_prompt}],
        )
        text = response.content[0].text.strip()

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)

        parsed = json.loads(text)
        if (
            "invoke_sql" in parsed
            and "invoke_rag" in parsed
            and "mode" in parsed
            and "reasoning" in parsed
        ):
            plan = parsed
    except Exception as e:
        print(f"[Orchestrator] Exception calling or parsing orchestrator LLM: {e}")

    print(
        f"[Orchestrator] Plan: mode={plan['mode']}, invoke_sql={plan['invoke_sql']}, invoke_rag={plan['invoke_rag']}"
    )
    print(f"[Orchestrator] Reasoning: {plan['reasoning']}")

    return {
        "invoke_sql": plan["invoke_sql"],
        "invoke_rag": plan["invoke_rag"],
        "mode": plan["mode"],
        "orchestrator_reasoning": plan["reasoning"],
        "sql_attempts": 0,
        "rag_attempts": 0,
        "sql_sufficient": False,
        "rag_sufficient": False,
        "sql_fix_instruction": "",
        "rag_fix_instruction": "",
        "sql_judge_reasoning": "",
        "rag_judge_reasoning": "",
        "progress_tokens": ["*Analyzing query and planning agent workflow...*\n\n"],
    }

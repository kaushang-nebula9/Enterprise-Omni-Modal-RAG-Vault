import os
import json
import uuid
import logging
import tempfile
from datetime import datetime, timezone

# Ensure matplotlib runs headlessly
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    HRFlowable,
    ListFlowable,
    ListItem,
    Preformatted,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from PIL import Image as PILImage
import redis

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.core.config import settings

# Import models to ensure mapping is resolved
import app.models.tenant
import app.models.user
import app.models.role
import app.models.document
import app.models.document_access_policy
import app.models.invite_token
import app.models.otp_verification
import app.models.query_session
import app.models.query_message
import app.models.query_citation
import app.models.refresh_token
import app.models.db_query_log
import app.models.generated_report
import app.models.report_agent_run  # noqa: F401

from app.models.generated_report import GeneratedReport
from app.models.report_agent_run import ReportAgentRun
from app.models.query_session import QuerySession
from app.models.query_message import QueryMessage
from app.models.query_citation import QueryCitation
from app.models.db_query_log import DBQueryLog
from app.models.user import User
from app.models.tenant import Tenant
from app.models.enums import MessageRole  # noqa: F401

logger = logging.getLogger(__name__)

DEFAULT_NEXT_STEP = {
    "gather": "cluster",
    "cluster": "synthesize",
    "synthesize": "assemble",
    "assemble": "render",
    "render": "deliver",
    "deliver": "done",
}


def get_anthropic_client():
    import anthropic

    api_key = settings.ANTHROPIC_API_KEY or "mock-key-for-testing"
    return anthropic.Anthropic(api_key=api_key)


def get_image_flowable(image_path, target_width):
    try:
        with PILImage.open(image_path) as img:
            w, h = img.size
        aspect = h / w
        target_height = target_width * aspect
        return Image(image_path, width=target_width, height=target_height)
    except Exception as e:
        logger.error(f"Failed to load image size: {e}")
        return None


def agent_controller(state: dict) -> dict:
    """
    Agent controller makes LLM call to decide what to do next based on the current state.
    """
    # 1. Hardcoded guards for Gather step validation
    if state["current_step"] == "gather" and state["gathered_data"]:
        gd = state["gathered_data"]
        qa_pairs_count = gd.get("qa_pairs_count", 0)
        messages_count = gd.get("messages_count", 0)
        messages = gd.get("messages", [])

        if qa_pairs_count == 0:
            return {
                "next_step": "abort",
                "reasoning": "Session has no question-answer pairs to generate a report from",
                "retry_current": False,
                "retry_reason": None,
                "adjustments": [],
            }

        if messages_count > 0:
            roles = {m.get("role") for m in messages if m.get("role")}
            if len(roles) == 1:
                return {
                    "next_step": "abort",
                    "reasoning": "All messages in the session are from one role",
                    "retry_current": False,
                    "retry_reason": None,
                    "adjustments": [],
                }

    # Hardcoded guard for successful delivery to terminate agent loop with success (done)
    if state["current_step"] == "deliver" and "deliver" in state["completed_steps"]:
        return {
            "next_step": "done",
            "reasoning": "Report was successfully delivered.",
            "retry_current": False,
            "retry_reason": None,
            "adjustments": [],
        }

    # 2. Summarize state to stay within token limits
    summarized_state = {
        "report_id": state["report_id"],
        "session_id": state["session_id"],
        "current_step": state["current_step"],
        "completed_steps": state["completed_steps"],
        "failed_steps": state["failed_steps"],
        "retry_counts": state["retry_counts"],
        "chart_render_failures": state["chart_render_failures"],
        "skipped_sections": state["skipped_sections"],
    }

    if state.get("gathered_data"):
        gd = state["gathered_data"]
        summarized_state["gathered_data_summary"] = {
            "messages_count": gd.get("messages_count", 0),
            "qa_pairs_count": gd.get("qa_pairs_count", 0),
            "charts_count": len(gd.get("charts", [])),
            "cited_documents_count": len(gd.get("cited_documents", [])),
            "db_queries_count": len(gd.get("db_queries", [])),
            "has_charts": gd.get("has_charts", False),
            "has_db_queries": gd.get("has_db_queries", False),
            "has_cited_documents": gd.get("has_cited_documents", False),
        }

    if state.get("clusters"):
        summarized_state["clusters_summary"] = {
            "clusters_count": len(state["clusters"].get("clusters", []))
        }

    if state.get("synthesized_content"):
        sc = state["synthesized_content"]
        summarized_state["synthesized_content_summary"] = {
            "title": sc.get("title"),
            "has_executive_summary": bool(sc.get("executive_summary")),
            "key_findings_count": len(sc.get("key_findings", [])),
            "detailed_findings_count": len(sc.get("detailed_findings", [])),
        }

    if state.get("assembled_content"):
        ac = state["assembled_content"]
        summarized_state["assembled_content_summary"] = {
            "title": ac.get("title"),
            "chart_image_paths_count": len(ac.get("chart_image_paths", [])),
            "chart_render_failures_count": len(ac.get("chart_render_failures", [])),
        }

    # If previous attempt failed, include validation error details in the prompt
    previous_error = None
    if state["current_step"] in state["failed_steps"] and state["decisions"]:
        # Find why it failed
        last_decision = state["decisions"][-1]
        previous_error = (
            last_decision.get("retry_reason") or "Previous attempt failed validation."
        )

    prompt = f"""You are the controller agent for an automated AI report generation system. Your task is to analyze the current state of report generation and decide the next course of action.

Current Step: {state["current_step"]}
Previous attempt failed: {"Yes" if previous_error else "No"}
{"Failure Reason: " + previous_error if previous_error else ""}

Summarized System State:
{json.dumps(summarized_state, indent=2)}

You can decide to:
1. Proceed to the next step.
2. Retry the current step if it failed, optionally specifying feedback/adjustments.
3. Abort the report generation if there are critical errors or missing data.
4. Conclude the report generation successfully by transitioning to "done".

Return ONLY a JSON object matching this exact schema:
{{
  "next_step": "cluster | synthesize | assemble | render | deliver | done | abort",
  "reasoning": "short explanation of why",
  "retry_current": false,
  "retry_reason": null,
  "adjustments": []
}}
"""

    fallback_decision = {
        "next_step": DEFAULT_NEXT_STEP.get(state["current_step"], "abort"),
        "reasoning": "Failed to parse controller response. Falling back to default step sequence.",
        "retry_current": False,
        "retry_reason": None,
        "adjustments": [],
    }

    try:
        client = get_anthropic_client()
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        decision = json.loads(content)
        return decision
    except Exception as e:
        logger.error(f"Error in agent_controller: {e}", exc_info=True)
        return fallback_decision


def gather_step(state: dict, db) -> dict:
    """
    Step 1 - Gather data from database. Pure query logic.
    """
    try:
        session_id = uuid.UUID(state["session_id"])
        user_id = uuid.UUID(state["generated_by"])

        # 1. Fetch messages
        messages = (
            db.query(QueryMessage)
            .filter(QueryMessage.session_id == session_id)
            .order_by(QueryMessage.created_at.asc())
            .all()
        )

        messages_list = []
        for m in messages:
            messages_list.append(
                {
                    "id": str(m.id),
                    "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "chart_spec": m.chart_spec,
                }
            )

        # 2. Extract Q&A pairs
        qa_pairs = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            if role == "user":
                question = msg.content
                question_id = str(msg.id)
                answer = None
                answer_id = None
                chart_spec = None

                if i + 1 < len(messages):
                    next_msg = messages[i + 1]
                    next_role = (
                        next_msg.role.value
                        if hasattr(next_msg.role, "value")
                        else str(next_msg.role)
                    )
                    if next_role == "assistant":
                        answer = next_msg.content
                        answer_id = str(next_msg.id)
                        chart_spec = next_msg.chart_spec
                        i += 2
                        qa_pairs.append(
                            {
                                "question": question,
                                "answer": answer,
                                "chart_spec": chart_spec,
                                "message_ids": [question_id, answer_id],
                            }
                        )
                        continue

                i += 1
                qa_pairs.append(
                    {
                        "question": question,
                        "answer": None,
                        "chart_spec": None,
                        "message_ids": [question_id],
                    }
                )
            else:
                i += 1

        # 3. Extract charts
        charts = []
        for m in messages:
            if m.chart_spec:
                charts.append({"message_id": str(m.id), "chart_spec": m.chart_spec})

        # 4. Extract citations / cited sources
        citations = (
            db.query(QueryCitation)
            .join(QueryMessage, QueryCitation.message_id == QueryMessage.id)
            .filter(QueryMessage.session_id == session_id)
            .all()
        )

        docs_map = {}
        for citation in citations:
            if citation.document_id:
                doc_id = str(citation.document_id)
                doc_name = (
                    citation.document.filename
                    if citation.document
                    else "Unnamed Document"
                )
                page = citation.page_number
                if doc_id not in docs_map:
                    docs_map[doc_id] = {
                        "doc_id": doc_id,
                        "doc_name": doc_name,
                        "pages": set(),
                    }
                if page is not None:
                    docs_map[doc_id]["pages"].add(page)

        cited_documents = []
        for doc_id, data in docs_map.items():
            cited_documents.append(
                {
                    "doc_id": doc_id,
                    "doc_name": data["doc_name"],
                    "pages": sorted(list(data["pages"])),
                }
            )

        # 5. Extract DB queries
        db_queries = []
        session = db.query(QuerySession).filter(QuerySession.id == session_id).first()
        if session and session.db_connection_id:
            sql_to_question = {}
            for idx, msg in enumerate(messages):
                role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
                if role == "assistant" and msg.generated_sql:
                    # Find previous user question
                    user_q = None
                    for prev_idx in range(idx - 1, -1, -1):
                        prev_msg = messages[prev_idx]
                        prev_role = (
                            prev_msg.role.value
                            if hasattr(prev_msg.role, "value")
                            else str(prev_msg.role)
                        )
                        if prev_role == "user":
                            user_q = prev_msg.content
                            break
                    sql_to_question[msg.generated_sql] = user_q or "Database Query"

            msg_sqls = [m.generated_sql for m in messages if m.generated_sql]
            if msg_sqls:
                logs = (
                    db.query(DBQueryLog)
                    .filter(
                        DBQueryLog.user_id == user_id,
                        DBQueryLog.db_connection_id == session.db_connection_id,
                        DBQueryLog.generated_sql.in_(msg_sqls),
                    )
                    .all()
                )
                unique_sqls = list(
                    set([log.generated_sql for log in logs if log.generated_sql])
                )
                for sql in unique_sqls:
                    db_queries.append(
                        {
                            "question": sql_to_question.get(sql, "Database Query"),
                            "sql": sql,
                        }
                    )

        data = {
            "messages": messages_list,
            "qa_pairs": qa_pairs,
            "charts": charts,
            "cited_documents": cited_documents,
            "db_queries": db_queries,
            "has_charts": len(charts) > 0,
            "has_db_queries": len(db_queries) > 0,
            "has_cited_documents": len(cited_documents) > 0,
            "messages_count": len(messages_list),
            "qa_pairs_count": len(qa_pairs),
        }
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        logger.error(f"Error in gather_step: {e}", exc_info=True)
        return {"success": False, "data": None, "error": str(e)}


def cluster_step(state: dict, db) -> dict:
    """
    Step 2 - Cluster Q&A pairs by topic using Claude Haiku.
    """
    try:
        qa_pairs = state["gathered_data"]["qa_pairs"]
        formatted_pairs = [
            {"index": i, "question": p["question"], "answer": p["answer"]}
            for i, p in enumerate(qa_pairs)
        ]

        feedback = ""
        # Look for validation error in previous decision
        if state["retry_counts"]["cluster"] > 0 and state["decisions"]:
            last_decision = state["decisions"][-1]
            retry_reason = (
                last_decision.get("retry_reason")
                or "Previous attempt failed validation."
            )
            feedback = f"\n\nYour previous response failed validation: {retry_reason}. Fix it and return valid JSON."

        prompt = f"""You are a report structuring assistant. Group the following question-answer pairs from a chat session into coherent topic clusters for a business report.

Return ONLY a JSON object with this exact structure, no other text:
{{
  "clusters": [
    {{
      "cluster_id": 1,
      "topic_label": "short topic name",
      "topic_description": "one sentence describing this cluster",
      "qa_pair_indices": [0, 2, 4]
    }}
  ]
}}

Rules:
- Every Q&A pair must appear in exactly one cluster
- Minimum 1 cluster, maximum 6 clusters
- qa_pair_indices are 0-based indices into the input list
- topic_label must be 2-5 words
- Do not include any text outside the JSON object

Q&A pairs (indexed):
{json.dumps(formatted_pairs, indent=2)}{feedback}
"""
        client = get_anthropic_client()
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        result = json.loads(content)

        # Validation checks
        if "clusters" not in result or not isinstance(result["clusters"], list):
            return {"success": False, "data": None, "error": "Missing 'clusters' array"}

        all_indices = set()
        N = len(qa_pairs)
        for cluster in result["clusters"]:
            for field in [
                "cluster_id",
                "topic_label",
                "topic_description",
                "qa_pair_indices",
            ]:
                if field not in cluster:
                    return {
                        "success": False,
                        "data": None,
                        "error": f"Cluster missing field '{field}'",
                    }

            indices = cluster["qa_pair_indices"]
            for idx in indices:
                if not isinstance(idx, int) or idx < 0 or idx >= N:
                    return {
                        "success": False,
                        "data": None,
                        "error": f"Index {idx} is out of bounds [0, {N - 1}]",
                    }
                if idx in all_indices:
                    return {
                        "success": False,
                        "data": None,
                        "error": f"Duplicate index {idx} found across clusters",
                    }
                all_indices.add(idx)

        if len(all_indices) != N:
            missing = set(range(N)) - all_indices
            return {
                "success": False,
                "data": None,
                "error": f"Some Q&A pairs are not clustered. Missing indices: {list(missing)}",
            }

        return {"success": True, "data": result, "error": None}
    except Exception as e:
        logger.error(f"Error in cluster_step: {e}", exc_info=True)
        return {"success": False, "data": None, "error": str(e)}


def synthesize_step(state: dict, db) -> dict:
    """
    Step 3 - Synthesize the clustered Q&A pairs into report sections.
    """
    try:
        qa_pairs = state["gathered_data"]["qa_pairs"]
        cited_documents = state["gathered_data"]["cited_documents"]
        db_queries = state["gathered_data"]["db_queries"]

        clustered_content = []
        for cluster in state["clusters"]["clusters"]:
            indices = cluster["qa_pair_indices"]
            cluster_qa = []
            for idx in indices:
                if idx < len(qa_pairs):
                    cluster_qa.append(qa_pairs[idx])
            clustered_content.append(
                {
                    "cluster_id": cluster["cluster_id"],
                    "topic_label": cluster["topic_label"],
                    "topic_description": cluster["topic_description"],
                    "qa_pairs": cluster_qa,
                }
            )

        feedback = ""
        if state["retry_counts"]["synthesize"] > 0 and state["decisions"]:
            last_decision = state["decisions"][-1]
            retry_reason = (
                last_decision.get("retry_reason")
                or "Previous attempt failed validation."
            )
            feedback = f"\n\nYour previous response failed validation: {retry_reason}. Fix it and return valid JSON."

        prompt = f"""You are a professional business report writer. Based on the clustered chat session content below, write all sections of a business intelligence report.

Return ONLY a JSON object with this exact structure, no other text:
{{
  "title": "concise report title derived from the session content (max 10 words)",
  "executive_summary": "2-3 paragraph synthesis of the session's overall findings and key takeaways",
  "key_findings": [
    "finding 1 as a complete sentence",
    "finding 2 as a complete sentence"
  ],
  "detailed_findings": [
    {{
      "cluster_id": 1,
      "section_title": "section heading",
      "narrative": "synthesized narrative for this topic cluster, 1-3 paragraphs, written as coherent prose not bullet points",
      "citations": ["document name page X", "table name"]
    }}
  ]
}}

Rules:
- key_findings must have between 3 and 6 items
- detailed_findings must have one entry per cluster, matching cluster_ids exactly
- narrative must be prose, not bullet points
- Do not include any text outside the JSON object
- Write in a formal business report tone

Session clusters:
{json.dumps(clustered_content, indent=2)}

Cited sources available:
{json.dumps(cited_documents, indent=2)}

DB tables queried (if any):
{json.dumps(db_queries, indent=2)}{feedback}
"""
        client = get_anthropic_client()
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        result = json.loads(content)

        # Validation checks
        if not result.get("title"):
            return {"success": False, "data": None, "error": "Missing or empty 'title'"}
        if not result.get("executive_summary"):
            return {
                "success": False,
                "data": None,
                "error": "Missing or empty 'executive_summary'",
            }

        key_findings = result.get("key_findings", [])
        if (
            not isinstance(key_findings, list)
            or len(key_findings) < 3
            or len(key_findings) > 6
        ):
            return {
                "success": False,
                "data": None,
                "error": f"key_findings count must be between 3 and 6 (got {len(key_findings)})",
            }

        detailed_findings = result.get("detailed_findings", [])
        cluster_ids_input = {c["cluster_id"] for c in state["clusters"]["clusters"]}
        cluster_ids_output = {d.get("cluster_id") for d in detailed_findings}

        if (
            len(detailed_findings) != len(state["clusters"]["clusters"])
            or cluster_ids_input != cluster_ids_output
        ):
            return {
                "success": False,
                "data": None,
                "error": "detailed_findings must have one entry per cluster, matching cluster_ids exactly",
            }

        return {"success": True, "data": result, "error": None}
    except Exception as e:
        logger.error(f"Error in synthesize_step: {e}", exc_info=True)
        return {"success": False, "data": None, "error": str(e)}


def assemble_step(state: dict, db) -> dict:
    """
    Step 4 - Assemble report and draw charts using matplotlib.
    """
    try:
        report_id = state["report_id"]
        temp_dir = os.path.join(tempfile.gettempdir(), f"report_{report_id}")
        os.makedirs(temp_dir, exist_ok=True)

        rendered_charts_paths = {}

        # Render charts using matplotlib
        for chart in state["gathered_data"]["charts"]:
            msg_id = chart["message_id"]
            spec = chart["chart_spec"]
            chart_image_path = os.path.join(temp_dir, f"chart_{msg_id}.png")

            try:
                chart_type = spec.get("chart_type")
                data = spec.get("data", [])
                x_key = spec.get("x_key")
                name_key = spec.get("name_key")
                value_key = spec.get("value_key")

                # Extract y_keys or series keys
                y_keys = spec.get("y_keys")
                series_list = spec.get("series", [])

                if not y_keys:
                    if series_list:
                        if isinstance(series_list[0], dict):
                            y_keys = [s.get("key") for s in series_list if s.get("key")]
                        else:
                            y_keys = [str(s) for s in series_list]
                    else:
                        y_keys = []

                # Fallback: scan for numeric columns in data if y_keys is still empty
                if not y_keys and data:
                    first_item = data[0]
                    for k, v in first_item.items():
                        if k != x_key and isinstance(v, (int, float)):
                            y_keys.append(k)
                        elif k != x_key:
                            try:
                                float(v)
                                y_keys.append(k)
                            except (ValueError, TypeError):
                                pass

                # Map series details (names, colors) for plotting if available
                series_map = {}
                if series_list and isinstance(series_list[0], dict):
                    for s in series_list:
                        k = s.get("key")
                        if k:
                            series_map[k] = s

                if not data:
                    raise ValueError("Empty data list for chart")

                plt.figure(figsize=(6, 4))

                if chart_type == "bar":
                    x = range(len(data))
                    width = 0.8 / len(y_keys) if y_keys else 0.8
                    for idx, y_key in enumerate(y_keys):
                        y_vals = [float(d.get(y_key, 0) or 0) for d in data]
                        offset = (idx - len(y_keys) / 2 + 0.5) * width
                        s_info = series_map.get(y_key, {})
                        plt.bar(
                            [pos + offset for pos in x],
                            y_vals,
                            width,
                            label=s_info.get("name", y_key),
                            color=s_info.get("color"),
                        )
                    plt.xticks(
                        x,
                        [str(d.get(x_key, "")) for d in data],
                        rotation=45,
                        ha="right",
                    )
                    if y_keys:
                        plt.legend()

                elif chart_type == "line":
                    x_labels = [str(d.get(x_key, "")) for d in data]
                    for y_key in y_keys:
                        y_vals = [float(d.get(y_key, 0) or 0) for d in data]
                        s_info = series_map.get(y_key, {})
                        plt.plot(
                            x_labels,
                            y_vals,
                            marker="o",
                            label=s_info.get("name", y_key),
                            color=s_info.get("color"),
                        )
                    plt.xticks(rotation=45, ha="right")
                    if y_keys:
                        plt.legend()

                elif chart_type == "area":
                    x_labels = [str(d.get(x_key, "")) for d in data]
                    for y_key in y_keys:
                        y_vals = [float(d.get(y_key, 0) or 0) for d in data]
                        s_info = series_map.get(y_key, {})
                        plt.plot(
                            x_labels,
                            y_vals,
                            label=s_info.get("name", y_key),
                            color=s_info.get("color"),
                        )
                        plt.fill_between(
                            x_labels, y_vals, alpha=0.3, color=s_info.get("color")
                        )
                    plt.xticks(rotation=45, ha="right")
                    if y_keys:
                        plt.legend()

                elif chart_type == "pie":
                    n_key = name_key or x_key
                    v_key = value_key or (y_keys[0] if y_keys else None)
                    if not n_key or not v_key:
                        raise ValueError(
                            f"Pie chart missing keys. name_key: {n_key}, value_key: {v_key}"
                        )
                    labels = [str(d.get(n_key, "")) for d in data]
                    values = [float(d.get(v_key, 0) or 0) for d in data]
                    if sum(values) == 0:
                        raise ValueError(
                            "All values for the pie chart are zero. Cannot render pie chart."
                        )
                    plt.pie(values, labels=labels, autopct="%1.1f%%")

                else:
                    raise ValueError(f"Unsupported chart type: {chart_type}")

                plt.title(spec.get("title", "Chart"))
                plt.tight_layout()
                plt.savefig(chart_image_path, dpi=300, bbox_inches="tight")
                plt.close()
                rendered_charts_paths[msg_id] = chart_image_path

            except Exception as chart_err:
                logger.error(
                    f"Failed to render chart for message {msg_id}: {chart_err}",
                    exc_info=True,
                )
                state["chart_render_failures"].append(
                    f"Chart {msg_id} failed: {chart_err}"
                )

        # Match Q&A pair index back to message IDs to locate which cluster needs which chart
        qa_pairs = state["gathered_data"]["qa_pairs"]
        cluster_charts = {}
        for cluster in state["clusters"]["clusters"]:
            c_id = cluster["cluster_id"]
            indices = cluster["qa_pair_indices"]
            # Find all message_ids in this cluster
            c_message_ids = []
            for idx in indices:
                if idx < len(qa_pairs):
                    c_message_ids.extend(qa_pairs[idx].get("message_ids", []))
            # Check if any message in this cluster has a successfully rendered chart
            for m_id in c_message_ids:
                if m_id in rendered_charts_paths:
                    cluster_charts[c_id] = rendered_charts_paths[m_id]
                    break

        detailed_findings_assembled = []
        for section in state["synthesized_content"]["detailed_findings"]:
            c_id = section["cluster_id"]
            section_copy = dict(section)
            section_copy["chart_image_path"] = cluster_charts.get(c_id)
            detailed_findings_assembled.append(section_copy)

        # Retrieve user and tenant names from DB
        user_name = "Unknown User"
        tenant_name = "Unknown Tenant"
        user_id = uuid.UUID(state["generated_by"])
        tenant_id = uuid.UUID(state["tenant_id"])

        user_row = db.query(User).filter(User.id == user_id).first()
        if user_row:
            user_name = user_row.full_name

        tenant_row = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant_row:
            tenant_name = tenant_row.name

        data = {
            "title": state["synthesized_content"]["title"],
            "generated_by": user_name,
            "tenant_name": tenant_name,
            "generation_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "executive_summary": state["synthesized_content"]["executive_summary"],
            "key_findings": state["synthesized_content"]["key_findings"],
            "detailed_findings": detailed_findings_assembled,
            "chart_image_paths": list(rendered_charts_paths.values()),
            "cited_documents": state["gathered_data"]["cited_documents"],
            "db_queries": state["gathered_data"]["db_queries"],
            "has_charts": state["gathered_data"]["has_charts"],
            "has_db_queries": state["gathered_data"]["has_db_queries"],
            "chart_render_failures": state["chart_render_failures"],
        }
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        logger.error(f"Error in assemble_step: {e}", exc_info=True)
        return {"success": False, "data": None, "error": str(e)}


def render_step(state: dict, db) -> dict:
    """
    Step 5 - Build the PDF using ReportLab Platypus.
    """
    try:
        report_id = state["report_id"]
        assembled = state["assembled_content"]

        pdf_filename = f"report_{report_id}.pdf"
        pdf_path = os.path.join(settings.REPORTS_DIR, pdf_filename)
        os.makedirs(settings.REPORTS_DIR, exist_ok=True)

        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=letter,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54,
        )

        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=34,
            textColor=HexColor("#1e3a5f"),
            alignment=0,
            spaceAfter=20,
        )

        h1_style = ParagraphStyle(
            "ReportH1",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=HexColor("#1e3a5f"),
            spaceBefore=15,
            spaceAfter=10,
            keepWithNext=True,
        )

        h2_style = ParagraphStyle(
            "ReportH2",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=HexColor("#1e3a5f"),
            spaceBefore=12,
            spaceAfter=8,
            keepWithNext=True,
        )

        body_style = ParagraphStyle(
            "ReportBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=HexColor("#000000"),
            spaceAfter=10,
        )

        meta_style = ParagraphStyle(
            "ReportMeta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=HexColor("#555555"),
            spaceAfter=5,
        )

        citation_style = ParagraphStyle(
            "ReportCitation",
            parent=styles["Italic"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10,
            textColor=HexColor("#555555"),
            spaceAfter=10,
        )

        pre_style = ParagraphStyle(
            "ReportPre",
            parent=styles["Normal"],
            fontName="Courier",
            fontSize=8,
            leading=10,
            textColor=HexColor("#000000"),
            backColor=HexColor("#f5f5f5"),
            borderPadding=6,
            spaceAfter=10,
        )

        story = []

        # 1. Cover Page
        story.append(Spacer(1, 40))
        story.append(Paragraph(assembled["title"], title_style))
        story.append(Spacer(1, 20))
        story.append(Paragraph(f"Date: {assembled['generation_date']}", meta_style))
        story.append(
            Paragraph(f"Generated by: {assembled['generated_by']}", meta_style)
        )
        story.append(Paragraph(f"Organization: {assembled['tenant_name']}", meta_style))
        story.append(Spacer(1, 20))
        story.append(
            HRFlowable(
                width="100%", thickness=2, color=HexColor("#1e3a5f"), spaceAfter=30
            )
        )

        # 2. Executive Summary
        story.append(Paragraph("Executive Summary", h1_style))
        # Split executive summary paragraphs
        exec_paragraphs = [
            p.strip() for p in assembled["executive_summary"].split("\n") if p.strip()
        ]
        for p in exec_paragraphs:
            story.append(Paragraph(p, body_style))
        story.append(Spacer(1, 15))

        # 3. Key Findings
        story.append(Paragraph("Key Findings", h1_style))
        bullet_items = [
            ListItem(
                Paragraph(finding, body_style),
                leftIndent=20,
                bulletColor=HexColor("#1e3a5f"),
            )
            for finding in assembled["key_findings"]
        ]
        story.append(ListFlowable(bullet_items, bulletType="bullet", start="circle"))
        story.append(Spacer(1, 15))

        # 4. Detailed Findings
        story.append(Paragraph("Detailed Findings", h1_style))
        for section in assembled["detailed_findings"]:
            story.append(Paragraph(section["section_title"], h2_style))

            # Print paragraphs of section narrative
            paragraphs = [
                p.strip() for p in section["narrative"].split("\n") if p.strip()
            ]
            for p in paragraphs:
                story.append(Paragraph(p, body_style))

            # Display inline chart if present
            chart_path = section.get("chart_image_path")
            if chart_path and os.path.exists(chart_path):
                img_flowable = get_image_flowable(chart_path, 400)
                if img_flowable:
                    story.append(Spacer(1, 5))
                    story.append(img_flowable)
                    story.append(Spacer(1, 5))

            # Display citations
            if section.get("citations"):
                cits_str = ", ".join(section["citations"])
                story.append(Paragraph(f"Sources: {cits_str}", citation_style))

        # 5. Sources Referenced
        if assembled["cited_documents"]:
            story.append(Paragraph("Sources Referenced", h1_style))
            doc_items = []
            for doc in assembled["cited_documents"]:
                pages_str = (
                    f" (pages: {', '.join(map(str, doc['pages']))})"
                    if doc["pages"]
                    else ""
                )
                doc_items.append(
                    ListItem(
                        Paragraph(f"{doc['doc_name']}{pages_str}", body_style),
                        leftIndent=20,
                        bulletColor=HexColor("#1e3a5f"),
                    )
                )
            story.append(ListFlowable(doc_items, bulletType="bullet"))
            story.append(Spacer(1, 15))

        # 6. Methodology Note
        story.append(Paragraph("Methodology Note", h1_style))
        story.append(
            Paragraph(
                "This report was generated automatically from a chat session using AI-assisted analysis. "
                "Content is derived from retrieved documents and database queries within the scope of the session. "
                "All findings should be independently verified before use in business decisions.",
                body_style,
            )
        )
        story.append(Spacer(1, 15))

        # 7. Query Log Appendix
        if assembled["has_db_queries"] and assembled["db_queries"]:
            story.append(Paragraph("Query Log Appendix", h1_style))
            for item in assembled["db_queries"]:
                question = item.get("question", "Database Query")
                sql = item.get("sql", "")
                if sql:
                    story.append(Paragraph(f'Query for: "{question}"', h2_style))
                    story.append(Preformatted(sql, pre_style))
                    story.append(Spacer(1, 5))

        doc.build(story)
        return {"success": True, "data": pdf_path, "error": None}
    except Exception as e:
        logger.error(f"Error in render_step: {e}", exc_info=True)
        return {"success": False, "data": None, "error": str(e)}


def deliver_step(state: dict, db) -> dict:
    """
    Step 6 - Deliver. Update DB status and send SSE notification via Redis.
    """
    try:
        report_id = uuid.UUID(state["report_id"])
        session_id = uuid.UUID(state["session_id"])
        user_id = uuid.UUID(state["generated_by"])
        pdf_path = state["pdf_path"]
        title = state["synthesized_content"]["title"]

        # 1. Update report in DB
        report = (
            db.query(GeneratedReport).filter(GeneratedReport.id == report_id).first()
        )
        if not report:
            raise ValueError(f"Report not found in DB: {report_id}")

        report.status = "complete"
        report.storage_path = pdf_path
        report.completed_at = datetime.now(timezone.utc)
        report.title = title
        db.commit()

        # 2. Push SSE notification to Redis notifications:{user_id} channel
        try:
            r = redis.from_url(settings.REDIS_URL)
            payload = {
                "type": "report_ready",
                "report_id": str(report_id),
                "title": str(title),
                "session_id": str(session_id),
            }
            r.publish(f"notifications:{user_id}", json.dumps(payload))
            logger.info(f"Published report_ready to channel notifications:{user_id}")
        except Exception as redis_err:
            logger.error(f"Redis notification failed: {redis_err}", exc_info=True)

        return {"success": True, "data": "Report delivered", "error": None}
    except Exception as e:
        logger.error(f"Error in deliver_step: {e}", exc_info=True)
        return {"success": False, "data": None, "error": str(e)}


@celery_app.task(name="run_report_generation_agent", bind=True, max_retries=0)
def run_report_generation_agent(self, report_id: str):
    """
    Celery task that runs the Report Generation Agent.
    """
    logger.info(f"Starting Report Generation Agent task for report_id: {report_id}")
    db = SessionLocal()
    current_step = "gather"

    try:
        # Load the report details to construct initial state
        report = (
            db.query(GeneratedReport)
            .filter(GeneratedReport.id == uuid.UUID(report_id))
            .first()
        )
        if not report:
            logger.error(f"Report not found in database: {report_id}")
            return

        state = {
            "report_id": str(report.id),
            "session_id": str(report.session_id),
            "tenant_id": str(report.tenant_id),
            "generated_by": str(report.generated_by),
            "current_step": "gather",
            "completed_steps": [],
            "failed_steps": [],
            "retry_counts": {
                "gather": 0,
                "cluster": 0,
                "synthesize": 0,
                "assemble": 0,
                "render": 0,
                "deliver": 0,
            },
            "gathered_data": None,
            "clusters": None,
            "synthesized_content": None,
            "assembled_content": None,
            "pdf_path": None,
            "decisions": [],
            "chart_render_failures": [],
            "skipped_sections": [],
        }

        steps_map = {
            "gather": gather_step,
            "cluster": cluster_step,
            "synthesize": synthesize_step,
            "assemble": assemble_step,
            "render": render_step,
            "deliver": deliver_step,
        }

        # Run the agent loop
        while current_step not in ("done", "abort"):
            state["current_step"] = current_step
            step_func = steps_map.get(current_step)

            if not step_func:
                logger.error(f"Unknown step: {current_step}")
                break

            logger.info(f"Agent running step: {current_step}")

            # Measure step execution time
            start_time = datetime.now(timezone.utc)
            result = step_func(state, db)
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # Log result in report_agent_runs table
            try:
                run = ReportAgentRun(
                    report_id=uuid.UUID(report_id),
                    step_name=current_step,
                    status="success" if result["success"] else "failed",
                    duration_ms=duration_ms,
                    error_message=result.get("error"),
                )
                db.add(run)
                db.commit()
            except Exception as run_db_err:
                logger.error(
                    f"Failed to write agent run log: {run_db_err}", exc_info=True
                )

            # Update loop state
            if result["success"]:
                if current_step not in state["completed_steps"]:
                    state["completed_steps"].append(current_step)
                if current_step in state["failed_steps"]:
                    state["failed_steps"].remove(current_step)

                # Store result data
                if current_step == "gather":
                    state["gathered_data"] = result["data"]
                elif current_step == "cluster":
                    state["clusters"] = result["data"]
                elif current_step == "synthesize":
                    state["synthesized_content"] = result["data"]
                elif current_step == "assemble":
                    state["assembled_content"] = result["data"]
                elif current_step == "render":
                    state["pdf_path"] = result["data"]
            else:
                if current_step not in state["failed_steps"]:
                    state["failed_steps"].append(current_step)

            # Run controller LLM decision
            decision = agent_controller(state)
            state["decisions"].append(decision)

            logger.info(f"Agent controller decision: {json.dumps(decision)}")

            # Process decision
            if (
                decision.get("retry_current")
                and state["retry_counts"][current_step] < 2
            ):
                state["retry_counts"][current_step] += 1
                logger.info(
                    f"Retrying step '{current_step}' (Attempt {state['retry_counts'][current_step] + 1})"
                )
                continue

            if decision.get("next_step") == "abort":
                logger.error(f"Report generation aborted: {decision.get('reasoning')}")
                try:
                    report_row = (
                        db.query(GeneratedReport)
                        .filter(GeneratedReport.id == uuid.UUID(report_id))
                        .first()
                    )
                    if report_row and report_row.status != "complete":
                        report_row.status = "failed"
                        db.commit()
                except Exception as abort_db_err:
                    logger.error(f"Failed to update aborted status: {abort_db_err}")
                break

            current_step = decision.get("next_step", "abort")

    except Exception as exc:
        logger.error(
            f"Fatal unhandled exception in Report Generation Agent loop: {exc}",
            exc_info=True,
        )
        # Mark report failed
        try:
            report_row = (
                db.query(GeneratedReport)
                .filter(GeneratedReport.id == uuid.UUID(report_id))
                .first()
            )
            if report_row and report_row.status != "complete":
                report_row.status = "failed"
                db.commit()
        except Exception as db_err:
            logger.error(f"Failed to update report status to failed: {db_err}")

        # Log step failure in run table
        try:
            run = ReportAgentRun(
                report_id=uuid.UUID(report_id),
                step_name=current_step,
                status="failed",
                error_message=str(exc),
            )
            db.add(run)
            db.commit()
        except Exception as db_err:
            logger.error(f"Failed to write step run failure: {db_err}")

    finally:
        db.close()

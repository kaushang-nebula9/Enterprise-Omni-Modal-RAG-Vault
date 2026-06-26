from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.core.config import settings
from app.models.evaluation import EvaluationRun, EvaluationResult
from app.models.query_log import QueryLog
from app.models.enums import EvaluationStatus, NotificationType
from app.services.notification_service import create_notification
from anthropic import Anthropic
import logging
import json
import re
import uuid
from datetime import datetime, timezone

# Ensure all models are loaded
import app.models.tenant            # noqa: F401
import app.models.user              # noqa: F401
import app.models.role              # noqa: F401
import app.models.document          # noqa: F401
import app.models.document_access_policy  # noqa: F401
import app.models.invite_token      # noqa: F401
import app.models.otp_verification  # noqa: F401
import app.models.query_session     # noqa: F401
import app.models.query_message     # noqa: F401
import app.models.query_citation    # noqa: F401
import app.models.refresh_token     # noqa: F401
import app.models.query_log         # noqa: F401
import app.models.evaluation        # noqa: F401
import app.models.notification      # noqa: F401

logger = logging.getLogger(__name__)

JUDGE_PROMPT_TEMPLATE = """You are evaluating an AI-generated answer from a RAG system for quality.

Source context (retrieved chunks):
{contexts}

Question asked:
{question}

Generated answer:
{answer}

Evaluate two things:
1. Faithfulness: is the answer fully supported by the source context? Identify any claims NOT supported by the context.
2. Retrieval relevance: were the retrieved chunks actually relevant and useful for answering this question?

Respond ONLY with valid JSON in this exact format, no other text:
{{
  "faithfulness_score": <integer 0-100>,
  "relevance_score": <integer 0-100>,
  "unsupported_claims": ["list of specific claims not supported by context, empty list if none"],
  "reasoning": "brief explanation covering both scores"
}}"""

def clean_and_parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()
            
    # Try parsing
    data = json.loads(text)
    
    # Validation & parsing fields
    faithfulness_score = int(data.get("faithfulness_score", 0))
    relevance_score = int(data.get("relevance_score", 0))
    
    unsupported_claims = data.get("unsupported_claims", [])
    if not isinstance(unsupported_claims, list):
        unsupported_claims = [str(unsupported_claims)]
        
    reasoning = str(data.get("reasoning", ""))
    
    # Clamp scores
    faithfulness_score = max(0, min(100, faithfulness_score))
    relevance_score = max(0, min(100, relevance_score))
    
    return {
        "faithfulness_score": faithfulness_score,
        "relevance_score": relevance_score,
        "unsupported_claims": unsupported_claims,
        "reasoning": reasoning
    }

@celery_app.task(name="run_evaluation_task")
def run_evaluation_task(evaluation_run_id: str):
    db = SessionLocal()
    try:
        run = db.query(EvaluationRun).filter(EvaluationRun.id == evaluation_run_id).first()
        if not run:
            logger.error(f"EvaluationRun {evaluation_run_id} not found.")
            return

        run.status = EvaluationStatus.running
        db.commit()

        # Build query
        query = db.query(QueryLog).filter(QueryLog.tenant_id == run.tenant_id)
        if run.date_range_start:
            query = query.filter(QueryLog.created_at >= run.date_range_start)
        if run.date_range_end:
            query = query.filter(QueryLog.created_at <= run.date_range_end)

        # Sort by creation time desc (newest first)
        query = query.order_by(QueryLog.created_at.desc())

        # Limit by count if provided
        if run.query_count > 0:
            query = query.limit(run.query_count)

        logs = query.all()
        run.query_count = len(logs)
        db.commit()

        if not logs:
            run.status = EvaluationStatus.completed
            run.avg_faithfulness_score = 0.0
            run.avg_relevance_score = 0.0
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            
            create_notification(
                db=db,
                user_id=run.requested_by_user_id,
                tenant_id=run.tenant_id,
                type=NotificationType.evaluation_completed,
                message="Evaluation run completed: No query logs matched your requested scope.",
                related_evaluation_id=run.id,
            )
            return

        anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        success_count = 0
        total_faithfulness = 0
        total_relevance = 0

        for log in logs:
            try:
                # Format contexts
                contexts_str = "\n\n".join(log.contexts) if log.contexts else "No context retrieved."
                
                # Format prompt
                prompt = JUDGE_PROMPT_TEMPLATE.format(
                    contexts=contexts_str,
                    question=log.question,
                    answer=log.answer
                )

                # Call Claude Sonnet
                message = anthropic_client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    temperature=0.0,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                response_content = message.content[0].text
                
                # Parse JSON
                parsed_eval = clean_and_parse_json(response_content)

                # Store result
                res = EvaluationResult(
                    evaluation_run_id=run.id,
                    query_log_id=log.id,
                    faithfulness_score=parsed_eval["faithfulness_score"],
                    relevance_score=parsed_eval["relevance_score"],
                    unsupported_claims=parsed_eval["unsupported_claims"],
                    reasoning=parsed_eval["reasoning"],
                    created_at=datetime.now(timezone.utc),
                )
                db.add(res)
                db.flush()

                success_count += 1
                total_faithfulness += parsed_eval["faithfulness_score"]
                total_relevance += parsed_eval["relevance_score"]

            except Exception as e:
                logger.error(f"Error evaluating QueryLog {log.id}: {str(e)}", exc_info=True)
                # Keep processing other rows
                continue

        # Finalize run
        run.completed_at = datetime.now(timezone.utc)
        if len(logs) > 0 and success_count == 0:
            run.status = EvaluationStatus.failed
            notification_message = "Evaluation run failed: unable to evaluate any matching queries."
        else:
            run.status = EvaluationStatus.completed
            if success_count > 0:
                run.avg_faithfulness_score = total_faithfulness / success_count
                run.avg_relevance_score = total_relevance / success_count
            else:
                run.avg_faithfulness_score = 0.0
                run.avg_relevance_score = 0.0
            
            notification_message = f"Evaluation run completed! Processed {success_count} queries. Avg Faithfulness: {run.avg_faithfulness_score:.1f}%, Avg Relevance: {run.avg_relevance_score:.1f}%."

        db.commit()

        # Send notification
        create_notification(
            db=db,
            user_id=run.requested_by_user_id,
            tenant_id=run.tenant_id,
            type=NotificationType.evaluation_completed,
            message=notification_message,
            related_evaluation_id=run.id,
        )

    except Exception as exc:
        logger.error(f"Unhandled error in run_evaluation_task: {str(exc)}", exc_info=True)
        # Try to mark the run failed if possible
        try:
            db.rollback()
            run = db.query(EvaluationRun).filter(EvaluationRun.id == evaluation_run_id).first()
            if run:
                run.status = EvaluationStatus.failed
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
                
                create_notification(
                    db=db,
                    user_id=run.requested_by_user_id,
                    tenant_id=run.tenant_id,
                    type=NotificationType.evaluation_completed,
                    message=f"Evaluation run failed due to a system error: {str(exc)}",
                    related_evaluation_id=run.id,
                )
        except Exception as db_exc:
            logger.error(f"Failed to mark run as failed: {str(db_exc)}", exc_info=True)
    finally:
        db.close()

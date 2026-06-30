from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from app.db.session import get_db
from app.core.dependencies import require_admin
from app.models.user import User
from app.models.evaluation import EvaluationRun, EvaluationResult
from app.models.query_log import QueryLog
from app.models.enums import EvaluationStatus
from app.schemas.evaluation import (
    EvaluationRunRequest,
    EvaluationRunResponse,
    EvaluationDetailResponse,
    EvaluationResultResponse,
    ModelEvaluationBreakdown,
    EvaluationOverallResponse,
    AllEvaluationResultItem,
    AllEvaluationResultsResponse,
)
from app.tasks.evaluation_tasks import run_evaluation_task
import uuid
from typing import Optional, List

router = APIRouter()


@router.post(
    "/run", response_model=EvaluationRunResponse, status_code=status.HTTP_201_CREATED
)
def run_evaluation_endpoint(
    body: EvaluationRunRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Creates an EvaluationRun in pending state and schedules the Celery task to execute it.
    """
    run = EvaluationRun(
        tenant_id=current_admin.tenant_id,
        requested_by_user_id=current_admin.id,
        status=EvaluationStatus.pending,
        query_count=body.query_count or 0,
        date_range_start=body.date_range_start,
        date_range_end=body.date_range_end,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Enqueue Celery task
    run_evaluation_task.delay(str(run.id))

    return run


@router.get("/latest", response_model=Optional[EvaluationRunResponse])
def get_latest_evaluation(
    current_admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    """
    Fetches the most recent completed evaluation run.
    """
    run = (
        db.query(EvaluationRun)
        .filter(
            EvaluationRun.tenant_id == current_admin.tenant_id,
            EvaluationRun.status == EvaluationStatus.completed,
        )
        .order_by(EvaluationRun.created_at.desc())
        .first()
    )
    return run


@router.get("/by-model", response_model=List[ModelEvaluationBreakdown])
def get_evaluations_by_model(
    current_admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    """
    Aggregates EvaluationResult rows grouped by model_string across all evaluation runs.
    """
    results = (
        db.query(
            func.coalesce(QueryLog.model_string, "Unknown (legacy)").label(
                "model_string"
            ),
            func.count(EvaluationResult.id).label("query_count"),
            func.avg(EvaluationResult.faithfulness_score).label(
                "avg_faithfulness_score"
            ),
            func.avg(EvaluationResult.relevance_score).label("avg_relevance_score"),
        )
        .join(EvaluationResult, EvaluationResult.query_log_id == QueryLog.id)
        .join(EvaluationRun, EvaluationResult.evaluation_run_id == EvaluationRun.id)
        .filter(EvaluationRun.tenant_id == current_admin.tenant_id)
        .group_by(func.coalesce(QueryLog.model_string, "Unknown (legacy)"))
        .all()
    )
    return results


@router.get("/results/all", response_model=AllEvaluationResultsResponse)
def get_all_evaluation_results(
    limit: int = 20,
    offset: int = 0,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Returns every EvaluationResult row for the tenant across all evaluation runs.
    """
    # Base query
    query = (
        db.query(
            EvaluationResult.id,
            EvaluationResult.evaluation_run_id,
            EvaluationResult.query_log_id,
            EvaluationResult.faithfulness_score,
            EvaluationResult.relevance_score,
            EvaluationResult.unsupported_claims,
            EvaluationResult.reasoning,
            EvaluationResult.created_at,
            QueryLog.question,
            QueryLog.answer,
            QueryLog.model_string,
            EvaluationRun.created_at.label("run_created_at"),
        )
        .join(QueryLog, EvaluationResult.query_log_id == QueryLog.id)
        .join(EvaluationRun, EvaluationResult.evaluation_run_id == EvaluationRun.id)
        .filter(EvaluationRun.tenant_id == current_admin.tenant_id)
    )

    total_count = query.count()

    # Sort worst-first: combined score (faithfulness + relevance) ascending
    sorted_query = query.order_by(
        (EvaluationResult.faithfulness_score + EvaluationResult.relevance_score).asc()
    )

    db_results = sorted_query.limit(limit).offset(offset).all()

    results = []
    for r in db_results:
        results.append(
            AllEvaluationResultItem(
                id=r.id,
                evaluation_run_id=r.evaluation_run_id,
                query_log_id=r.query_log_id,
                faithfulness_score=r.faithfulness_score,
                relevance_score=r.relevance_score,
                unsupported_claims=r.unsupported_claims,
                reasoning=r.reasoning,
                created_at=r.created_at,
                question=r.question,
                answer=r.answer,
                model_string=r.model_string,
                run_created_at=r.run_created_at,
            )
        )

    return AllEvaluationResultsResponse(results=results, total_count=total_count)


@router.get("/overall", response_model=Optional[EvaluationOverallResponse])
def get_overall_evaluation(
    current_admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    """
    Computes average faithfulness_score and relevance_score across all EvaluationResult rows for the tenant.
    """
    # Check if there are any completed runs first
    has_runs = (
        db.query(EvaluationRun)
        .filter(
            EvaluationRun.tenant_id == current_admin.tenant_id,
            EvaluationRun.status == EvaluationStatus.completed,
        )
        .first()
    )

    if not has_runs:
        return None

    results = (
        db.query(
            func.avg(EvaluationResult.faithfulness_score).label(
                "avg_faithfulness_score"
            ),
            func.avg(EvaluationResult.relevance_score).label("avg_relevance_score"),
            func.count(EvaluationResult.id).label("query_count"),
        )
        .join(EvaluationRun, EvaluationResult.evaluation_run_id == EvaluationRun.id)
        .filter(
            EvaluationRun.tenant_id == current_admin.tenant_id,
            EvaluationRun.status == EvaluationStatus.completed,
        )
        .first()
    )

    if not results or results.query_count == 0:
        return None

    return {
        "avg_faithfulness_score": results.avg_faithfulness_score,
        "avg_relevance_score": results.avg_relevance_score,
        "query_count": results.query_count,
    }


@router.get("/{id}", response_model=EvaluationDetailResponse)
def get_evaluation_details(
    id: uuid.UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Fetches details of a specific evaluation run along with its individual results,
    sorted by the lowest combined score first.
    """
    run = (
        db.query(EvaluationRun)
        .filter(
            EvaluationRun.id == id, EvaluationRun.tenant_id == current_admin.tenant_id
        )
        .first()
    )
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found"
        )

    # Fetch results, eager loading query logs, sorted by lowest combined score first
    results = (
        db.query(EvaluationResult)
        .options(joinedload(EvaluationResult.query_log))
        .filter(EvaluationResult.evaluation_run_id == id)
        .all()
    )

    # Sort worst-first (combined score = faithfulness + relevance)
    sorted_results = sorted(
        results, key=lambda r: r.faithfulness_score + r.relevance_score
    )

    # Map to schema responses
    results_response = []
    for r in sorted_results:
        schema = EvaluationResultResponse.model_validate(r)
        if r.query_log:
            schema.question = r.query_log.question
            schema.answer = r.query_log.answer
            schema.model_string = r.query_log.model_string
        results_response.append(schema)

    return EvaluationDetailResponse(
        run=EvaluationRunResponse.model_validate(run), results=results_response
    )

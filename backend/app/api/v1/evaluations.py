from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.db.session import get_db
from app.core.dependencies import require_admin
from app.models.user import User
from app.models.evaluation import EvaluationRun, EvaluationResult
from app.models.enums import EvaluationStatus
from app.schemas.evaluation import (
    EvaluationRunRequest,
    EvaluationRunResponse,
    EvaluationDetailResponse,
    EvaluationResultResponse,
)
from app.tasks.evaluation_tasks import run_evaluation_task
import uuid
from typing import Optional

router = APIRouter()

@router.post("/run", response_model=EvaluationRunResponse, status_code=status.HTTP_201_CREATED)
def run_evaluation_endpoint(
    body: EvaluationRunRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
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
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Fetches the most recent completed evaluation run.
    """
    run = (
        db.query(EvaluationRun)
        .filter(
            EvaluationRun.tenant_id == current_admin.tenant_id,
            EvaluationRun.status == EvaluationStatus.completed
        )
        .order_by(EvaluationRun.created_at.desc())
        .first()
    )
    return run

@router.get("/{id}", response_model=EvaluationDetailResponse)
def get_evaluation_details(
    id: uuid.UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Fetches details of a specific evaluation run along with its individual results,
    sorted by the lowest combined score first.
    """
    run = (
        db.query(EvaluationRun)
        .filter(
            EvaluationRun.id == id,
            EvaluationRun.tenant_id == current_admin.tenant_id
        )
        .first()
    )
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found"
        )
    
    # Fetch results, eager loading query logs, sorted by lowest combined score first
    results = (
        db.query(EvaluationResult)
        .options(joinedload(EvaluationResult.query_log))
        .filter(EvaluationResult.evaluation_run_id == id)
        .all()
    )
    
    # Sort worst-first (combined score = faithfulness + relevance)
    sorted_results = sorted(results, key=lambda r: r.faithfulness_score + r.relevance_score)
    
    # Map to schema responses
    results_response = []
    for r in sorted_results:
        schema = EvaluationResultResponse.model_validate(r)
        if r.query_log:
            schema.question = r.query_log.question
            schema.answer = r.query_log.answer
        results_response.append(schema)
        
    return EvaluationDetailResponse(
        run=EvaluationRunResponse.model_validate(run),
        results=results_response
    )

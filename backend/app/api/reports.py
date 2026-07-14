import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.query_session import QuerySession
from app.models.generated_report import GeneratedReport
from app.schemas.report import (
    ReportCreateResponse,
    ReportStatusResponse,
    ReportStepResponse,
)
from app.services.storage_service import get_absolute_path

router = APIRouter()


@router.post("/sessions/{session_id}/reports", response_model=ReportCreateResponse)
def create_report(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a report from the messages in a query session.
    """
    # 1. Verify session exists and belongs to user's tenant
    session = (
        db.query(QuerySession)
        .options(joinedload(QuerySession.messages))
        .filter(QuerySession.id == session_id)
        .first()
    )
    if not session or session.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # 2. Verify session has at least one message
    if not session.messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The session has no content to generate a report from",
        )

    # 3. Create a new GeneratedReport in the database
    report = GeneratedReport(
        tenant_id=current_user.tenant_id,
        session_id=session_id,
        generated_by=current_user.id,
        title="Generating...",
        status="generating",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # 4. Dispatch Celery task
    from app.tasks.report_agent import run_report_generation_agent

    run_report_generation_agent.delay(str(report.id))

    return ReportCreateResponse(
        report_id=report.id,
        status=report.status,
    )


@router.get(
    "/sessions/{session_id}/reports/latest", response_model=ReportStatusResponse
)
def get_latest_report_status(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the latest report generation status and agent run steps of a session.
    """
    report = (
        db.query(GeneratedReport)
        .options(joinedload(GeneratedReport.runs))
        .filter(GeneratedReport.session_id == session_id)
        .order_by(GeneratedReport.created_at.desc())
        .first()
    )
    if not report or report.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No report found for this session",
        )

    # Sort runs by created_at to preserve execution order
    sorted_runs = sorted(report.runs, key=lambda r: r.created_at)

    steps = [
        ReportStepResponse(
            step_name=r.step_name,
            status=r.status,
            duration_ms=r.duration_ms,
            error_message=r.error_message,
        )
        for r in sorted_runs
    ]

    return ReportStatusResponse(
        report_id=report.id,
        status=report.status,
        title=report.title,
        created_at=report.created_at,
        completed_at=report.completed_at,
        steps=steps,
    )


@router.get("/reports/{report_id}/status", response_model=ReportStatusResponse)
def get_report_status(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the current generation status and agent run steps of a report.
    """
    # 1. Verify report exists and belongs to user's tenant
    report = (
        db.query(GeneratedReport)
        .options(joinedload(GeneratedReport.runs))
        .filter(GeneratedReport.id == report_id)
        .first()
    )
    if not report or report.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    # Note: report.runs is already ordered by created_at asc due to SQLAlchemy relationship order_by config
    steps = [
        ReportStepResponse(
            step_name=run.step_name,
            status=run.status,
            duration_ms=run.duration_ms,
            error_message=run.error_message,
        )
        for run in report.runs
    ]

    return ReportStatusResponse(
        report_id=report.id,
        status=report.status,
        title=report.title,
        created_at=report.created_at,
        completed_at=report.completed_at,
        steps=steps,
    )


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Download the generated PDF report.
    """
    # 1. Verify report exists and belongs to user's tenant
    report = db.query(GeneratedReport).filter(GeneratedReport.id == report_id).first()
    if not report or report.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    # 2. Check if the status is complete
    if report.status != "complete":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report is not ready for download yet",
        )

    # 3. Check if storage_path is null or the file does not exist on disk
    if not report.storage_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found",
        )

    file_path = report.storage_path
    if not os.path.isabs(file_path):
        file_path = get_absolute_path(file_path)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found",
        )

    # 4. Return PDF file with attachment filename
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"report_{report.id}.pdf",
    )

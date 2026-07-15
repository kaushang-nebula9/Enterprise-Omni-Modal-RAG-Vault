import os
import re
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.query_session import QuerySession
from app.models.generated_report import GeneratedReport
from app.models.report_agent_run import ReportAgentRun
from app.models.query_citation import QueryCitation
from app.models.query_message import QueryMessage
from app.models.external_database import ExternalDatabaseConnection
from app.schemas.report import (
    ReportCreateResponse,
    ReportStatusResponse,
    ReportStepResponse,
)
from app.services.storage_service import get_absolute_path

logger = logging.getLogger(__name__)

router = APIRouter()


def get_sources_and_type(db: Session, session_id: uuid.UUID):
    # Get citations for session
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
                citation.document.filename if citation.document else "Unnamed Document"
            )
            page = citation.page_number
            if doc_id not in docs_map:
                docs_map[doc_id] = {
                    "doc_name": doc_name,
                    "pages": set(),
                }
            if page is not None:
                docs_map[doc_id]["pages"].add(page)

    sources_used = []
    for doc_id, data in docs_map.items():
        if data["pages"]:
            pages_str = ", ".join(map(str, sorted(list(data["pages"]))))
            sources_used.append(f"{data['doc_name']} (pages: {pages_str})")
        else:
            sources_used.append(data["doc_name"])

    session = db.query(QuerySession).filter(QuerySession.id == session_id).first()
    has_db = False
    if session and session.db_connection_id:
        conn = (
            db.query(ExternalDatabaseConnection)
            .filter(ExternalDatabaseConnection.id == session.db_connection_id)
            .first()
        )
        if conn:
            has_db = True
            tables = set()
            messages = (
                db.query(QueryMessage)
                .filter(QueryMessage.session_id == session_id)
                .all()
            )
            for m in messages:
                if m.generated_sql:
                    matches = re.findall(
                        r"\b(?:from|join)\s+([a-zA-Z0-9_\.]+)",
                        m.generated_sql,
                        re.IGNORECASE,
                    )
                    for match in matches:
                        tbl = match.split(".")[-1].strip('`"[]')
                        tables.add(tbl)
            if tables:
                tables_str = ", ".join(sorted(list(tables)))
                sources_used.append(f"Database: {conn.name} (Tables: {tables_str})")
            else:
                sources_used.append(f"Database: {conn.name}")

    if docs_map and has_db:
        source_type = "Mixed"
    elif has_db:
        source_type = "Database"
    else:
        source_type = "Documents"

    return source_type, sources_used


@router.post("/sessions/{session_id}/reports", response_model=ReportCreateResponse)
def create_report(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a report from the messages in a query session.
    """
    # 1. Verify session exists and belongs to the user and tenant
    session = (
        db.query(QuerySession)
        .options(joinedload(QuerySession.messages))
        .filter(
            QuerySession.id == session_id,
            QuerySession.user_id == current_user.id,
            QuerySession.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not session:
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
    # Query report that belongs to user and matches session and tenant
    report = (
        db.query(GeneratedReport)
        .options(joinedload(GeneratedReport.runs))
        .filter(
            GeneratedReport.session_id == session_id,
            GeneratedReport.generated_by == current_user.id,
            GeneratedReport.tenant_id == current_user.tenant_id,
        )
        .order_by(GeneratedReport.created_at.desc())
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No report found for this session",
        )

    # Fetch session title
    session = (
        db.query(QuerySession).filter(QuerySession.id == report.session_id).first()
    )
    session_title = session.title if session else "Deleted Session"

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

    source_type, sources_used = get_sources_and_type(db, report.session_id)

    return ReportStatusResponse(
        report_id=report.id,
        session_id=report.session_id,
        session_title=session_title,
        source_type=source_type,
        sources_used=sources_used,
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
    # 1. Verify report exists and belongs to user and tenant
    report = (
        db.query(GeneratedReport)
        .options(joinedload(GeneratedReport.runs))
        .filter(
            GeneratedReport.id == report_id,
            GeneratedReport.generated_by == current_user.id,
            GeneratedReport.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    # Fetch session title
    session = (
        db.query(QuerySession).filter(QuerySession.id == report.session_id).first()
    )
    session_title = session.title if session else "Deleted Session"

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

    source_type, sources_used = get_sources_and_type(db, report.session_id)

    return ReportStatusResponse(
        report_id=report.id,
        session_id=report.session_id,
        session_title=session_title,
        source_type=source_type,
        sources_used=sources_used,
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
    # 1. Verify report exists and belongs to user and tenant
    report = (
        db.query(GeneratedReport)
        .filter(
            GeneratedReport.id == report_id,
            GeneratedReport.generated_by == current_user.id,
            GeneratedReport.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not report:
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


@router.get("/reports", response_model=list[ReportStatusResponse])
def list_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all reports generated by the current user.
    """
    reports = (
        db.query(GeneratedReport)
        .options(joinedload(GeneratedReport.runs))
        .filter(
            GeneratedReport.generated_by == current_user.id,
            GeneratedReport.tenant_id == current_user.tenant_id,
        )
        .order_by(GeneratedReport.created_at.desc())
        .all()
    )

    response = []
    for report in reports:
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

        # Fetch session title
        session = (
            db.query(QuerySession).filter(QuerySession.id == report.session_id).first()
        )
        session_title = session.title if session else "Deleted Session"

        source_type, sources_used = get_sources_and_type(db, report.session_id)

        response.append(
            ReportStatusResponse(
                report_id=report.id,
                session_id=report.session_id,
                session_title=session_title,
                source_type=source_type,
                sources_used=sources_used,
                status=report.status,
                title=report.title,
                created_at=report.created_at,
                completed_at=report.completed_at,
                steps=steps,
            )
        )

    return response


@router.get("/sessions/{session_id}/reports", response_model=list[ReportStatusResponse])
def get_session_reports(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all reports generated for a specific query session.
    """
    # Verify session exists and belongs to the user and tenant
    session = (
        db.query(QuerySession)
        .filter(
            QuerySession.id == session_id,
            QuerySession.user_id == current_user.id,
            QuerySession.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    reports = (
        db.query(GeneratedReport)
        .options(joinedload(GeneratedReport.runs))
        .filter(
            GeneratedReport.session_id == session_id,
            GeneratedReport.generated_by == current_user.id,
            GeneratedReport.tenant_id == current_user.tenant_id,
        )
        .order_by(GeneratedReport.created_at.desc())
        .all()
    )

    response = []
    for report in reports:
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

        source_type, sources_used = get_sources_and_type(db, report.session_id)

        response.append(
            ReportStatusResponse(
                report_id=report.id,
                session_id=report.session_id,
                session_title=session.title,
                source_type=source_type,
                sources_used=sources_used,
                status=report.status,
                title=report.title,
                created_at=report.created_at,
                completed_at=report.completed_at,
                steps=steps,
            )
        )

    return response


@router.post("/reports/{report_id}/retry", response_model=ReportCreateResponse)
def retry_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retry a failed report generation.
    """
    # Verify report exists and belongs to user and tenant
    report = (
        db.query(GeneratedReport)
        .filter(
            GeneratedReport.id == report_id,
            GeneratedReport.generated_by == current_user.id,
            GeneratedReport.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    if report.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed reports can be retried",
        )

    # Reset status and delete old run steps
    report.status = "generating"
    report.title = "Generating..."
    db.query(ReportAgentRun).filter(ReportAgentRun.report_id == report_id).delete()
    db.commit()
    db.refresh(report)

    # Dispatch Celery task
    from app.tasks.report_agent import run_report_generation_agent

    run_report_generation_agent.delay(str(report.id))

    return ReportCreateResponse(
        report_id=report.id,
        status=report.status,
    )


@router.delete("/reports/{report_id}")
def delete_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a report.
    """
    # Verify report exists and belongs to user and tenant
    report = (
        db.query(GeneratedReport)
        .filter(
            GeneratedReport.id == report_id,
            GeneratedReport.generated_by == current_user.id,
            GeneratedReport.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    # Clean up physical file on disk
    if report.storage_path:
        file_path = report.storage_path
        if not os.path.isabs(file_path):
            file_path = get_absolute_path(file_path)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Failed to delete report file {file_path}: {e}")

    db.delete(report)
    db.commit()

    return {"status": "success", "message": "Report deleted successfully"}

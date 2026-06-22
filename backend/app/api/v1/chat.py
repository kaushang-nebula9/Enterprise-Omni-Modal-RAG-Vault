"""
Chat API routes — session management, RAG query, and private document upload.
"""
import uuid
import logging
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.document_access_policy import DocumentAccessPolicy
from app.models.query_session import QuerySession
from app.models.query_message import QueryMessage
from app.models.query_citation import QueryCitation
from app.models.enums import (
    MessageRole,
    DocumentStatus,
    FileType,
    OwnerType,
    Visibility,
)
from app.schemas.chat import (
    SessionResponse,
    CreateSessionResponse,
    SessionDetailResponse,
    MessageResponse,
    CitationResponse,
    QueryRequest,
    QueryResponse,
    TranscriptionResponse,
)
from app.services.embedding_service import transcribe_audio
from app.schemas.document import DocumentResponse
from app.services.rag_service import run_rag_pipeline
from app.services.storage_service import save_file
from app.services.document_processor import process_document

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXTENSION_TO_FILE_TYPE: dict[str, FileType] = {
    ".pdf": FileType.pdf,
    ".docx": FileType.docx,
    ".txt": FileType.text,
    ".pptx": FileType.pptx,
    ".xlsx": FileType.excel,
    ".xls": FileType.excel,
    ".mp3": FileType.audio,
    ".wav": FileType.audio,
    ".m4a": FileType.audio,
}


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------


@router.post("/sessions", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new chat session."""
    session = QuerySession(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        title="New Chat",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all sessions for the current user, newest first."""
    sessions = (
        db.query(QuerySession)
        .filter(QuerySession.user_id == current_user.id)
        .order_by(QuerySession.updated_at.desc())
        .all()
    )
    return sessions


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a session with all messages and their citations,
    ordered by created_at ascending.
    """
    session = (
        db.query(QuerySession)
        .options(
            joinedload(QuerySession.messages)
            .joinedload(QueryMessage.citations)
            .joinedload(QueryCitation.document),
            joinedload(QuerySession.messages)
            .joinedload(QueryMessage.attached_document),
        )
        .filter(
            QuerySession.id == session_id,
            QuerySession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # joinedload does not guarantee ordering — sort messages chronologically
    # before serialisation so the client always receives them oldest-first.
    # Fallback to role if timestamps are identical.
    session.messages.sort(key=lambda m: (m.created_at, 0 if m.role == MessageRole.user else 1))

    return session



@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a session and all its messages/citations (cascade)."""
    session = (
        db.query(QuerySession)
        .filter(
            QuerySession.id == session_id,
            QuerySession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    db.delete(session)
    db.commit()
    return {"message": "Session deleted successfully"}


# ---------------------------------------------------------------------------
# Query endpoint
# ---------------------------------------------------------------------------


@router.post("/sessions/{session_id}/query")
async def send_query(
    session_id: uuid.UUID,
    body: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Send a user query to the RAG pipeline and stream the response.

    1. Verify session ownership
    2. Fetch recent conversation history
    3. Store user message and commit (before streaming starts)
    4. Stream response from RAG pipeline
    5. After streaming completes, store assistant message + citations and commit
    """
    # Verify session belongs to this user
    session = (
        db.query(QuerySession)
        .filter(
            QuerySession.id == session_id,
            QuerySession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    content = body.content

    # Fetch the last 10 messages for conversation history
    recent_messages = (
        db.query(QueryMessage)
        .filter(QueryMessage.session_id == session_id)
        .order_by(QueryMessage.created_at.desc())
        .limit(10)
        .all()
    )
    # Reverse to chronological order
    recent_messages = list(reversed(recent_messages))

    # Check if this is the first message (no previous messages)
    is_first_message = len(recent_messages) == 0

    # Format conversation history
    conversation_history = ""
    if recent_messages:
        history_lines = []
        for msg in recent_messages:
            role_label = "User" if msg.role == MessageRole.user else "Assistant"
            history_lines.append(f"{role_label}: {msg.content}")
        conversation_history = "\n".join(history_lines)

    # Store the user's message
    user_message = QueryMessage(
        session_id=session_id,
        role=MessageRole.user,
        content=content,
        created_at=datetime.now(timezone.utc),
        attached_document_id=body.document_id,
    )
    db.add(user_message)

    # If first message, update session title
    if is_first_message:
        session.title = content[:50]

    # Commit before streaming starts so the user message is saved immediately
    db.commit()

    async def event_generator():
        try:
            generator = run_rag_pipeline(
                query=content,
                user=current_user,
                db=db,
                conversation_history=conversation_history,
                document_id=body.document_id,
            )

            full_answer = ""
            citations = []

            async for event in generator:
                if event["type"] == "token":
                    # Stream format: data: {"type": "token", "content": "..."}\n\n
                    yield f"data: {json.dumps({'type': 'token', 'content': event['content']})}\n\n"
                elif event["type"] == "done":
                    full_answer = event["answer"]
                    citations = event["citations"]

            # Store the assistant's response in the database after streaming completes
            assistant_message = QueryMessage(
                session_id=session_id,
                role=MessageRole.assistant,
                content=full_answer,
                created_at=datetime.now(timezone.utc),
            )
            db.add(assistant_message)
            db.flush()

            # Store citations linked to the assistant message
            citation_models = []
            for cit in citations:
                citation = QueryCitation(
                    message_id=assistant_message.id,
                    document_id=cit["document_id"],
                    qdrant_vector_id=str(cit.get("chunk_index", "")),
                    chunk_text=cit["chunk_text"],
                    page_number=cit.get("page_number"),
                    chunk_index=cit.get("chunk_index", 0),
                )
                db.add(citation)
                citation_models.append(citation)

            # Update session timestamp
            session.updated_at = datetime.now(timezone.utc)
            db.commit()

            # Refresh to get generated IDs
            db.refresh(assistant_message)
            for c in citation_models:
                db.refresh(c)

            # Build citation responses for the done event
            citation_responses = []
            for cit_model, cit_data in zip(citation_models, citations):
                citation_responses.append({
                    "id": str(cit_model.id),
                    "document_id": str(cit_data["document_id"]),
                    "filename": cit_data["filename"],
                    "chunk_text": cit_data["chunk_text"],
                    "page_number": cit_data.get("page_number"),
                    "chunk_index": cit_data.get("chunk_index", 0),
                })

            # Final event: data: {"type": "done", "citations": [...], "message_id": "..."}\n\n
            yield f"data: {json.dumps({'type': 'done', 'citations': citation_responses, 'message_id': str(assistant_message.id)})}\n\n"

        except Exception as exc:
            logger.error("Error in event_generator: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'content': 'An error occurred during streaming.'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )



# ---------------------------------------------------------------------------
# Private document upload (members only)
# ---------------------------------------------------------------------------


@router.post("/sessions/{session_id}/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_private_document(
    session_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a private document from the chat interface.
    Only non-admin (member) users can use this route.
    """
    # Only members can upload private documents
    if current_user.role.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins cannot upload private documents. Use the Documents page instead.",
        )

    # Verify session belongs to this user
    session = (
        db.query(QuerySession)
        .filter(
            QuerySession.id == session_id,
            QuerySession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Validate file extension
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    file_type = EXTENSION_TO_FILE_TYPE.get(ext)
    if not file_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type",
        )

    # Generate document ID and save file
    document_id = uuid.uuid4()
    file_path = save_file(file, str(current_user.tenant_id), str(document_id))

    tenant_id = current_user.tenant_id
    collection_name = f"tenant_{tenant_id}"

    # Create document record — private, no access policies
    document = Document(
        id=document_id,
        tenant_id=tenant_id,
        uploaded_by=current_user.id,
        filename=filename,
        file_type=file_type,
        owner_type=OwnerType.private,
        visibility=Visibility.private,
        chunk_count=0,
        qdrant_collection=collection_name,
        status=DocumentStatus.pending,
        file_path=file_path,
        file_size=file.size,
    )
    db.add(document)
    db.commit()

    # Process document synchronously
    process_document(str(document_id), db)

    db.refresh(document)
    return document


@router.post("/transcribe", response_model=TranscriptionResponse)
def transcribe_voice_query(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Accepts a short audio recording, transcribes it using Gemini 2.5 Flash,
    and returns the transcribed text.
    """
    content_type = audio.content_type or ""
    if "webm" in content_type:
        ext = "webm"
    elif "wav" in content_type:
        ext = "wav"
    elif "mpeg" in content_type or "mp3" in content_type:
        ext = "mp3"
    elif "mp4" in content_type or "m4a" in content_type:
        ext = "m4a"
    else:
        # Fallback to filename extension
        filename = audio.filename or ""
        if "." in filename:
            ext = filename.rsplit(".", 1)[-1].lower()
        else:
            ext = "webm"

    tmp_dir = "/tmp"
    os.makedirs(tmp_dir, exist_ok=True)
    temp_file_path = os.path.join(tmp_dir, f"{uuid.uuid4()}_voice_query.{ext}")

    try:
        with open(temp_file_path, "wb") as f:
            f.write(audio.file.read())

        transcribed_text = transcribe_audio(temp_file_path)
        return TranscriptionResponse(text=transcribed_text)
    except Exception as exc:
        logger.error(f"Failed to transcribe audio query: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not transcribe audio. Please try again.",
        )
    finally:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as delete_exc:
                logger.warning(f"Failed to delete temp file {temp_file_path}: {delete_exc}")

import re
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, func
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.query_session import QuerySession
from app.models.query_message import QueryMessage
from app.schemas.chat import ChatSearchResponse, ChatSearchItem, MatchingLineItem

logger = logging.getLogger(__name__)

router = APIRouter()


def strip_markdown(line: str) -> str:
    """
    Remove basic markdown formatting from a text line.
    """
    # Remove headers at start of line (e.g. #, ##)
    line = re.sub(r"^\s*#+\s+", "", line)
    # Remove list markers at start of line (e.g. -, *, +, 1.)
    line = re.sub(r"^\s*[-*+]\s+", "", line)
    line = re.sub(r"^\s*\d+\.\s+", "", line)
    # Remove blockquotes at start of line (e.g. >)
    line = re.sub(r"^\s*>\s*", "", line)
    # Remove styling markdown characters anywhere in the string (e.g. *, _, `, ~)
    line = re.sub(r"[*_`~]", "", line)
    return line.strip()


@router.get("/conversations/search", response_model=ChatSearchResponse)
def search_conversations(
    q: str = Query(..., min_length=1),
    offset: int = Query(0, ge=0),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    match_in: str = Query("all"),
    sort: str = Query("recent"),
    case_sensitive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Search past conversations (query_sessions) and message contents for the logged-in user.
    """
    if not q or not q.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query 'q' cannot be empty or whitespaces.",
        )

    clean_q = q.strip()

    # Parse and validate date filters
    parsed_date_from = None
    if date_from:
        try:
            parsed_date_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date_from must be a valid ISO date/datetime string.",
            )

    parsed_date_to = None
    if date_to:
        try:
            if len(date_to.strip()) == 10:
                # adjust to end of day
                parsed_date_to = datetime.fromisoformat(date_to).replace(
                    hour=23, minute=59, second=59, microsecond=999999
                )
            else:
                parsed_date_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date_to must be a valid ISO date/datetime string.",
            )

    # Base query for sessions owned by the user
    query = db.query(QuerySession).filter(QuerySession.user_id == current_user.id)

    # Apply date filters if present
    if parsed_date_from:
        query = query.filter(QuerySession.updated_at >= parsed_date_from)
    if parsed_date_to:
        query = query.filter(QuerySession.updated_at <= parsed_date_to)

    # Apply search criteria based on match_in parameter and case sensitivity
    if case_sensitive:
        # Bypassing case-insensitive FTS and using standard SQL case-sensitive LIKE
        if match_in == "titles":
            query = query.filter(QuerySession.title.like(f"%{clean_q}%"))
        elif match_in == "messages":
            query = query.filter(
                QuerySession.id.in_(
                    db.query(QueryMessage.session_id).filter(
                        QueryMessage.content.like(f"%{clean_q}%")
                    )
                )
            )
        else:  # Default: all (search both)
            query = query.filter(
                or_(
                    QuerySession.title.like(f"%{clean_q}%"),
                    QuerySession.id.in_(
                        db.query(QueryMessage.session_id).filter(
                            QueryMessage.content.like(f"%{clean_q}%")
                        )
                    ),
                )
            )
    else:
        # Case-insensitive (FTS on Postgres, ILIKE on SQLite)
        if match_in == "titles":
            query = query.filter(QuerySession.title.ilike(f"%{clean_q}%"))
        elif match_in == "messages":
            if db.bind and db.bind.dialect.name == "sqlite":
                query = query.filter(
                    QuerySession.id.in_(
                        db.query(QueryMessage.session_id).filter(
                            QueryMessage.content.ilike(f"%{clean_q}%")
                        )
                    )
                )
            else:
                query = query.filter(
                    QuerySession.id.in_(
                        db.query(QueryMessage.session_id).filter(
                            func.to_tsvector("english", QueryMessage.content).op("@@")(
                                func.plainto_tsquery("english", clean_q)
                            )
                        )
                    )
                )
        else:  # Default: all (search both)
            if db.bind and db.bind.dialect.name == "sqlite":
                query = query.filter(
                    or_(
                        QuerySession.title.ilike(f"%{clean_q}%"),
                        QuerySession.id.in_(
                            db.query(QueryMessage.session_id).filter(
                                QueryMessage.content.ilike(f"%{clean_q}%")
                            )
                        ),
                    )
                )
            else:
                query = query.filter(
                    or_(
                        QuerySession.title.ilike(f"%{clean_q}%"),
                        QuerySession.id.in_(
                            db.query(QueryMessage.session_id).filter(
                                func.to_tsvector("english", QueryMessage.content).op(
                                    "@@"
                                )(func.plainto_tsquery("english", clean_q))
                            )
                        ),
                    )
                )

    # Fetch all candidate sessions to process matching lines and sorting
    sessions = query.options(joinedload(QuerySession.messages)).all()

    processed_results = []
    for session in sessions:
        # Check title match
        if case_sensitive:
            match_in_title = bool(session.title and clean_q in session.title)
        else:
            match_in_title = bool(
                session.title and clean_q.lower() in session.title.lower()
            )

        if match_in == "messages":
            match_in_title = False

        # Extract matching lines from message contents
        matching_lines = []
        if match_in != "titles":
            for msg in session.messages:
                lines = msg.content.split("\n")
                for line in lines:
                    is_line_matched = False
                    if case_sensitive:
                        is_line_matched = clean_q in line
                    else:
                        is_line_matched = clean_q.lower() in line.lower()

                    if is_line_matched:
                        cleaned_line = strip_markdown(line)
                        if cleaned_line:
                            role_str = (
                                msg.role.value
                                if hasattr(msg.role, "value")
                                else str(msg.role)
                            )
                            # Standardize to user or assistant
                            if "user" in role_str.lower():
                                final_role = "user"
                            else:
                                final_role = "assistant"

                            matching_lines.append(
                                MatchingLineItem(text=cleaned_line, role=final_role)
                            )

        match_count = len(matching_lines)

        # Scoping filter based on match_in selection
        is_matched = False
        if match_in == "titles":
            is_matched = match_in_title
        elif match_in == "messages":
            is_matched = match_count > 0
        else:
            is_matched = match_in_title or match_count > 0

        if is_matched:
            processed_results.append(
                {
                    "conversation_id": session.id,
                    "conversation_title": session.title or "New Chat",
                    "conversation_updated_at": session.updated_at,
                    "conversation_date": session.updated_at,
                    "matching_lines": matching_lines,
                    "match_in_title": match_in_title,
                    "match_count": match_count,
                }
            )

    # Sort results
    if sort == "oldest":
        processed_results.sort(key=lambda x: x["conversation_date"])
    elif sort == "most_matches":
        processed_results.sort(
            key=lambda x: (-x["match_count"], -x["conversation_date"].timestamp())
        )
    else:  # Default: recent
        processed_results.sort(key=lambda x: x["conversation_date"], reverse=True)

    # Paginate results
    total_count = len(processed_results)
    paginated_results = processed_results[offset : offset + 10]
    has_more = offset + len(paginated_results) < total_count

    # Convert dictionary to ChatSearchItem objects
    results = [ChatSearchItem(**item) for item in paginated_results]

    return ChatSearchResponse(
        results=results,
        total_count=total_count,
        has_more=has_more,
    )

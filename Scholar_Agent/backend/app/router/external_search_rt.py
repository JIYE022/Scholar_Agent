import asyncio
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.external_paper_search_agent import ExternalPaperSearchAgent
from models.session import Session as ChatSession
from schemas.external_search import ExternalPaperSearchRequest, ExternalPaperSearchResponse
from service.auth import access_security
from service.core.chat import update_session_name, write_chat_to_db
from service.core.chat import get_redis_client
from utils import logger
from utils.database import get_db


router = APIRouter(prefix="/agents", tags=["agents"])


def _enforce_rate_limit(user_id: str, limit_per_minute: int = 10) -> None:
    """Best-effort per-user limiter; Redis outages must not disable search."""
    try:
        bucket = int(time.time() // 60)
        key = f"external-paper-search:{user_id}:{bucket}"
        redis_client = get_redis_client()
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, 70)
        if count > limit_per_minute:
            raise HTTPException(status_code=429, detail="外部论文搜索过于频繁，请稍后重试")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"External search rate limiter unavailable: {type(exc).__name__}")


@router.post("/external-paper-search", response_model=ExternalPaperSearchResponse)
async def search_external_papers(
    request: ExternalPaperSearchRequest,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    subject_user_id = credentials.subject.get("user_id")
    if not subject_user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    user_id = str(subject_user_id)
    _enforce_rate_limit(user_id)

    existing_session = db.execute(
        select(ChatSession).where(ChatSession.session_id == request.session_id)
    ).scalar_one_or_none()
    if existing_session is not None and existing_session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await asyncio.to_thread(ExternalPaperSearchAgent().run, request)
    await asyncio.to_thread(
        write_chat_to_db,
        request.session_id,
        request.query,
        result.markdown,
        [],
        json.dumps([], ensure_ascii=False),
        "",
    )
    await asyncio.to_thread(update_session_name, request.session_id, request.query, user_id)
    return result

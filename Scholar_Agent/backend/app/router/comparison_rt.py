import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy.orm import Session

from agents.paper_comparison_agent import PaperComparisonAgent
from schemas.comparison import PaperComparisonRequest, PaperComparisonResponse
from service.auth import access_security
from service.core.retrieval import PaperAccessError
from service.core.chat import update_session_name, write_chat_to_db
from utils.database import get_db


router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/paper-comparison", response_model=PaperComparisonResponse)
async def compare_papers(
    request: PaperComparisonRequest,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    user_id = str(credentials.subject.get("user_id"))
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    try:
        agent = PaperComparisonAgent(db)
        result = await asyncio.to_thread(
            agent.run,
            user_id,
            request.paper_ids,
            request.question,
            request.dimensions,
        )
        await asyncio.to_thread(
            write_chat_to_db,
            request.session_id,
            request.question,
            result.markdown,
            [item.model_dump() for item in result.evidence],
            json.dumps([], ensure_ascii=False),
            "",
        )
        await asyncio.to_thread(
            update_session_name,
            request.session_id,
            request.question,
            user_id,
        )
        return result
    except PaperAccessError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

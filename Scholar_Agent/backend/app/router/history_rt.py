from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy.orm import Session
from utils.database import get_db
from models.knowledgebase import KnowledgeBase
from schemas.message import SessionListResponse, SessionResponse
from schemas.paper import PaperResponse, PaperUpdate
from fastapi_jwt import JwtAuthorizationCredentials
from service.auth import access_security
from typing import List
from sqlalchemy import text ,select 
from urllib.parse import unquote
from service.document_operations import delete_document
from database.knowledgebase_operations import update_paper
from service.core.rag.utils.es_conn import ESConnection

router = APIRouter()


def count_document_chunks(user_id: str, file_name: str) -> int:
    try:
        es_connection = ESConnection()
        result = es_connection.es.count(
            index=user_id,
            body={
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"kb_id": user_id}},
                        ],
                        "should": [
                            {"term": {"docnm": file_name}},
                            {"term": {"docnm.keyword": file_name}},
                            {"term": {"docnm_kwd": file_name}},
                        ],
                        "minimum_should_match": 1,
                    }
                }
            },
        )
        return int(result.get("count", 0))
    except Exception:
        return 0


def to_paper_response(row: KnowledgeBase, chunk_count: int = 0) -> PaperResponse:
    """将数据库论文对象转换为对外响应。"""
    return PaperResponse(
        id=row.id,
        user_id=row.user_id,
        file_name=row.file_name,
        title=row.title,
        authors=row.authors or [],
        year=row.year,
        venue=row.venue,
        doi=row.doi,
        keywords=row.keywords or [],
        abstract=row.abstract,
        research_topic=row.research_topic,
        read_status=row.read_status,
        personal_tags=row.personal_tags or [],
        chunk_count=chunk_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )

############################
#   获取文档列表
############################

@router.get("/get_files", response_model=List[PaperResponse])
async def get_documents_by_user_id(
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    """
    获取用户上传的文档列表，需要用户认证
    """
    try:
        # 从 token 中获取用户 ID
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 构建查询语句
        stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.user_id == user_id)
            .order_by(KnowledgeBase.updated_at.desc())
        )
        
        # 执行查询
        result = db.execute(stmt).scalars().all()

        # 如果没有找到文档，返回空列表
        if not result:
            return []

        # 将查询结果转换为 Pydantic 模型
        documents = [
            to_paper_response(
                row,
                chunk_count=count_document_chunks(user_id, row.file_name),
            )
            for row in result
        ]

        return documents

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve documents: {str(e)}"
        )


@router.get("/papers/{paper_id}", response_model=PaperResponse)
async def get_paper(
    paper_id: int,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    user_id = str(credentials.subject.get("user_id"))
    paper = db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == paper_id,
            KnowledgeBase.user_id == user_id,
        )
    ).scalar_one_or_none()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return to_paper_response(
        paper,
        chunk_count=count_document_chunks(user_id, paper.file_name),
    )


@router.patch("/papers/{paper_id}", response_model=PaperResponse)
async def patch_paper(
    paper_id: int,
    changes: PaperUpdate,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    user_id = str(credentials.subject.get("user_id"))
    paper = db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == paper_id,
            KnowledgeBase.user_id == user_id,
        )
    ).scalar_one_or_none()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")

    updated = update_paper(db, paper, changes)
    return to_paper_response(
        updated,
        chunk_count=count_document_chunks(user_id, updated.file_name),
    )


@router.delete("/papers/{paper_id}")
async def delete_paper_endpoint(
    paper_id: int,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    user_id = str(credentials.subject.get("user_id"))
    result = delete_document(user_id, None, db, paper_id=paper_id)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return {"message": result["message"]}

############################
#   删除文档
############################

@router.delete("/delete_file/{file_name}")
async def delete_document_endpoint(
    file_name: str,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    try:
        # URL 解码文件名
        decoded_file_name = unquote(file_name)
        
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 调用 service 层的删除方法
        result = delete_document(user_id, decoded_file_name, db)
        
        if result["status"] == "error":
            raise HTTPException(status_code=404, detail=result["message"])
            
        return {"message": result["message"]}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get_messages")
async def get_messages_by_session_id(
    session_id: str,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 查询 messages 表中对应 session_id 的消息
        messages_data = db.execute(
            text("SELECT message_id, session_id, user_question, model_answer, documents, recommended_questions, think, created_at FROM messages WHERE session_id = :session_id"),
            {"session_id": session_id}
        ).fetchall()

        # 构造返回数据
        messages = []
        for message in messages_data:
            messages.append(
                {
                    "message_id": message.message_id,
                    "session_id": message.session_id,
                    "user_question": message.user_question,
                    "model_answer":message.model_answer,
                    "documents" : message.documents,
                    "recommended_questions" : message.recommended_questions,
                    "think" : message.think,
                    "created_at": message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                }
            )

        return messages

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve messages: {str(e)}"
        )
    
@router.get("/get_sessions", response_model=SessionListResponse)
async def get_sessions_by_user_id(
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")


        # 查询 sessions 表中对应 user_id 的所有会话
        sessions_data = db.execute(
            text("SELECT * FROM sessions WHERE user_id = :user_id"),
            {"user_id": user_id}
        ).fetchall()

        # 构造返回数据
        sessions = []
        for session in sessions_data:
            sessions.append(
                SessionResponse(
                    session_id=session.session_id,
                    session_name=session.session_name,
                    user_id=session.user_id,
                    created_at=session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    updated_at=session.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                )
            )

        return {"user_id": user_id, "sessions": sessions}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

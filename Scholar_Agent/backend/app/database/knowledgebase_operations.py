from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from utils.database import get_db  # 根据实际模块名称导入
from fastapi import HTTPException
from models.knowledgebase import KnowledgeBase
from schemas.paper import PaperMetadataCreate, PaperUpdate


def create_paper(
    db: Session,
    user_id: str,
    file_name: str,
    metadata: Optional[PaperMetadataCreate] = None,
) -> KnowledgeBase:
    """
    将论文文件及其元数据插入 knowledgebases 表。

    :param db: 由路由层传入的数据库会话
    :param user_id: 用户 ID
    :param file_name: 文件名称
    :param metadata: 已通过 Pydantic 校验的论文元数据
    :return: 已写入数据库并刷新的论文对象

    metadata 暂时允许为空，以兼容尚未接入论文表单的上传接口；
    此时使用不含扩展名的文件名作为临时标题。
    """
    if metadata is None:
        metadata = PaperMetadataCreate(title=Path(file_name).stem)

    paper = KnowledgeBase(
        user_id=user_id,
        file_name=file_name,
        title=metadata.title,
        authors=metadata.authors,
        year=metadata.year,
        venue=metadata.venue,
        doi=metadata.doi,
        keywords=metadata.keywords,
        abstract=metadata.abstract,
        research_topic=metadata.research_topic,
        read_status=metadata.read_status.value,
        personal_tags=metadata.personal_tags,
    )

    try:
        db.add(paper)
        db.commit()
        db.refresh(paper)
        return paper
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Failed to create paper: {str(e)}") from e


def update_paper(
    db: Session,
    paper: KnowledgeBase,
    changes: PaperUpdate,
) -> KnowledgeBase:
    """更新用户提交的论文元数据，不修改文件名和所属用户。"""
    update_data = changes.model_dump(exclude_unset=True)
    if "read_status" in update_data and update_data["read_status"] is not None:
        update_data["read_status"] = update_data["read_status"].value

    for field, value in update_data.items():
        setattr(paper, field, value)

    try:
        db.commit()
        db.refresh(paper)
        return paper
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Failed to update paper: {str(e)}") from e

def verify_user_knowledgebase(user_id: str):
    """
    验证用户是否有自己的知识库。

    :param user_id: 用户 ID
    :raises HTTPException: 如果用户没有知识库，抛出 404 错误
    """
    db = next(get_db())  # 获取数据库会话
    try:
        query_result = db.execute(
            text("SELECT id FROM knowledgebases WHERE user_id = :user_id LIMIT 1"),
            {"user_id": user_id}
        ).fetchone()

        if not query_result:
            # 如果没有查到知识库数据，返回特定的错误码
            raise HTTPException(status_code=461,detail="You do not have your own knowledge base yet.")
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database operation failed: {str(e)}"
        )
    finally:
        db.close()

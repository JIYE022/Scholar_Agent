from sqlalchemy import Column, Integer, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from models.base import Base

class KnowledgeBase(Base):
    __tablename__ = 'knowledgebases'  # 表名
    
    id = Column(Integer, primary_key=True, autoincrement=True)  # 主键
    user_id = Column(String(255), nullable=False)  # 用户 ID
    file_name = Column(String(255), nullable=False)  # 文件名称
    title = Column(String(500), nullable=True)  # 文档标题
    authors = Column(JSONB, nullable=False, default=list)  # 论文作者（有序列表）
    year = Column(Integer, nullable=True)
    venue = Column(String(255), nullable=True)
    doi = Column(String(255), nullable=True)
    keywords = Column(JSONB, nullable=False, default=list)
    abstract = Column(Text, nullable=True)
    research_topic = Column(String(255), nullable=True)
    read_status = Column(String(32), nullable=False, default="unread")
    personal_tags = Column(JSONB, nullable=False, default=list)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())  # 创建时间
    updated_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )  # 更新时间

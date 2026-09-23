from sqlalchemy import Column, String, Text, TIMESTAMP, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from models.base import Base

class Message(Base):
    __tablename__ = "messages"

    message_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    session_id = Column(String(16), nullable=False)
    user_question = Column(Text, nullable=False)
    model_answer = Column(Text, nullable=False)
    create_time = Column(TIMESTAMP, server_default=func.now())
    retrieval_content = Column(Text)



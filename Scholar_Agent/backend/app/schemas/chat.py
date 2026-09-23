from pydantic import BaseModel, Field
from typing import List

##################################
# 创建一个新的对话 Session
##################################


# 定义响应模型
class SessionResponse(BaseModel):
    session_id: str
    status: str
    message: str

##################################
# 基于用户发送的 message，后端检索并返回相关文档
##################################

# 请求体模型
class ExploreRequest(BaseModel):
    user_message: str

# 响应体模型
class DocumentResponse(BaseModel):
    document_id: str
    document_name: str
    preview: str
    create_time: int
    update_time: int

class ExploreResponse(BaseModel):
    documents: List[DocumentResponse]
    message: str
    status: str


##################################
# 添加文档到会话上下文
##################################
# 请求体模型
class AddDocsRequest(BaseModel):
    document_id: List[str]

# 响应体模型
class AddDocsResponse(BaseModel):
    status: str
    message: str

##################################
# 在已经添加文档的会话上下文基础上，对用户消息进行分析，并返回问答结果
##################################

class ChatRequest(BaseModel):
    message: str
    paper_ids: List[int] = Field(default_factory=list)
    sections: List[str] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=50)
    per_paper_top_k: int | None = Field(default=None, ge=1, le=20)

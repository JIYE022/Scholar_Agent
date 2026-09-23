from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class ReadStatus(str, Enum):
    UNREAD = "unread"
    READING = "reading"
    READ = "read"
    ARCHIVED = "archived"

class PaperMetadataCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1000, le=9999)
    venue: str | None = None
    doi: str | None = None
    keywords: list[str] = Field(default_factory=list)
    abstract: str | None = None
    research_topic: str | None = None
    read_status: ReadStatus = ReadStatus.UNREAD
    personal_tags: list[str] = Field(default_factory=list)

class PaperUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    authors: list[str] | None = None
    year: int | None = Field(default=None, ge=1000, le=9999)
    venue: str | None = None
    doi: str | None = None
    keywords: list[str] | None = None
    abstract: str | None = None
    research_topic: str | None = None
    read_status: ReadStatus | None = None
    personal_tags: list[str] | None = None

class PaperResponse(BaseModel):
    id: int
    user_id: str
    file_name: str
    title: str | None
    authors: list[str] = Field(default_factory=list)
    year: int | None
    venue: str | None
    doi: str | None
    keywords: list[str]
    abstract: str | None
    research_topic: str | None
    read_status: ReadStatus
    personal_tags: list[str]
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

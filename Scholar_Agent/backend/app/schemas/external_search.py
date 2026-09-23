from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


ExternalSource = Literal["openalex", "arxiv"]
SearchSort = Literal["relevance", "newest", "cited"]


class ExternalPaperSearchRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    query: str = Field(min_length=2, max_length=1000)
    limit: int = Field(default=10, ge=1, le=20)
    sources: list[ExternalSource] = Field(
        default_factory=lambda: ["openalex", "arxiv"],
        min_length=1,
        max_length=2,
    )
    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)
    sort: SearchSort | None = None

    @model_validator(mode="after")
    def validate_filters(self):
        self.sources = list(dict.fromkeys(self.sources))
        if self.year_from and self.year_to and self.year_from > self.year_to:
            raise ValueError("year_from 不能晚于 year_to")
        return self


class ExternalSearchPlan(BaseModel):
    original_query: str
    search_query: str = Field(min_length=1, max_length=300)
    keywords: list[str] = Field(default_factory=list, max_length=8)
    authors: list[str] = Field(default_factory=list, max_length=5)
    year_from: int | None = None
    year_to: int | None = None
    sort: SearchSort = "relevance"
    sources: list[ExternalSource]
    limit: int


class ExternalPaper(BaseModel):
    external_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    year: int | None = None
    published_at: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    venue: str | None = None
    citation_count: int | None = None
    sources: list[ExternalSource]
    landing_url: str
    pdf_url: str | None = None
    keywords: list[str] = Field(default_factory=list)
    relevance_score: float = 0.0
    relevance_reason: str | None = None


class ExternalPaperSearchResponse(BaseModel):
    query_plan: ExternalSearchPlan
    papers: list[ExternalPaper]
    summary: str
    total_found: int
    returned_count: int
    sources: list[ExternalSource]
    warnings: list[str] = Field(default_factory=list)
    searched_at: datetime
    markdown: str

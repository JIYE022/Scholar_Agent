from typing import Literal

from pydantic import BaseModel, Field, model_validator


ComparisonDimension = Literal[
    "research_problem",
    "method",
    "model_architecture",
    "dataset",
    "training_strategy",
    "evaluation_metric",
    "main_result",
    "innovation",
    "limitation",
]


class PaperComparisonRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    paper_ids: list[int] = Field(min_length=2, max_length=5)
    question: str = Field(min_length=1, max_length=2000)
    dimensions: list[ComparisonDimension] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def validate_unique_papers(self):
        self.paper_ids = list(dict.fromkeys(self.paper_ids))
        if len(self.paper_ids) < 2:
            raise ValueError("请至少选择两篇不同的论文")
        return self


class ComparisonPaper(BaseModel):
    paper_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None


class ComparisonCell(BaseModel):
    paper_id: str
    dimension: ComparisonDimension
    status: Literal["found", "partial", "not_found", "not_applicable"]
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)


class ComparisonEvidence(BaseModel):
    evidence_id: str
    dimension: ComparisonDimension
    chunk_id: str | None = None
    paper_id: str
    paper_title: str
    document_id: str
    document_name: str
    section: str | None = None
    page: int | None = None
    content_with_weight: str
    score: float = 0.0


class PaperComparisonResponse(BaseModel):
    papers: list[ComparisonPaper]
    dimensions: list[ComparisonDimension]
    cells: list[ComparisonCell]
    summary: str
    markdown: str
    evidence: list[ComparisonEvidence]

"""FastAPI endpoints for running an offline RAG baseline evaluation."""

from __future__ import annotations

import json
import re
import statistics
import time
import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Security
from fastapi.concurrency import run_in_threadpool
from fastapi_jwt import JwtAuthorizationCredentials
from pydantic import BaseModel, Field

from service.auth import access_security
from service.core.chat import get_chat_completion
from service.core.retrieval import retrieve_content


router = APIRouter(prefix="/evaluation", tags=["RAG Evaluation"])

REFUSAL_WORDS = (
    "没有相关信息",
    "未提供相关信息",
    "无法从提供",
    "无法根据提供",
    "资料中未提及",
    "不知道",
)


class EvaluationSample(BaseModel):
    id: str
    question: str = Field(min_length=1)
    reference_answer: str = ""
    paper_ids: list[str] = Field(default_factory=list)
    relevant_chunks: list[str] = Field(default_factory=list)
    question_type: Literal[
        "fact",
        "method",
        "result",
        "paraphrase",
        "cross_chunk",
        "out_of_scope",
        "multi_turn",
    ]
    answerable: bool = True
    answer_score: int | None = Field(default=None, ge=0, le=2)


class EvaluationRequest(BaseModel):
    samples: list[EvaluationSample] = Field(min_length=1, max_length=50)
    session_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


def _collect_answer(
    session_id: str,
    question: str,
    retrieved: list[dict[str, Any]],
    user_id: str,
) -> tuple[str, float | None, float]:
    started = time.perf_counter()
    first_token_ms: float | None = None
    answer_parts: list[str] = []

    for event in get_chat_completion(session_id, question, retrieved, user_id):
        for line in event.splitlines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                continue
            try:
                message = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if message.get("role") == "error":
                raise RuntimeError(message.get("content", "RAG generation failed"))
            if message.get("thinking") is False and message.get("content"):
                if first_token_ms is None:
                    first_token_ms = (time.perf_counter() - started) * 1000
                answer_parts.append(str(message["content"]))

    return (
        "".join(answer_parts),
        first_token_ms,
        (time.perf_counter() - started) * 1000,
    )


def _retrieval_metrics(
    sample: EvaluationSample,
    retrieved: list[dict[str, Any]],
    top_k: int,
) -> dict[str, float | int | None]:
    if not sample.answerable:
        return {"recall_at_k": None, "mrr": None, "document_hit": None}

    top = retrieved[:top_k]
    relevant = set(sample.relevant_chunks)
    target_papers = set(sample.paper_ids)
    retrieved_ids = [
        str(item.get("chunk_id") or item.get("document_id") or item.get("id"))
        for item in top
    ]
    retrieved_papers = {
        str(item.get("paper_id") or item.get("document_id")) for item in top
    }
    hits = relevant.intersection(retrieved_ids)
    first_rank = next(
        (rank for rank, item_id in enumerate(retrieved_ids, 1) if item_id in relevant),
        None,
    )
    return {
        "recall_at_k": len(hits) / len(relevant) if relevant else None,
        "mrr": 1 / first_rank if first_rank else 0.0,
        "document_hit": (
            int(bool(target_papers.intersection(retrieved_papers)))
            if target_papers
            else None
        ),
    }


def _evaluate(request: EvaluationRequest, user_id: str) -> dict[str, Any]:
    session_id = request.session_id or f"rag-eval-{uuid.uuid4().hex[:12]}"
    results: list[dict[str, Any]] = []

    for sample in request.samples:
        retrieval_started = time.perf_counter()
        retrieved = retrieve_content(user_id, sample.question)
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
        answer, first_token_ms, total_ms = _collect_answer(
            session_id, sample.question, retrieved, user_id
        )

        citations = [int(value) for value in re.findall(r"\[(\d+)]", answer)]
        valid_citations = sum(1 <= value <= len(retrieved) for value in citations)
        refused = any(word in answer for word in REFUSAL_WORDS)
        result = {
            "id": sample.id,
            "question_type": sample.question_type,
            "answerable": sample.answerable,
            "reference_answer": sample.reference_answer,
            "generated_answer": answer,
            "retrieved_chunks": retrieved[: request.top_k],
            **_retrieval_metrics(sample, retrieved, request.top_k),
            "answer_score": sample.answer_score,
            "citation_count": len(citations),
            "citation_correctness": (
                valid_citations / len(citations) if citations else None
            ),
            "correct_refusal": int(refused) if not sample.answerable else None,
            "wrong_refusal": int(refused) if sample.answerable else None,
            "retrieval_ms": round(retrieval_ms, 2),
            "first_token_ms": (
                round(first_token_ms, 2) if first_token_ms is not None else None
            ),
            "total_response_ms": round(total_ms, 2),
        }
        results.append(result)

    def mean(field: str) -> float | None:
        values = [row[field] for row in results if row.get(field) is not None]
        return round(statistics.fmean(values), 4) if values else None

    answer_score = mean("answer_score")
    return {
        "session_id": session_id,
        "sample_count": len(results),
        "summary": {
            f"recall_at_{request.top_k}": mean("recall_at_k"),
            "mrr": mean("mrr"),
            "document_hit_rate": mean("document_hit"),
            "answer_accuracy": answer_score / 2 if answer_score is not None else None,
            "citation_correctness": mean("citation_correctness"),
            "out_of_scope_refusal_rate": mean("correct_refusal"),
            "wrong_refusal_rate": mean("wrong_refusal"),
            "average_retrieval_ms": mean("retrieval_ms"),
            "average_first_token_ms": mean("first_token_ms"),
            "average_total_response_ms": mean("total_response_ms"),
        },
        "results": results,
    }


@router.post("/run")
async def run_evaluation(
    request: EvaluationRequest,
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    """Run 1-50 evaluation samples against the current RAG pipeline."""
    user_id = str(credentials.subject.get("user_id") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    try:
        return await run_in_threadpool(_evaluate, request, user_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"评测运行失败: {exc}") from exc

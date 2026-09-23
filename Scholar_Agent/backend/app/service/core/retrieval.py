from __future__ import annotations

import os
from collections.abc import Sequence

import xxhash
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.knowledgebase import KnowledgeBase
from service.core.rag.nlp.search_v2 import Dealer
from service.core.rag.utils.es_conn import ESConnection
from utils.database import get_db


es_connection = ESConnection()
dealer = Dealer(dataStore=es_connection)


class PaperAccessError(ValueError):
    """请求的论文不存在或不属于当前用户。"""


def _serialize_chunks(chunks: list[dict]) -> list[dict]:
    extracted_data = []
    for chunk in chunks:
        doc_id = chunk.get("doc_id", "N/A")
        docnm = str(chunk.get("docnm_kwd", "N/A")).split("/")[-1]
        extracted_data.append({
            "chunk_id": chunk.get("chunk_id") or chunk.get("_id") or chunk.get("id"),
            "document_id": doc_id,
            "document_name": docnm,
            "content_with_weight": chunk.get("content_with_weight", "N/A"),
            "paper_id": chunk.get("paper_id", doc_id),
            "paper_title": chunk.get("paper_title", docnm),
            "section": chunk.get("section", "Unknown"),
            "page": chunk.get("page"),
            "authors": chunk.get("authors", []),
            "year": chunk.get("year"),
            "score": float(chunk.get("similarity", 0.0)),
            "rerank_score": float(chunk.get("vector_similarity", 0.0)),
        })
    return extracted_data


def _legacy_retrieve(index_names: str, question: str) -> list[dict]:
    """原有 RAG 路径；Dealer 调用参数保持不变。"""
    results = dealer.retrieval(
        question=question,
        embd_mdl=None,
        tenant_ids=index_names,
        kb_ids=None,
        vector_similarity_weight=0.6,
        page=1,
        page_size=5,
        rerank_mdl=os.getenv("RERANK_MODEL", "Qwen/Qwen3-Reranker-4B"),
        dynamic_min_score=float(os.getenv("RERANK_MIN_SCORE", "0.05")),
        dynamic_relative_floor=float(os.getenv("RERANK_RELATIVE_FLOOR", "0.45")),
    )
    return _serialize_chunks(results["chunks"])


def _normalize_paper_ids(paper_ids: Sequence[int | str] | None) -> list[int]:
    normalized: list[int] = []
    for paper_id in paper_ids or []:
        try:
            value = int(paper_id)
        except (TypeError, ValueError) as exc:
            raise PaperAccessError("paper_ids 必须是数据库论文 ID") from exc
        if value <= 0:
            raise PaperAccessError("paper_ids 必须是正整数")
        if value not in normalized:
            normalized.append(value)
    return normalized


def _authorize_papers(
    db: Session, user_id: str, paper_ids: Sequence[int | str]
) -> list[KnowledgeBase]:
    normalized = _normalize_paper_ids(paper_ids)
    if not normalized:
        return []
    papers = db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.user_id == user_id,
            KnowledgeBase.id.in_(normalized),
        )
    ).scalars().all()
    papers_by_id = {paper.id: paper for paper in papers}
    if any(paper_id not in papers_by_id for paper_id in normalized):
        raise PaperAccessError("一个或多个论文不存在")
    return [papers_by_id[paper_id] for paper_id in normalized]


def _document_id(file_name: str) -> str:
    """与现有入库代码生成 doc_id 的规则保持一致。"""
    return xxhash.xxh64(file_name.encode("utf-8")).hexdigest()


def _scoped_retrieve(
    user_id: str,
    question: str,
    *,
    doc_ids: list[str] | None,
    sections: list[str] | None,
    page_size: int,
) -> list[dict]:
    results = dealer.retrieval(
        question=question,
        embd_mdl=None,
        tenant_ids=user_id,
        kb_ids=None,
        doc_ids=doc_ids,
        vector_similarity_weight=0.6,
        page=1,
        page_size=page_size,
        rerank_mdl=os.getenv("RERANK_MODEL", "Qwen/Qwen3-Reranker-4B"),
        dynamic_min_score=float(os.getenv("RERANK_MIN_SCORE", "0.05")),
        dynamic_relative_floor=float(os.getenv("RERANK_RELATIVE_FLOOR", "0.45")),
        sections=sections,
        preserve_doc_filter=bool(doc_ids),
    )
    return results["chunks"]


def _apply_authoritative_metadata(
    evidence: list[dict], papers_by_document: dict[str, KnowledgeBase]
) -> list[dict]:
    for item in evidence:
        paper = papers_by_document.get(str(item["document_id"]))
        if paper is not None:
            item.update({
                "paper_id": str(paper.id),
                "paper_title": paper.title or paper.file_name,
                "document_name": paper.file_name,
                "authors": paper.authors or [],
                "year": paper.year,
            })
    return evidence


def retrieve_content(
    indexNames: str,
    question: str,
    *,
    paper_ids: Sequence[int | str] | None = None,
    sections: Sequence[str] | None = None,
    top_k: int = 5,
    per_paper_top_k: int | None = None,
    db: Session | None = None,
) -> list[dict]:
    """统一证据检索；未传新参数时完整走原有 RAG 路径。"""
    if top_k <= 0:
        raise ValueError("top_k 必须是正整数")
    if per_paper_top_k is not None and per_paper_top_k <= 0:
        raise ValueError("per_paper_top_k 必须是正整数")

    normalized_ids = _normalize_paper_ids(paper_ids)
    normalized_sections = list(dict.fromkeys(
        section.strip() for section in sections or [] if section and section.strip()
    ))

    if not normalized_ids and not normalized_sections and top_k == 5 and per_paper_top_k is None:
        return _legacy_retrieve(indexNames, question)

    db_generator = get_db() if normalized_ids and db is None else None
    if db_generator is not None:
        db = next(db_generator)
    try:
        papers = _authorize_papers(db, indexNames, normalized_ids) if normalized_ids else []
    finally:
        if db_generator is not None:
            db_generator.close()

    papers_by_document = {_document_id(paper.file_name): paper for paper in papers}
    section_filter = normalized_sections or None

    if papers and per_paper_top_k is not None:
        chunks: list[dict] = []
        for document_id in papers_by_document:
            chunks.extend(_scoped_retrieve(
                indexNames,
                question,
                doc_ids=[document_id],
                sections=section_filter,
                page_size=per_paper_top_k,
            ))
        chunks.sort(key=lambda chunk: float(chunk.get("similarity", 0.0)), reverse=True)
    else:
        chunks = _scoped_retrieve(
            indexNames,
            question,
            doc_ids=list(papers_by_document) or None,
            sections=section_filter,
            page_size=top_k,
        )

    evidence = _serialize_chunks(chunks)
    return _apply_authoritative_metadata(evidence, papers_by_document)


if __name__ == "__main__":
    print(retrieve_content(question="世运电路成长性如何", indexNames="test01"))

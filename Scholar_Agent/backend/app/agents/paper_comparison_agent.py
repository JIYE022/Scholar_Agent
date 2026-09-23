from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.knowledgebase import KnowledgeBase
from schemas.comparison import (
    ComparisonCell,
    ComparisonDimension,
    ComparisonEvidence,
    ComparisonPaper,
    PaperComparisonResponse,
)
from service.core.retrieval import PaperAccessError, retrieve_content
from utils.model_config import get_model_api_key, get_model_base_url


@dataclass(frozen=True)
class DimensionConfig:
    label: str
    query: str
    sections: tuple[str, ...]


DIMENSIONS: dict[ComparisonDimension, DimensionConfig] = {
    "research_problem": DimensionConfig("研究问题", "研究问题 research problem objective task motivation", ("Abstract", "Introduction")),
    "method": DimensionConfig("研究方法", "研究方法 core method methodology approach algorithm framework", ("Method", "Approach")),
    "model_architecture": DimensionConfig("模型架构", "模型架构 model architecture components modules workflow", ("Method", "Approach")),
    "dataset": DimensionConfig("数据集", "数据集 dataset corpus benchmark evaluation data", ("Experiments", "Experimental Setup")),
    "training_strategy": DimensionConfig("训练策略", "训练策略 training optimization fine-tuning parameter update", ("Method", "Experiments")),
    "evaluation_metric": DimensionConfig("评测指标", "评测指标 evaluation metrics experimental setup", ("Experiments", "Results")),
    "main_result": DimensionConfig("主要结果", "主要结果 main results findings performance conclusion", ("Results", "Experiments", "Conclusion")),
    "innovation": DimensionConfig("创新点", "创新贡献 novelty innovation contribution compared with prior work", ("Abstract", "Introduction", "Conclusion")),
    "limitation": DimensionConfig("局限性", "局限性 limitations risks future work", ("Conclusion", "Results")),
}

DEFAULT_DIMENSIONS: list[ComparisonDimension] = ["method", "dataset", "main_result"]


class PaperComparisonAgent:
    def __init__(self, db: Session):
        self.db = db

    def run(
        self,
        user_id: str,
        paper_ids: list[int],
        question: str,
        requested_dimensions: list[ComparisonDimension] | None = None,
    ) -> PaperComparisonResponse:
        papers = self._authorized_papers(user_id, paper_ids)
        dimensions = requested_dimensions or self._plan_dimensions(question)
        evidence = self._collect_evidence(user_id, papers, dimensions)
        cells, summary = self._extract_and_validate(papers, dimensions, question, evidence)
        markdown = self._render_markdown(papers, dimensions, cells, summary)
        return PaperComparisonResponse(
            papers=[self._paper_model(paper) for paper in papers],
            dimensions=dimensions,
            cells=cells,
            summary=summary,
            markdown=markdown,
            evidence=evidence,
        )

    def _authorized_papers(self, user_id: str, paper_ids: list[int]) -> list[KnowledgeBase]:
        papers = self.db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.user_id == user_id,
                KnowledgeBase.id.in_(paper_ids),
            )
        ).scalars().all()
        by_id = {paper.id: paper for paper in papers}
        if any(paper_id not in by_id for paper_id in paper_ids):
            raise PaperAccessError("一个或多个论文不存在")
        return [by_id[paper_id] for paper_id in paper_ids]

    def _plan_dimensions(self, question: str) -> list[ComparisonDimension]:
        prompt = {
            "task": "从用户的论文比较要求中选择比较维度",
            "allowed_dimensions": list(DIMENSIONS),
            "user_question": question,
            "rules": "只返回 JSON：{\"dimensions\":[...]}; 最多6项。",
        }
        try:
            result = self._json_completion(json.dumps(prompt, ensure_ascii=False))
            planned = [item for item in result.get("dimensions", []) if item in DIMENSIONS]
            return list(dict.fromkeys(planned))[:6] or DEFAULT_DIMENSIONS
        except Exception:
            return self._fallback_dimensions(question)

    @staticmethod
    def _fallback_dimensions(question: str) -> list[ComparisonDimension]:
        keywords = {
            "method": ("方法", "算法", "流程"),
            "model_architecture": ("架构", "结构", "模块"),
            "dataset": ("数据集", "语料", "基准"),
            "training_strategy": ("训练", "优化", "微调"),
            "evaluation_metric": ("指标", "评测", "评价"),
            "main_result": ("结果", "效果", "性能"),
            "innovation": ("创新", "贡献", "新颖"),
            "limitation": ("局限", "不足", "缺点"),
            "research_problem": ("问题", "目标", "任务"),
        }
        selected = [key for key, words in keywords.items() if any(word in question for word in words)]
        return selected[:6] or DEFAULT_DIMENSIONS

    def _collect_evidence(
        self,
        user_id: str,
        papers: list[KnowledgeBase],
        dimensions: list[ComparisonDimension],
    ) -> list[ComparisonEvidence]:
        evidence: list[ComparisonEvidence] = []
        for paper in papers:
            for dimension in dimensions:
                config = DIMENSIONS[dimension]
                chunks = retrieve_content(
                    user_id,
                    config.query,
                    paper_ids=[paper.id],
                    sections=list(config.sections),
                    top_k=3,
                    db=self.db,
                )
                if not chunks:
                    chunks = retrieve_content(
                        user_id,
                        config.query,
                        paper_ids=[paper.id],
                        top_k=3,
                        db=self.db,
                    )
                for chunk in chunks:
                    evidence.append(ComparisonEvidence(
                        evidence_id=str(len(evidence) + 1),
                        dimension=dimension,
                        chunk_id=chunk.get("chunk_id"),
                        paper_id=str(paper.id),
                        paper_title=paper.title or paper.file_name,
                        document_id=str(chunk.get("document_id", "")),
                        document_name=paper.file_name,
                        section=chunk.get("section"),
                        page=chunk.get("page"),
                        content_with_weight=chunk.get("content_with_weight", ""),
                        score=float(chunk.get("score", 0.0)),
                    ))
        return evidence

    def _extract_and_validate(
        self,
        papers: list[KnowledgeBase],
        dimensions: list[ComparisonDimension],
        question: str,
        evidence: list[ComparisonEvidence],
    ) -> tuple[list[ComparisonCell], str]:
        evidence_payload = [item.model_dump() for item in evidence]
        prompt = {
            "task": "根据证据生成逐论文、逐维度的比较事实",
            "question": question,
            "papers": [self._paper_model(paper).model_dump() for paper in papers],
            "dimensions": dimensions,
            "evidence": evidence_payload,
            "output": {
                "cells": [{
                    "paper_id": "论文ID",
                    "dimension": "维度",
                    "status": "found|partial|not_found|not_applicable",
                    "summary": "仅基于证据的简洁结论",
                    "evidence_ids": ["1"],
                }],
                "summary": "2到4条Markdown无序列表形式的综合结论",
            },
            "rules": [
                "每篇论文的每个维度必须有一个cell",
                "不得使用证据以外的事实",
                "evidence_ids必须属于对应论文",
                "证据不足时使用not_found",
                "summary必须直接概括最重要的共同点、差异和选择启示，不得只说已完成比较",
                "summary中的每一条都必须能由cells中的事实支持，不要自行编造引用编号",
                "只返回JSON",
            ],
        }
        try:
            raw = self._json_completion(json.dumps(prompt, ensure_ascii=False))
        except Exception:
            raw = {"cells": [], "summary": "已按所选维度整理现有证据。"}

        valid_evidence = {item.evidence_id: item for item in evidence}
        raw_cells = {
            (str(item.get("paper_id")), item.get("dimension")): item
            for item in raw.get("cells", [])
            if isinstance(item, dict)
        }
        cells: list[ComparisonCell] = []
        for paper in papers:
            for dimension in dimensions:
                item = raw_cells.get((str(paper.id), dimension), {})
                ids = [
                    evidence_id for evidence_id in item.get("evidence_ids", [])
                    if evidence_id in valid_evidence
                    and valid_evidence[evidence_id].paper_id == str(paper.id)
                    and valid_evidence[evidence_id].dimension == dimension
                ]
                summary = str(item.get("summary", "")).strip()
                status = item.get("status", "not_found")
                if status not in {"found", "partial", "not_found", "not_applicable"}:
                    status = "partial" if ids else "not_found"
                if status in {"found", "partial"} and not ids:
                    status = "not_found"
                    summary = "当前证据中未找到明确说明。"
                cells.append(ComparisonCell(
                    paper_id=str(paper.id),
                    dimension=dimension,
                    status=status,
                    summary=summary or "当前证据中未找到明确说明。",
                    evidence_ids=list(dict.fromkeys(ids)),
                ))
        summary = str(raw.get("summary", "")).strip()
        if not summary or summary in {
            "已完成所选论文的证据化比较。",
            "已按所选维度整理现有证据。",
        }:
            summary = PaperComparisonAgent._fallback_summary(papers, dimensions, cells)
        return cells, summary

    @staticmethod
    def _fallback_summary(
        papers: list[KnowledgeBase],
        dimensions: list[ComparisonDimension],
        cells: list[ComparisonCell],
    ) -> str:
        """Build a useful grounded summary if the model returns boilerplate."""
        by_key = {(cell.paper_id, cell.dimension): cell for cell in cells}
        points: list[str] = []
        for dimension in dimensions[:3]:
            descriptions = []
            for paper in papers:
                cell = by_key[(str(paper.id), dimension)]
                if cell.status in {"found", "partial"}:
                    descriptions.append(f"**{paper.title or paper.file_name}**：{cell.summary}")
            if descriptions:
                points.append(f"- **{DIMENSIONS[dimension].label}**：" + "；".join(descriptions))
        return "\n".join(points) or "- 当前检索证据不足，暂时无法形成可靠的综合结论。"

    def _json_completion(self, prompt: str) -> dict:
        client = OpenAI(api_key=get_model_api_key(), base_url=get_model_base_url())
        response = client.chat.completions.create(
            model=os.getenv("CHAT_MODEL", "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            stream=False,
            timeout=60,
        )
        content = response.choices[0].message.content or "{}"
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I | re.S)
        return json.loads(content)

    @staticmethod
    def _paper_model(paper: KnowledgeBase) -> ComparisonPaper:
        return ComparisonPaper(
            paper_id=str(paper.id),
            title=paper.title or paper.file_name,
            authors=paper.authors or [],
            year=paper.year,
        )

    @staticmethod
    def _render_markdown(
        papers: list[KnowledgeBase],
        dimensions: list[ComparisonDimension],
        cells: list[ComparisonCell],
        summary: str,
    ) -> str:
        by_key = {(cell.paper_id, cell.dimension): cell for cell in cells}
        paper_headers = [
            f"论文 {chr(65 + index)}：{paper.title or paper.file_name}"
            for index, paper in enumerate(papers)
        ]
        header = "| 比较维度 | " + " | ".join(paper_headers) + " |"
        separator = "| --- | " + " | ".join("---" for _ in papers) + " |"
        rows = [header, separator]
        for dimension in dimensions:
            values = []
            for paper in papers:
                cell = by_key[(str(paper.id), dimension)]
                citations = "".join(f"[{evidence_id}]" for evidence_id in cell.evidence_ids)
                status_prefix = {
                    "found": "",
                    "partial": "⚠️ **证据有限：** ",
                    "not_found": "⚠️ **未检索到明确证据：** ",
                    "not_applicable": "**不适用：** ",
                }[cell.status]
                value = f"{status_prefix}{cell.summary}{citations}"
                values.append(value.replace("\n", "<br>").replace("|", "\\|"))
            rows.append(f"| {DIMENSIONS[dimension].label} | " + " | ".join(values) + " |")
        return (
            "## 核心结论\n\n"
            + summary
            + "\n\n## 对比总览\n\n"
            + "\n".join(rows)
            + "\n\n> 结论仅基于当前检索到的论文切片；带有“证据有限”标记的内容建议结合原文进一步核对。"
        )

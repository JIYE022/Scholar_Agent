from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone

from openai import OpenAI

from schemas.external_search import (
    ExternalPaper,
    ExternalPaperSearchRequest,
    ExternalPaperSearchResponse,
    ExternalSearchPlan,
)
from tools.paper_search import PaperSearchService
from tools.paper_search.normalize import deduplicate_papers, rank_papers
from utils.model_config import get_model_api_key, get_model_base_url


class ExternalPaperSearchAgent:
    def __init__(self):
        self.search_service = PaperSearchService()

    def run(self, request: ExternalPaperSearchRequest) -> ExternalPaperSearchResponse:
        plan = self._plan(request)
        raw_papers, warnings = self.search_service.search(plan)
        unique_papers = deduplicate_papers(raw_papers)
        ranked = rank_papers(unique_papers, plan)[:request.limit]
        summary, reasons = self._summarize(request.query, ranked)
        for index, paper in enumerate(ranked):
            paper.relevance_reason = reasons.get(str(index + 1))
        markdown = self._render_markdown(summary, ranked, warnings)
        return ExternalPaperSearchResponse(
            query_plan=plan,
            papers=ranked,
            summary=summary,
            total_found=len(unique_papers),
            returned_count=len(ranked),
            sources=plan.sources,
            warnings=warnings,
            searched_at=datetime.now(timezone.utc),
            markdown=markdown,
        )

    def _plan(self, request: ExternalPaperSearchRequest) -> ExternalSearchPlan:
        prompt = {
            "task": "将用户的外部论文检索需求转换为简洁、可执行的学术搜索计划",
            "user_query": request.query,
            "explicit_filters": {
                "year_from": request.year_from,
                "year_to": request.year_to,
                "sort": request.sort,
            },
            "output": {
                "search_query": "优先使用适合国际学术数据库检索的英文主题短语",
                "keywords": ["最多8个中英文关键词"],
                "authors": ["用户明确提到的作者"],
                "year_from": "整数或null",
                "year_to": "整数或null",
                "sort": "relevance|newest|cited",
            },
            "rules": [
                "不要生成URL",
                "不要虚构用户未提出的作者、年份和研究条件",
                "search_query应聚焦研究主题，不包含找论文、推荐论文等指令词",
                "只返回JSON",
            ],
        }
        try:
            raw = self._json_completion(json.dumps(prompt, ensure_ascii=False), timeout=45)
        except Exception:
            raw = {}

        search_query = str(raw.get("search_query") or request.query).strip()[:300]
        keywords = [str(item).strip()[:80] for item in raw.get("keywords", []) if str(item).strip()][:8]
        authors = [str(item).strip()[:100] for item in raw.get("authors", []) if str(item).strip()][:5]
        sort = request.sort or raw.get("sort")
        if sort not in {"relevance", "newest", "cited"}:
            sort = self._fallback_sort(request.query)
        year_from = request.year_from or self._valid_year(raw.get("year_from"))
        year_to = request.year_to or self._valid_year(raw.get("year_to"))
        if year_from and year_to and year_from > year_to:
            year_from, year_to = request.year_from, request.year_to
        return ExternalSearchPlan(
            original_query=request.query,
            search_query=search_query,
            keywords=keywords,
            authors=authors,
            year_from=year_from,
            year_to=year_to,
            sort=sort,
            sources=request.sources,
            limit=request.limit,
        )

    def _summarize(
        self,
        query: str,
        papers: list[ExternalPaper],
    ) -> tuple[str, dict[str, str]]:
        if not papers:
            return "未检索到符合当前条件的论文。可以尝试放宽年份限制或使用更通用的英文关键词。", {}
        payload = []
        for index, paper in enumerate(papers, start=1):
            payload.append({
                "index": index,
                "title": paper.title,
                "year": paper.year,
                "venue": paper.venue,
                "abstract": (paper.abstract or "")[:1200],
                "keywords": paper.keywords,
            })
        prompt = {
            "task": "只根据公开论文元数据与摘要，总结本次外部论文搜索结果",
            "query": query,
            "papers": payload,
            "output": {
                "summary": "2到4条Markdown无序列表，概括研究趋势、结果覆盖和优先阅读建议",
                "reasons": {"1": "用一句话解释该论文为什么与查询相关"},
            },
            "rules": [
                "不得声称已阅读论文全文",
                "不得使用输入之外的事实",
                "reasons的编号必须来自papers中的index",
                "避免空泛地说已完成搜索",
                "只返回JSON",
            ],
        }
        try:
            raw = self._json_completion(json.dumps(prompt, ensure_ascii=False), timeout=60)
            summary = str(raw.get("summary") or "").strip()
            reasons = {
                str(key): str(value).strip()
                for key, value in (raw.get("reasons") or {}).items()
                if str(key).isdigit() and str(value).strip()
            }
            if summary:
                return summary, reasons
        except Exception:
            pass
        years = [paper.year for paper in papers if paper.year]
        year_text = f"，年份覆盖 {min(years)}–{max(years)}" if years else ""
        return (
            f"- 共筛选出 **{len(papers)}** 篇相关论文{year_text}。\n"
            f"- 排名前列的工作包括 **{papers[0].title}**，建议先根据摘要确认相关性，再决定是否阅读全文。",
            {},
        )

    def _json_completion(self, prompt: str, timeout: int) -> dict:
        client = OpenAI(api_key=get_model_api_key(), base_url=get_model_base_url())
        response = client.chat.completions.create(
            model=os.getenv("CHAT_MODEL", "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            stream=False,
            timeout=timeout,
        )
        content = response.choices[0].message.content or "{}"
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I | re.S)
        return json.loads(content)

    @staticmethod
    def _fallback_sort(query: str) -> str:
        if any(word in query.casefold() for word in ("最新", "近期", "recent", "newest", "latest")):
            return "newest"
        if any(word in query.casefold() for word in ("经典", "高引用", "highly cited", "influential")):
            return "cited"
        return "relevance"

    @staticmethod
    def _valid_year(value) -> int | None:
        try:
            year = int(value)
            return year if 1900 <= year <= 2100 else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _render_markdown(summary: str, papers: list[ExternalPaper], warnings: list[str]) -> str:
        lines = ["## 搜索总结", "", summary, ""]
        if warnings:
            lines.extend(["> " + "；".join(warnings), ""])
        lines.extend([
            "> 以下内容来自外部平台公开的论文元数据和摘要，不代表已完成全文分析。",
            "",
            "## 论文结果",
            "",
        ])
        if not papers:
            lines.append("未找到结果。")
            return "\n".join(lines)
        for index, paper in enumerate(papers, start=1):
            title = html.escape(paper.title)
            authors = "、".join(html.escape(author) for author in paper.authors[:5]) or "未知"
            if len(paper.authors) > 5:
                authors += " 等"
            metadata = [str(paper.year) if paper.year else "年份未知", paper.venue or "来源未知"]
            if paper.citation_count is not None:
                metadata.append(f"引用 {paper.citation_count}")
            links = [f"[查看详情]({paper.landing_url})"]
            if paper.pdf_url:
                links.append(f"[PDF]({paper.pdf_url})")
            lines.extend([
                f"### {index}. {title}",
                "",
                f"- **作者：** {authors}",
                f"- **信息：** {' · '.join(html.escape(item) for item in metadata)}",
                f"- **来源：** {', '.join(paper.sources)}",
            ])
            if paper.relevance_reason:
                lines.append(f"- **推荐理由：** {html.escape(paper.relevance_reason)}")
            lines.extend([f"- {' · '.join(links)}", ""])
        return "\n".join(lines)

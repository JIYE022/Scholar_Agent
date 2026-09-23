import re
from datetime import datetime

from schemas.external_search import ExternalPaper, ExternalSearchPlan


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", title.casefold())


def deduplicate_papers(papers: list[ExternalPaper]) -> list[ExternalPaper]:
    merged: dict[str, ExternalPaper] = {}
    aliases: dict[str, str] = {}
    for paper in papers:
        keys = []
        if paper.doi:
            keys.append(f"doi:{paper.doi.casefold().strip()}")
        if paper.arxiv_id:
            keys.append(f"arxiv:{paper.arxiv_id.casefold().strip()}")
        keys.append(f"title:{normalize_title(paper.title)}")
        canonical = next((aliases[key] for key in keys if key in aliases), keys[0])
        if canonical not in merged:
            merged[canonical] = paper.model_copy(deep=True)
        else:
            merged[canonical] = _merge(merged[canonical], paper)
        for key in keys:
            aliases[key] = canonical
    return list(merged.values())


def rank_papers(papers: list[ExternalPaper], plan: ExternalSearchPlan) -> list[ExternalPaper]:
    terms = {
        token.casefold()
        for value in [plan.search_query, *plan.keywords]
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9+.-]{1,}|[\u4e00-\u9fff]{2,}", value)
    }
    max_citations = max((paper.citation_count or 0 for paper in papers), default=0) or 1
    current_year = plan.year_to or datetime.now().year
    for paper in papers:
        title = paper.title.casefold()
        abstract = (paper.abstract or "").casefold()
        title_hits = sum(term in title for term in terms)
        abstract_hits = sum(term in abstract for term in terms)
        lexical = (3 * title_hits + abstract_hits) / max(4 * len(terms), 1)
        citation_signal = (paper.citation_count or 0) / max_citations
        recency = max(0.0, 1.0 - max(0, current_year - (paper.year or 1900)) / 10)
        provider_signal = min(paper.relevance_score / 100.0, 1.0)
        if plan.sort == "newest":
            score = 0.55 * recency + 0.35 * lexical + 0.1 * provider_signal
        elif plan.sort == "cited":
            score = 0.55 * citation_signal + 0.35 * lexical + 0.1 * provider_signal
        else:
            score = 0.7 * lexical + 0.2 * provider_signal + 0.1 * recency
        paper.relevance_score = round(score, 4)
    return sorted(
        papers,
        key=lambda paper: (
            paper.relevance_score,
            paper.year or 0,
            paper.citation_count or 0,
        ),
        reverse=True,
    )


def _merge(left: ExternalPaper, right: ExternalPaper) -> ExternalPaper:
    # Prefer the richer record while retaining identifiers and links from both.
    richer, other = (right, left) if len(right.abstract or "") > len(left.abstract or "") else (left, right)
    data = richer.model_dump()
    for field in ("abstract", "year", "published_at", "doi", "arxiv_id", "venue", "citation_count", "pdf_url"):
        if data.get(field) in (None, "", []):
            data[field] = getattr(other, field)
    data["authors"] = list(dict.fromkeys([*richer.authors, *other.authors]))
    data["keywords"] = list(dict.fromkeys([*richer.keywords, *other.keywords]))[:8]
    data["sources"] = list(dict.fromkeys([*left.sources, *right.sources]))
    data["relevance_score"] = max(left.relevance_score, right.relevance_score)
    return ExternalPaper(**data)

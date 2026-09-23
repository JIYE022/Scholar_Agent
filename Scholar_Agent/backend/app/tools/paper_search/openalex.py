import os
import re

import requests

from schemas.external_search import ExternalPaper, ExternalSearchPlan
from tools.paper_search.base import PaperSearchProvider


class OpenAlexProvider(PaperSearchProvider):
    name = "openalex"
    endpoint = "https://api.openalex.org/works"

    def search(self, plan: ExternalSearchPlan) -> list[ExternalPaper]:
        filters: list[str] = []
        if plan.year_from:
            filters.append(f"from_publication_date:{plan.year_from}-01-01")
        if plan.year_to:
            filters.append(f"to_publication_date:{plan.year_to}-12-31")

        sort = {
            "newest": "publication_date:desc",
            "cited": "cited_by_count:desc",
        }.get(plan.sort)
        params: dict[str, str | int] = {
            "search": " ".join([plan.search_query, *plan.authors]).strip(),
            "per-page": min(max(plan.limit * 2, 10), 40),
        }
        if filters:
            params["filter"] = ",".join(filters)
        if sort:
            params["sort"] = sort
        if os.getenv("OPENALEX_EMAIL"):
            params["mailto"] = os.environ["OPENALEX_EMAIL"]

        response = requests.get(
            self.endpoint,
            params=params,
            headers={"User-Agent": os.getenv("PAPER_SEARCH_USER_AGENT", "ScholarAgent/1.0")},
            timeout=(5, 20),
        )
        response.raise_for_status()
        return [self._to_paper(item) for item in response.json().get("results", [])]

    @staticmethod
    def _to_paper(item: dict) -> ExternalPaper:
        primary = item.get("primary_location") or {}
        source = primary.get("source") or {}
        open_access = item.get("open_access") or {}
        doi = item.get("doi")
        if doi:
            doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.I)
        landing_url = OpenAlexProvider._safe_url(
            primary.get("landing_page_url") or item.get("id"),
            "https://openalex.org",
        )
        pdf_url = OpenAlexProvider._safe_url(primary.get("pdf_url") or open_access.get("oa_url"))
        authors = [
            authorship.get("author", {}).get("display_name")
            for authorship in item.get("authorships", [])
            if authorship.get("author", {}).get("display_name")
        ]
        keywords = [
            concept.get("display_name")
            for concept in item.get("concepts", [])[:6]
            if concept.get("display_name")
        ]
        return ExternalPaper(
            external_id=f"openalex:{str(item.get('id', '')).rsplit('/', 1)[-1]}",
            title=item.get("display_name") or item.get("title") or "Untitled",
            authors=authors,
            abstract=OpenAlexProvider._restore_abstract(item.get("abstract_inverted_index")),
            year=item.get("publication_year"),
            published_at=item.get("publication_date"),
            doi=doi,
            venue=source.get("display_name"),
            citation_count=item.get("cited_by_count"),
            sources=["openalex"],
            landing_url=landing_url,
            pdf_url=pdf_url,
            keywords=keywords,
            relevance_score=float(item.get("relevance_score") or 0.0),
        )

    @staticmethod
    def _restore_abstract(inverted_index: dict | None) -> str | None:
        if not inverted_index:
            return None
        positions = [
            (position, word)
            for word, indices in inverted_index.items()
            for position in indices
        ]
        positions.sort(key=lambda item: item[0])
        return " ".join(word for _, word in positions) or None

    @staticmethod
    def _safe_url(value: str | None, fallback: str | None = None) -> str | None:
        return value if value and value.lower().startswith(("https://", "http://")) else fallback

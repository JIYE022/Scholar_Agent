import os
import re
import xml.etree.ElementTree as ET

import requests

from schemas.external_search import ExternalPaper, ExternalSearchPlan
from tools.paper_search.base import PaperSearchProvider


class ArxivProvider(PaperSearchProvider):
    name = "arxiv"
    endpoint = "https://export.arxiv.org/api/query"
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

    def search(self, plan: ExternalSearchPlan) -> list[ExternalPaper]:
        safe_query = plan.search_query.replace('"', " ").strip()
        author_query = "".join(
            f' AND au:"{author.replace(chr(34), " ")}"'
            for author in plan.authors
        )
        params = {
            "search_query": f'all:"{safe_query}"{author_query}',
            "start": 0,
            "max_results": min(max(plan.limit * 2, 10), 40),
            "sortBy": "submittedDate" if plan.sort == "newest" else "relevance",
            "sortOrder": "descending",
        }
        response = requests.get(
            self.endpoint,
            params=params,
            headers={"User-Agent": os.getenv("PAPER_SEARCH_USER_AGENT", "ScholarAgent/1.0")},
            timeout=(5, 25),
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        papers = [self._to_paper(entry) for entry in root.findall("atom:entry", self.ns)]
        return [
            paper for paper in papers
            if (not plan.year_from or (paper.year and paper.year >= plan.year_from))
            and (not plan.year_to or (paper.year and paper.year <= plan.year_to))
        ]

    def _to_paper(self, entry: ET.Element) -> ExternalPaper:
        id_url = self._text(entry, "atom:id") or ""
        arxiv_id = re.sub(r"v\d+$", "", id_url.rsplit("/", 1)[-1])
        published = self._text(entry, "atom:published")
        links = {
            link.attrib.get("rel", "alternate"): link.attrib.get("href")
            for link in entry.findall("atom:link", self.ns)
        }
        pdf_link = next(
            (link.attrib.get("href") for link in entry.findall("atom:link", self.ns)
             if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf"),
            None,
        )
        authors = [
            self._text(author, "atom:name") or ""
            for author in entry.findall("atom:author", self.ns)
        ]
        categories = [node.attrib.get("term") for node in entry.findall("atom:category", self.ns)]
        return ExternalPaper(
            external_id=f"arxiv:{arxiv_id}",
            title=self._clean(self._text(entry, "atom:title")) or "Untitled",
            authors=[author for author in authors if author],
            abstract=self._clean(self._text(entry, "atom:summary")),
            year=int(published[:4]) if published and published[:4].isdigit() else None,
            published_at=published[:10] if published else None,
            doi=self._text(entry, "arxiv:doi"),
            arxiv_id=arxiv_id,
            venue=self._text(entry, "arxiv:journal_ref") or "arXiv",
            sources=["arxiv"],
            landing_url=self._safe_url(links.get("alternate") or id_url, "https://arxiv.org"),
            pdf_url=self._safe_url(pdf_link),
            keywords=[item for item in categories if item],
        )

    def _text(self, element: ET.Element, path: str) -> str | None:
        node = element.find(path, self.ns)
        return node.text.strip() if node is not None and node.text else None

    @staticmethod
    def _clean(value: str | None) -> str | None:
        return re.sub(r"\s+", " ", value).strip() if value else None

    @staticmethod
    def _safe_url(value: str | None, fallback: str | None = None) -> str | None:
        return value if value and value.lower().startswith(("https://", "http://")) else fallback

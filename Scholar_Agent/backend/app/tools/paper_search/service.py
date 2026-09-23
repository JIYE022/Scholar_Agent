from concurrent.futures import ThreadPoolExecutor, as_completed

from schemas.external_search import ExternalPaper, ExternalSearchPlan
from tools.paper_search.arxiv import ArxivProvider
from tools.paper_search.base import PaperSearchProvider
from tools.paper_search.openalex import OpenAlexProvider


class PaperSearchService:
    """Run one or more paper providers behind a stable application interface."""

    def __init__(self, providers: dict[str, PaperSearchProvider] | None = None):
        self.providers = providers or {
            "openalex": OpenAlexProvider(),
            "arxiv": ArxivProvider(),
        }

    def search(self, plan: ExternalSearchPlan) -> tuple[list[ExternalPaper], list[str]]:
        papers: list[ExternalPaper] = []
        warnings: list[str] = []
        with ThreadPoolExecutor(max_workers=len(plan.sources)) as executor:
            futures = {
                executor.submit(self.providers[source].search, plan): source
                for source in plan.sources
            }
            for future in as_completed(futures):
                source = futures[future]
                try:
                    papers.extend(future.result())
                except Exception as exc:
                    warnings.append(f"{source} 暂时不可用：{type(exc).__name__}")
        return papers, warnings

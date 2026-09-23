from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from schemas.external_search import ExternalPaper, ExternalSearchPlan
from tools.paper_search import PaperSearchService
from tools.paper_search.normalize import deduplicate_papers, rank_papers


PaperSource = Literal["openalex", "arxiv"]
PaperSort = Literal["relevance", "newest", "cited"]


class PaperSearchFilters(BaseModel):
    sources: list[PaperSource]
    year_from: int | None = None
    year_to: int | None = None
    sort: PaperSort
    authors: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class PaperSearchResult(BaseModel):
    query: str
    filters: PaperSearchFilters
    candidate_count: int
    returned_count: int
    warnings: list[str] = Field(default_factory=list)
    papers: list[ExternalPaper]
    notice: str


class PaperSearchProviderInfo(BaseModel):
    id: PaperSource
    name: str
    content: str


class PaperSearchProvidersResult(BaseModel):
    providers: list[PaperSearchProviderInfo]

mcp = MCPServer(
    "scholar-paper-search",
    title="Scholar Paper Search",
    description="Search public scholarly metadata from OpenAlex and arXiv.",
    instructions=(
        "Use search_papers when the user wants to discover external academic papers. "
        "Results contain public metadata and abstracts, not verified full-text evidence."
    ),
    version="1.0.0",
)


@mcp.tool(
    title="Search external academic papers",
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=True,
    ),
)
def search_papers(
    query: Annotated[
        str,
        Field(
            min_length=2,
            max_length=300,
            description="Focused academic search phrase; English generally gives broader coverage.",
        ),
    ],
    limit: Annotated[
        int,
        Field(ge=1, le=20, description="Maximum number of deduplicated papers to return."),
    ] = 10,
    sources: Annotated[
        list[PaperSource] | None,
        Field(description="Providers to search. Defaults to both OpenAlex and arXiv."),
    ] = None,
    year_from: Annotated[
        int | None,
        Field(ge=1900, le=2100, description="Earliest publication year, inclusive."),
    ] = None,
    year_to: Annotated[
        int | None,
        Field(ge=1900, le=2100, description="Latest publication year, inclusive."),
    ] = None,
    sort: PaperSort = "relevance",
    authors: Annotated[
        list[str] | None,
        Field(max_length=5, description="Optional author names explicitly requested by the user."),
    ] = None,
    keywords: Annotated[
        list[str] | None,
        Field(max_length=8, description="Optional keywords used for local relevance ranking."),
    ] = None,
) -> PaperSearchResult:
    """Search OpenAlex/arXiv, normalize records, remove duplicates, and rank results."""
    selected_sources = list(dict.fromkeys(sources or ["openalex", "arxiv"]))
    if year_from and year_to and year_from > year_to:
        raise ValueError("year_from must not be later than year_to")

    plan = ExternalSearchPlan(
        original_query=query,
        search_query=query,
        keywords=keywords or [],
        authors=authors or [],
        year_from=year_from,
        year_to=year_to,
        sort=sort,
        sources=selected_sources,
        limit=limit,
    )
    raw_papers, warnings = PaperSearchService().search(plan)
    unique_papers = deduplicate_papers(raw_papers)
    ranked_papers = rank_papers(unique_papers, plan)[:limit]
    return PaperSearchResult(
        query=query,
        filters=PaperSearchFilters(
            sources=selected_sources,
            year_from=year_from,
            year_to=year_to,
            sort=sort,
            authors=authors or [],
            keywords=keywords or [],
        ),
        candidate_count=len(unique_papers),
        returned_count=len(ranked_papers),
        warnings=warnings,
        papers=ranked_papers,
        notice="Results are based on public metadata and abstracts, not full-text analysis.",
    )


@mcp.tool(
    title="List paper search providers",
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
def list_paper_search_providers() -> PaperSearchProvidersResult:
    """List the external scholarly providers supported by this server."""
    return PaperSearchProvidersResult(
        providers=[
            PaperSearchProviderInfo(
                id="openalex",
                name="OpenAlex",
                content="metadata and abstracts",
            ),
            PaperSearchProviderInfo(
                id="arxiv",
                name="arXiv",
                content="preprint metadata and abstracts",
            ),
        ]
    )


if __name__ == "__main__":
    mcp.run()

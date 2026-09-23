declare namespace API {
  type ExternalPaperSource = 'openalex' | 'arxiv'
  type ExternalSearchSort = 'relevance' | 'newest' | 'cited'

  type ExternalPaper = {
    external_id: string
    title: string
    authors: string[]
    abstract?: string | null
    year?: number | null
    published_at?: string | null
    doi?: string | null
    arxiv_id?: string | null
    venue?: string | null
    citation_count?: number | null
    sources: ExternalPaperSource[]
    landing_url: string
    pdf_url?: string | null
    keywords: string[]
    relevance_score: number
    relevance_reason?: string | null
  }

  type ExternalPaperSearchResult = {
    query_plan: {
      original_query: string
      search_query: string
      keywords: string[]
      authors: string[]
      year_from?: number | null
      year_to?: number | null
      sort: ExternalSearchSort
      sources: ExternalPaperSource[]
      limit: number
    }
    papers: ExternalPaper[]
    summary: string
    total_found: number
    returned_count: number
    sources: ExternalPaperSource[]
    warnings: string[]
    searched_at: string
    markdown: string
  }
}

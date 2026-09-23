declare namespace API {
  type ComparisonDimension =
    | 'research_problem'
    | 'method'
    | 'model_architecture'
    | 'dataset'
    | 'training_strategy'
    | 'evaluation_metric'
    | 'main_result'
    | 'innovation'
    | 'limitation'

  type ComparisonEvidence = Reference & {
    evidence_id: string
    dimension: ComparisonDimension
    paper_id: string
    paper_title: string
    section?: string | null
    page?: number | null
    score: number
  }

  type PaperComparisonResult = {
    papers: {
      paper_id: string
      title: string
      authors: string[]
      year?: number | null
    }[]
    dimensions: ComparisonDimension[]
    cells: {
      paper_id: string
      dimension: ComparisonDimension
      status: 'found' | 'partial' | 'not_found' | 'not_applicable'
      summary: string
      evidence_ids: string[]
    }[]
    summary: string
    markdown: string
    evidence: ComparisonEvidence[]
  }
}

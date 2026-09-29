declare namespace API {
  type ReadStatus = 'unread' | 'reading' | 'read' | 'archived'

  type PaperMetadata = {
    title: string
    authors: string[]
    year?: number | null
    venue?: string | null
    doi?: string | null
    keywords: string[]
    abstract?: string | null
    research_topic?: string | null
    read_status: ReadStatus
    personal_tags: string[]
  }

  type PaperUpdate = Partial<PaperMetadata>

  type Paper = Omit<PaperMetadata, 'title'> & {
    id: number
    title: string | null
    created_at: string
    file_name: string
    updated_at: string
    user_id: string
    chunk_count: number
  }

  type UploadTaskStatus = 'queued' | 'processing' | 'succeeded' | 'failed'

  type UploadTask = {
    task_id: string
    file_name: string
    session_id: string
    status: UploadTaskStatus
    stage: string
    progress: number
    message: string
    created_at: string
    updated_at: string
    started_at?: string
    completed_at?: string
    error?: string
    result?: {
      paper_id: number
      file_name: string
      chunk_count: number
      recovered?: boolean
    }
  }
}

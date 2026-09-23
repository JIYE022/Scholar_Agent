import { AxiosRequestConfig } from 'axios'
import { request } from './request'

export function search(
  params: {
    session_id: string
    query: string
    limit?: number
    sources?: API.ExternalPaperSource[]
    year_from?: number
    year_to?: number
    sort?: API.ExternalSearchSort
  },
  options?: AxiosRequestConfig,
) {
  return request.post<API.ExternalPaperSearchResult>(
    '/agents/external-paper-search',
    params,
    options,
  )
}

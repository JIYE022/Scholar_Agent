import { AxiosRequestConfig } from 'axios'
import { request } from './request'

export function compare(
  params: {
    session_id: string
    paper_ids: number[]
    question: string
    dimensions?: API.ComparisonDimension[]
  },
  options?: AxiosRequestConfig,
) {
  return request.post<API.PaperComparisonResult>(
    '/agents/paper-comparison',
    params,
    options,
  )
}

import { AxiosRequestConfig } from 'axios'
import { request } from './request'

export function list(params?: {}, options?: AxiosRequestConfig) {
  return request.get<API.Paper[]>('/get_files', {
    ...options,
    params,
  })
}

export function upload(
  params: { file: File; metadata: API.PaperMetadata },
  options?: AxiosRequestConfig,
) {
  const form = new FormData()
  form.append('files', params.file)
  form.append('metadata', JSON.stringify(params.metadata))
  return request.post<
    API.Result<{ successful_files: { paper_id: number; file_name: string }[] }>
  >(`/upload_files`, form, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    ...options,
  })
}

export function remove(
  params: { paper_id: number },
  options?: AxiosRequestConfig,
) {
  return request.delete(`/papers/${params.paper_id}`, {
    ...options,
  })
}

export function update(
  params: { paper_id: number; changes: API.PaperUpdate },
  options?: AxiosRequestConfig,
) {
  return request.patch<API.Paper>(
    `/papers/${params.paper_id}`,
    params.changes,
    options,
  )
}

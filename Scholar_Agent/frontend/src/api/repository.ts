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
    API.Result<{
      task_id: string
      tasks: { task_id: string; file_name: string; task_status: 'queued' }[]
      failed_files: string[]
      total_files: number
    }>
  >(`/upload_files`, form, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    ...options,
  })
}

export function uploadTask(taskId: string, options?: AxiosRequestConfig) {
  return request.get<API.Result<{ task: API.UploadTask }>>(
    `/upload_tasks/${taskId}`,
    options,
  )
}

export async function waitForUploadTask(
  taskId: string,
  intervalMs = 3000,
): Promise<API.UploadTask> {
  let consecutiveErrors = 0

  while (true) {
    try {
      const response = await uploadTask(taskId, {
        loading: false,
        errorToast: false,
        cancelRepeat: false,
      })
      const task = response.data.task
      consecutiveErrors = 0

      if (task.status === 'succeeded') return task
      if (task.status === 'failed') {
        throw new Error(task.error || task.message || '论文解析失败')
      }
    } catch (error) {
      if (error instanceof Error && !('response' in error)) throw error
      consecutiveErrors += 1
      if (consecutiveErrors >= 20) {
        throw new Error('暂时无法获取解析状态，后台任务可能仍在运行，请稍后刷新知识库')
      }
    }

    await new Promise((resolve) => window.setTimeout(resolve, intervalMs))
  }
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

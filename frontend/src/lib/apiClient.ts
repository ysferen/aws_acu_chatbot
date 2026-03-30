import type {
  ApiEnvelope,
  ApiErrorDetail,
  ChatRequest,
  ChatResponseData,
  FeedbackRequest,
  FeedbackResponseData,
  SessionMessagesResponseData,
  SourceResponseData,
} from '../types/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export class HttpError extends Error {
  status: number
  code?: string
  details: ApiErrorDetail[]
  requestId?: string
  retryAfterSeconds?: number

  constructor(message: string, status: number, code?: string, details: ApiErrorDetail[] = [], requestId?: string) {
    super(message)
    this.name = 'HttpError'
    this.status = status
    this.code = code
    this.details = details
    this.requestId = requestId
    this.retryAfterSeconds = this.resolveRetryAfter(details)
  }

  private resolveRetryAfter(details: ApiErrorDetail[]): number | undefined {
    const detail = details.find((item) => item.field === 'retry_after_seconds')
    if (typeof detail?.value === 'number') {
      return detail.value
    }
    return undefined
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
    ...init,
  })

  let body: ApiEnvelope<T>
  try {
    body = (await response.json()) as ApiEnvelope<T>
  } catch {
    throw new HttpError('Invalid JSON response from server.', response.status)
  }

  if (!response.ok || !body.ok) {
    const errorBody = 'error' in body ? body.error : undefined
    throw new HttpError(
      errorBody?.message || 'Request failed.',
      response.status,
      errorBody?.code,
      errorBody?.details || [],
      body.meta?.request_id,
    )
  }

  return body.data
}

export function postChat(payload: ChatRequest) {
  return request<ChatResponseData>('/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getSessionMessages(sessionId: string, cursor?: string) {
  const params = new URLSearchParams({
    order: 'asc',
    limit: '50',
  })

  if (cursor) {
    params.set('cursor', cursor)
  }

  return request<SessionMessagesResponseData>(`/sessions/${encodeURIComponent(sessionId)}/messages?${params.toString()}`)
}

export function postFeedback(payload: FeedbackRequest) {
  return request<FeedbackResponseData>('/feedback', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getSourceById(sourceId: string, chunkId?: string) {
  const params = new URLSearchParams()
  if (chunkId) {
    params.set('chunk_id', chunkId)
  }
  const query = params.toString()
  const suffix = query ? `?${query}` : ''
  return request<SourceResponseData>(`/sources/${encodeURIComponent(sourceId)}${suffix}`)
}

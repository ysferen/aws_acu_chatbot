export type ApiErrorDetail = {
  field?: string
  reason?: string
  value?: string | number | boolean | null
}

export type ApiMeta = {
  request_id: string
  timestamp: string
}

export type ApiErrorBody = {
  code: string
  message: string
  details: ApiErrorDetail[]
  retryable: boolean
}

export type ApiSuccessEnvelope<T> = {
  ok: true
  meta: ApiMeta
  request_id: string
  timestamp: string
  data: T
}

export type ApiErrorEnvelope = {
  ok: false
  error: ApiErrorBody
  meta: ApiMeta
}

export type ApiEnvelope<T> = ApiSuccessEnvelope<T> | ApiErrorEnvelope

export type Citation = {
  citation_id: string
  source_id: string
  chunk_id: string
  snippet: string
  title: string
  url: string
  page: number | null
  doc_metadata: Record<string, unknown>
  score: number | null
}

export type ChatRequest = {
  question: string
  stream: boolean
  session_id?: string
}

export type ChatResponseData = {
  session: {
    id: string
    is_new: boolean
  }
  message: {
    id: string
    role: 'assistant'
    answer: string
    citations: Citation[]
    created_at: string
  }
  stream: {
    enabled: boolean
    transport: 'websocket' | null
    channel: string | null
  }
}

export type SessionMessage = {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  citations?: Citation[]
  created_at: string
}

export type SessionMessagesResponseData = {
  session_id: string
  messages: SessionMessage[]
  pagination: {
    limit: number
    next_cursor: string | null
    has_more: boolean
  }
}

export type FeedbackRequest = {
  session_id: string
  message_id: string
  rating: 'up' | 'down'
  reason?: 'incorrect' | 'incomplete' | 'unsafe' | 'other'
  comment?: string
}

export type FeedbackResponseData = {
  feedback: {
    id: string
    session_id: string
    message_id: string
    rating: 'up' | 'down'
    reason: 'incorrect' | 'incomplete' | 'unsafe' | 'other' | null
    comment: string
    created_at: string
  }
}

export type SourceResponseData = {
  source_id: string
  title: string
  url: string
  chunk_id: string
  snippet: string
  page: number | null
  doc_metadata: Record<string, unknown>
}

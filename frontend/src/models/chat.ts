import type { Citation, SessionMessage } from '../types/api'

export type FeedbackReason = 'incorrect' | 'incomplete' | 'unsafe' | 'other'

export type UiMessage = {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  createdAt: string
  citations: Citation[]
}

export function mapHistoryMessage(message: SessionMessage): UiMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    createdAt: message.created_at,
    citations: message.citations || [],
  }
}

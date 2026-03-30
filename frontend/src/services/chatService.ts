import { getSessionMessages, getSourceById, postChat, postFeedback } from '../lib/apiClient'
import { mapHistoryMessage, type FeedbackReason, type UiMessage } from '../models/chat'
import type { Citation, SourceResponseData } from '../types/api'

export async function fetchSessionHistory(sessionId: string): Promise<UiMessage[]> {
  const response = await getSessionMessages(sessionId)
  return response.messages.map(mapHistoryMessage)
}

export async function sendQuestion(question: string, sessionId?: string) {
  return postChat({
    question,
    stream: false,
    session_id: sessionId,
  })
}

export async function sendFeedback(params: {
  sessionId: string
  messageId: string
  rating: 'up' | 'down'
  reason?: FeedbackReason
  comment?: string
}) {
  return postFeedback({
    session_id: params.sessionId,
    message_id: params.messageId,
    rating: params.rating,
    reason: params.reason,
    comment: params.comment,
  })
}

export async function fetchCitationSource(citation: Citation): Promise<SourceResponseData> {
  return getSourceById(citation.source_id, citation.chunk_id)
}

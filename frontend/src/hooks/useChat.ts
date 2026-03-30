import { useEffect, useMemo, useState } from 'react'
import { getSessionMessages, getSourceById, HttpError, postChat, postFeedback } from '../lib/apiClient'
import { mapHistoryMessage, type FeedbackReason, type UiMessage } from '../models/chat'
import type { Citation, SourceResponseData } from '../types/api'

export function useChat() {
  const [question, setQuestion] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<UiMessage[]>([])
  const [pending, setPending] = useState(false)
  const [errorText, setErrorText] = useState<string | null>(null)
  const [retryAfter, setRetryAfter] = useState<number | null>(null)
  const [feedbackReasonByMessage, setFeedbackReasonByMessage] = useState<Record<string, FeedbackReason>>({})
  const [feedbackCommentByMessage, setFeedbackCommentByMessage] = useState<Record<string, string>>({})
  const [submittedFeedback, setSubmittedFeedback] = useState<Record<string, 'up' | 'down'>>({})
  const [selectedSource, setSelectedSource] = useState<SourceResponseData | null>(null)
  const [sourceLoading, setSourceLoading] = useState(false)

  useEffect(() => {
    if (!retryAfter || retryAfter <= 0) {
      return
    }

    const timer = window.setInterval(() => {
      setRetryAfter((seconds) => {
        if (!seconds || seconds <= 1) {
          window.clearInterval(timer)
          return null
        }
        return seconds - 1
      })
    }, 1000)

    return () => window.clearInterval(timer)
  }, [retryAfter])

  async function loadHistory(targetSessionId: string) {
    try {
      const response = await getSessionMessages(targetSessionId)
      setMessages(response.messages.map(mapHistoryMessage))
      setErrorText(null)
    } catch (error) {
      if (error instanceof HttpError) {
        setErrorText(`Could not load session history. ${error.message}`)
      } else {
        setErrorText('Could not load session history due to an unexpected error.')
      }
    }
  }

  async function submitQuestion() {
    const trimmedQuestion = question.trim()
    if (!trimmedQuestion || pending) {
      return
    }

    const tempUserMessage: UiMessage = {
      id: `temp-user-${Date.now()}`,
      role: 'user',
      content: trimmedQuestion,
      createdAt: new Date().toISOString(),
      citations: [],
    }

    setMessages((current) => [...current, tempUserMessage])
    setQuestion('')
    setPending(true)
    setErrorText(null)

    try {
      const response = await postChat({
        question: trimmedQuestion,
        stream: false,
        session_id: sessionId || undefined,
      })

      if (!sessionId) {
        setSessionId(response.session.id)
      }

      setMessages((current) => [
        ...current,
        {
          id: response.message.id,
          role: response.message.role,
          content: response.message.answer,
          createdAt: response.message.created_at,
          citations: response.message.citations || [],
        },
      ])

      if (!sessionId && response.session.id) {
        void loadHistory(response.session.id)
      }
    } catch (error) {
      setMessages((current) => current.filter((message) => message.id !== tempUserMessage.id))
      if (error instanceof HttpError) {
        setErrorText(error.message)
        if (typeof error.retryAfterSeconds === 'number') {
          setRetryAfter(error.retryAfterSeconds)
        }
      } else {
        setErrorText('Could not send message due to an unexpected error.')
      }
    } finally {
      setPending(false)
    }
  }

  async function submitFeedback(messageId: string, rating: 'up' | 'down') {
    if (!sessionId || submittedFeedback[messageId]) {
      return
    }

    try {
      await postFeedback({
        session_id: sessionId,
        message_id: messageId,
        rating,
        reason: feedbackReasonByMessage[messageId],
        comment: feedbackCommentByMessage[messageId] || undefined,
      })

      setSubmittedFeedback((current) => ({ ...current, [messageId]: rating }))
      setErrorText(null)
    } catch (error) {
      if (error instanceof HttpError) {
        setErrorText(`Could not submit feedback. ${error.message}`)
      } else {
        setErrorText('Could not submit feedback due to an unexpected error.')
      }
    }
  }

  async function loadSource(citation: Citation) {
    try {
      setSourceLoading(true)
      const source = await getSourceById(citation.source_id, citation.chunk_id)
      setSelectedSource(source)
      setErrorText(null)
    } catch (error) {
      if (error instanceof HttpError) {
        setErrorText(`Could not load citation source. ${error.message}`)
      } else {
        setErrorText('Could not load citation source due to an unexpected error.')
      }
    } finally {
      setSourceLoading(false)
    }
  }

  const sortedMessages = useMemo(
    () => [...messages].sort((a, b) => Date.parse(a.createdAt) - Date.parse(b.createdAt)),
    [messages],
  )

  return {
    question,
    setQuestion,
    sessionId,
    pending,
    sortedMessages,
    errorText,
    retryAfter,
    feedbackReasonByMessage,
    setFeedbackReasonByMessage,
    feedbackCommentByMessage,
    setFeedbackCommentByMessage,
    submittedFeedback,
    sourceLoading,
    selectedSource,
    submitQuestion,
    submitFeedback,
    loadSource,
  }
}

import type { Dispatch, FormEvent, SetStateAction } from 'react'
import type { FeedbackReason, UiMessage } from '../models/chat'
import type { Citation } from '../types/api'
import { formatDateTime } from '../utils/dateTime'

type ConversationPanelProps = {
  sessionId: string | null
  sortedMessages: UiMessage[]
  sourceLoading: boolean
  feedbackReasonByMessage: Record<string, FeedbackReason>
  setFeedbackReasonByMessage: Dispatch<SetStateAction<Record<string, FeedbackReason>>>
  feedbackCommentByMessage: Record<string, string>
  setFeedbackCommentByMessage: Dispatch<SetStateAction<Record<string, string>>>
  submittedFeedback: Record<string, 'up' | 'down'>
  handleCitationClick: (citation: Citation) => Promise<void>
  handleFeedback: (messageId: string, rating: 'up' | 'down') => Promise<void>
  question: string
  setQuestion: Dispatch<SetStateAction<string>>
  pending: boolean
  handleSubmit: (event: FormEvent<HTMLFormElement>) => Promise<void>
}

export function ConversationPanel({
  sessionId,
  sortedMessages,
  sourceLoading,
  feedbackReasonByMessage,
  setFeedbackReasonByMessage,
  feedbackCommentByMessage,
  setFeedbackCommentByMessage,
  submittedFeedback,
  handleCitationClick,
  handleFeedback,
  question,
  setQuestion,
  pending,
  handleSubmit,
}: ConversationPanelProps) {
  return (
    <section className="panel chat-panel" aria-live="polite">
      <div className="panel-head">
        <h2>Conversation</h2>
        <p>{sessionId ? `Session: ${sessionId}` : 'Session will be created on first message'}</p>
      </div>

      <div className="message-list">
        {sortedMessages.length === 0 && (
          <p className="placeholder">No messages yet. Ask about tuition, schedules, or deadlines.</p>
        )}

        {sortedMessages.map((message) => (
          <article key={message.id} className={`message message-${message.role}`}>
            <div className="message-meta">
              <span>{message.role.toUpperCase()}</span>
              <time dateTime={message.createdAt}>{formatDateTime(message.createdAt)}</time>
            </div>
            <p>{message.content}</p>

            {message.citations.length > 0 && (
              <div className="citations">
                <p className="caption">Citations</p>
                <div className="citation-list">
                  {message.citations.map((citation) => (
                    <button
                      key={citation.citation_id}
                      type="button"
                      className="citation-chip"
                      onClick={() => {
                        void handleCitationClick(citation)
                      }}
                      disabled={sourceLoading}
                    >
                      {citation.title || citation.source_id}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {message.role === 'assistant' && (
              <div className="feedback-box">
                <label>
                  Reason
                  <select
                    value={feedbackReasonByMessage[message.id] || ''}
                    onChange={(event) => {
                      const nextValue = event.target.value
                      setFeedbackReasonByMessage((current) => {
                        if (!nextValue) {
                          const { [message.id]: _removed, ...rest } = current
                          return rest
                        }
                        return {
                          ...current,
                          [message.id]: nextValue as FeedbackReason,
                        }
                      })
                    }}
                  >
                    <option value="">Optional</option>
                    <option value="incorrect">Incorrect</option>
                    <option value="incomplete">Incomplete</option>
                    <option value="unsafe">Unsafe</option>
                    <option value="other">Other</option>
                  </select>
                </label>
                <label>
                  Comment
                  <input
                    value={feedbackCommentByMessage[message.id] || ''}
                    onChange={(event) =>
                      setFeedbackCommentByMessage((current) => ({
                        ...current,
                        [message.id]: event.target.value.slice(0, 1000),
                      }))
                    }
                    placeholder="Optional details"
                  />
                </label>
                <div className="feedback-actions">
                  <button
                    type="button"
                    className="small"
                    onClick={() => {
                      void handleFeedback(message.id, 'up')
                    }}
                    disabled={Boolean(submittedFeedback[message.id])}
                  >
                    Helpful
                  </button>
                  <button
                    type="button"
                    className="small ghost"
                    onClick={() => {
                      void handleFeedback(message.id, 'down')
                    }}
                    disabled={Boolean(submittedFeedback[message.id])}
                  >
                    Needs work
                  </button>
                  {submittedFeedback[message.id] && <span className="feedback-status">Feedback saved</span>}
                </div>
              </div>
            )}
          </article>
        ))}
      </div>

      <form className="composer" onSubmit={(event) => void handleSubmit(event)}>
        <label htmlFor="question-input" className="caption">
          Ask a question
        </label>
        <textarea
          id="question-input"
          rows={3}
          value={question}
          maxLength={4000}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Example: What is the application deadline for transfer students?"
        />
        <div className="composer-row">
          <span>{question.trim().length}/4000</span>
          <button type="submit" disabled={pending || !question.trim()}>
            {pending ? 'Sending...' : 'Send'}
          </button>
        </div>
      </form>
    </section>
  )
}

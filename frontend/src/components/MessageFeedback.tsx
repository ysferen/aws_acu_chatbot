import type { Dispatch, SetStateAction } from 'react'
import type { FeedbackReason } from '../models/chat'

type MessageFeedbackProps = {
  messageId: string
  feedbackReasonByMessage: Record<string, FeedbackReason>
  setFeedbackReasonByMessage: Dispatch<SetStateAction<Record<string, FeedbackReason>>>
  feedbackCommentByMessage: Record<string, string>
  setFeedbackCommentByMessage: Dispatch<SetStateAction<Record<string, string>>>
  submittedFeedback: Record<string, 'up' | 'down'>
  onFeedback: (messageId: string, rating: 'up' | 'down') => Promise<void>
}

export function MessageFeedback({
  messageId,
  feedbackReasonByMessage,
  setFeedbackReasonByMessage,
  feedbackCommentByMessage,
  setFeedbackCommentByMessage,
  submittedFeedback,
  onFeedback,
}: MessageFeedbackProps) {
  return (
    <div className="feedback-box">
      <label>
        Reason
        <select
          value={feedbackReasonByMessage[messageId] || ''}
          onChange={(event) => {
            const nextValue = event.target.value
            setFeedbackReasonByMessage((current) => {
              if (!nextValue) {
                const { [messageId]: _removed, ...rest } = current
                return rest
              }
              return {
                ...current,
                [messageId]: nextValue as FeedbackReason,
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
          value={feedbackCommentByMessage[messageId] || ''}
          onChange={(event) =>
            setFeedbackCommentByMessage((current) => ({
              ...current,
              [messageId]: event.target.value.slice(0, 1000),
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
            void onFeedback(messageId, 'up')
          }}
          disabled={Boolean(submittedFeedback[messageId])}
        >
          Helpful
        </button>
        <button
          type="button"
          className="small ghost"
          onClick={() => {
            void onFeedback(messageId, 'down')
          }}
          disabled={Boolean(submittedFeedback[messageId])}
        >
          Needs work
        </button>
        {submittedFeedback[messageId] && <span className="feedback-status">Feedback saved</span>}
      </div>
    </div>
  )
}

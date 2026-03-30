import type { FormEvent } from 'react'
import type { Citation } from './types/api'
import { type FeedbackReason } from './models/chat'
import { useChat } from './hooks/useChat'
import { formatDateTime } from './utils/dateTime'
import './App.css'

function App() {
  const {
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
  } = useChat()

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await submitQuestion()
  }

  async function handleFeedback(messageId: string, rating: 'up' | 'down') {
    await submitFeedback(messageId, rating)
  }

  async function handleCitationClick(citation: Citation) {
    await loadSource(citation)
  }

  return (
    <main className="page">
      <header className="masthead">
        <p className="eyebrow">AWS ACU Assistant</p>
        <h1>Student Support Chat</h1>
        <p className="subhead">
          Ask a university question, inspect cited source details, and rate answer quality.
        </p>
      </header>

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
                        onClick={() => handleCitationClick(citation)}
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
                      onClick={() => handleFeedback(message.id, 'up')}
                      disabled={Boolean(submittedFeedback[message.id])}
                    >
                      Helpful
                    </button>
                    <button
                      type="button"
                      className="small ghost"
                      onClick={() => handleFeedback(message.id, 'down')}
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

        <form className="composer" onSubmit={handleSubmit}>
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

      <section className="panel source-panel">
        <div className="panel-head">
          <h2>Source Drill-down</h2>
          <p>{sourceLoading ? 'Loading source...' : 'Select a citation from an assistant message'}</p>
        </div>

        {selectedSource ? (
          <div className="source-body">
            <h3>{selectedSource.title || selectedSource.source_id}</h3>
            <p>{selectedSource.snippet}</p>
            <a href={selectedSource.url} target="_blank" rel="noreferrer">
              Open source URL
            </a>
            <dl>
              <dt>Source ID</dt>
              <dd>{selectedSource.source_id}</dd>
              <dt>Chunk ID</dt>
              <dd>{selectedSource.chunk_id}</dd>
              <dt>Page</dt>
              <dd>{selectedSource.page ?? 'N/A'}</dd>
            </dl>
            <pre>{JSON.stringify(selectedSource.doc_metadata, null, 2)}</pre>
          </div>
        ) : (
          <p className="placeholder">No source selected yet.</p>
        )}
      </section>

      {(errorText || retryAfter) && (
        <aside className="status-bar" role="status">
          {errorText && <span>{errorText}</span>}
          {retryAfter && <span>Retry after {retryAfter}s</span>}
        </aside>
      )}
    </main>
  )
}

export default App

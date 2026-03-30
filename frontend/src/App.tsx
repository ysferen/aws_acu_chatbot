import type { FormEvent } from 'react'
import type { Citation } from './types/api'
import { useChat } from './hooks/useChat'
import { ConversationPanel } from './components/ConversationPanel'
import { Masthead } from './components/Masthead'
import { SourcePanel } from './components/SourcePanel'
import { StatusBar } from './components/StatusBar'
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
      <Masthead />

      <ConversationPanel
        sessionId={sessionId}
        sortedMessages={sortedMessages}
        sourceLoading={sourceLoading}
        feedbackReasonByMessage={feedbackReasonByMessage}
        setFeedbackReasonByMessage={setFeedbackReasonByMessage}
        feedbackCommentByMessage={feedbackCommentByMessage}
        setFeedbackCommentByMessage={setFeedbackCommentByMessage}
        submittedFeedback={submittedFeedback}
        handleCitationClick={handleCitationClick}
        handleFeedback={handleFeedback}
        question={question}
        setQuestion={setQuestion}
        pending={pending}
        handleSubmit={handleSubmit}
      />

      <SourcePanel sourceLoading={sourceLoading} selectedSource={selectedSource} />

      <StatusBar errorText={errorText} retryAfter={retryAfter} />
    </main>
  )
}

export default App

import type { Citation } from '../types/api'

type MessageCitationsProps = {
  citations: Citation[]
  sourceLoading: boolean
  onCitationClick: (citation: Citation) => Promise<void>
}

export function MessageCitations({ citations, sourceLoading, onCitationClick }: MessageCitationsProps) {
  if (citations.length === 0) {
    return null
  }

  return (
    <div className="citations">
      <p className="caption">Citations</p>
      <div className="citation-list">
        {citations.map((citation) => (
          <button
            key={citation.citation_id}
            type="button"
            className="citation-chip"
            onClick={() => {
              void onCitationClick(citation)
            }}
            disabled={sourceLoading}
          >
            {citation.title || citation.source_id}
          </button>
        ))}
      </div>
    </div>
  )
}

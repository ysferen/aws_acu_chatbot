import type { SourceResponseData } from '../types/api'

type SourcePanelProps = {
  sourceLoading: boolean
  selectedSource: SourceResponseData | null
}

export function SourcePanel({ sourceLoading, selectedSource }: SourcePanelProps) {
  return (
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
  )
}

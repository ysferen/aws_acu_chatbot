type StatusBarProps = {
  errorText: string | null
  retryAfter: number | null
}

export function StatusBar({ errorText, retryAfter }: StatusBarProps) {
  if (!errorText && !retryAfter) {
    return null
  }

  return (
    <aside className="status-bar" role="status">
      {errorText && <span>{errorText}</span>}
      {retryAfter && <span>Retry after {retryAfter}s</span>}
    </aside>
  )
}

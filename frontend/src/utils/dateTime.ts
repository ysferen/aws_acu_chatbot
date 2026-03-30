export function formatDateTime(isoValue: string): string {
  return new Date(isoValue).toLocaleString()
}

import dayjs from 'dayjs'

export function formatDuration(seconds?: number | null) {
  const value = Math.max(0, Math.floor(seconds ?? 0))
  const hours = Math.floor(value / 3600)
  const minutes = Math.floor((value % 3600) / 60)
  if (hours) return `${hours} 小时 ${minutes} 分钟`
  return `${minutes} 分钟`
}

export function compactDuration(seconds?: number | null) {
  return `${((seconds ?? 0) / 3600).toFixed(1)}h`
}

export function formatDateTime(value?: string | null) {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '—'
}

export function formatDate(value?: string | null) {
  return value ? dayjs(value).format('YYYY-MM-DD') : '—'
}

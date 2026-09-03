import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

const desktopApiBase = typeof window !== 'undefined' ? window.labtime?.apiBase : undefined
export const http = axios.create({ baseURL: desktopApiBase || '/api/v1', withCredentials: true, timeout: 20_000 })
let accessToken: string | null = null
let refreshPromise: Promise<string | null> | null = null

export function setAccessToken(token: string | null) { accessToken = token }

http.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  return config
})

interface RetryConfig extends InternalAxiosRequestConfig { _retried?: boolean }

http.interceptors.response.use(undefined, async (error: AxiosError) => {
  const config = error.config as RetryConfig | undefined
  if (error.response?.status !== 401 || !config || config._retried || config.url?.includes('/auth/')) {
    return Promise.reject(error)
  }
  config._retried = true
  refreshPromise ??= axios.post('/api/v1/auth/refresh', {}, { withCredentials: true })
    .then((response) => {
      const token = response.data.access_token as string
      setAccessToken(token)
      return token
    })
    .catch(() => null)
    .finally(() => { refreshPromise = null })
  const token = await refreshPromise
  if (!token) return Promise.reject(error)
  config.headers.Authorization = `Bearer ${token}`
  return http(config)
})

export function errorMessage(error: unknown, fallback = '操作失败') {
  if (axios.isAxiosError(error)) {
    if (!error.response) return fallback
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (detail?.message) {
      const errors = Array.isArray(detail.errors) ? detail.errors.filter((item: unknown) => typeof item === 'string') : []
      return errors.length ? `${detail.message}：${errors.join('；')}` : detail.message as string
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const fieldLabels: Record<string, string> = {
        username: '账号',
        real_name: '真实姓名',
        identifier: '学号 / 工号',
        password: '密码',
        new_password: '新密码',
        current_password: '当前密码',
        role: '角色',
      }
      const item = detail[0] as {
        type?: string
        loc?: Array<string | number>
        msg?: string
        ctx?: Record<string, unknown>
      }
      const field = String(item.loc?.at(-1) ?? '')
      const label = fieldLabels[field] ?? field ?? '请求参数'
      if (item.type === 'missing') return `${label}不能为空`
      if (item.type === 'string_too_short') return `${label}至少需要 ${item.ctx?.min_length ?? ''} 个字符`
      if (item.type === 'string_too_long') return `${label}不能超过 ${item.ctx?.max_length ?? ''} 个字符`
      if (item.type === 'string_pattern_mismatch') return `${label}格式不正确`
      return item.msg ? `${label}：${item.msg}` : '提交内容不符合要求，请检查后重试'
    }
    if ((error.response?.status ?? 0) >= 500) return '服务器处理失败，请稍后重试或联系管理员'
  }
  return error instanceof Error ? error.message : fallback
}

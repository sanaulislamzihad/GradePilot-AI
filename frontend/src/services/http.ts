/**
 * Axios instance with access-token handling.
 *
 * The access token lives only in memory. The refresh token is an httpOnly
 * cookie the browser sends to /api/auth/* automatically; JavaScript never sees it.
 * On a 401, one refresh is attempted (shared across concurrent requests) and the
 * original request is retried once.
 */
import axios, { AxiosError, type AxiosRequestConfig } from 'axios'
import type { ApiErrorBody, TokenResponse } from '@/types/api'

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api',
  withCredentials: true,
  timeout: 30_000,
})

let accessToken: string | null = null
let refreshInFlight: Promise<TokenResponse> | null = null
let onSessionChange: ((session: TokenResponse | null) => void) | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
}

/** The auth context registers here so token refreshes and expiry update React state. */
export function bindSessionListener(listener: typeof onSessionChange) {
  onSessionChange = listener
}

const postRefresh = () =>
  http.post<TokenResponse>('/auth/refresh', undefined, { skipAuthRetry: true } as AxiosRequestConfig)

export function refreshSession(): Promise<TokenResponse> {
  if (!refreshInFlight) {
    refreshInFlight = postRefresh()
      .catch(async (error: AxiosError) => {
        // Another tab may have rotated the shared cookie a moment ago; the
        // browser now holds the newer token, so one retry is enough.
        if (error.response?.status !== 409) throw error
        await new Promise((resolve) => setTimeout(resolve, 400))
        return postRefresh()
      })
      .then(({ data }) => {
        setAccessToken(data.access_token)
        onSessionChange?.(data)
        return data
      })
      .finally(() => {
        refreshInFlight = null
      })
  }
  return refreshInFlight
}

http.interceptors.request.use((config) => {
  if (accessToken) config.headers.set('Authorization', `Bearer ${accessToken}`)
  return config
})

type RetriableConfig = AxiosRequestConfig & { _retried?: boolean; skipAuthRetry?: boolean }

http.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined
    const isAuthEndpoint = config?.url?.startsWith('/auth/')
    if (error.response?.status === 401 && config && !config._retried && !config.skipAuthRetry && !isAuthEndpoint) {
      config._retried = true
      try {
        await refreshSession()
        return http(config)
      } catch {
        setAccessToken(null)
        onSessionChange?.(null)
      }
    }
    return Promise.reject(error)
  },
)

/** Turn any request failure into a message a person can act on. */
export function errorMessage(error: unknown, fallback = 'Something went wrong. Please try again.'): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    if (!error.response) return 'Cannot reach the server. Check your connection and that the API is running.'
    const detail = error.response.data?.detail
    if (typeof detail === 'string' && detail) return detail
    if (error.response.status >= 500) return 'The server ran into a problem. Please try again shortly.'
  }
  return fallback
}

/** Field-level validation messages from a 422 response, keyed by field name. */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!axios.isAxiosError<ApiErrorBody>(error) || error.response?.status !== 422) return {}
  const result: Record<string, string> = {}
  for (const item of error.response.data?.fields ?? []) {
    if (item.field && !result[item.field]) result[item.field] = item.message
  }
  return result
}

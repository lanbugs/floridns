import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios'

const BASE_URL = '/api/v1'

// In-memory token store — avoids circular dep with auth store.
// auth store calls setCurrentToken() whenever the access token changes.
let _currentToken: string | null = null

export function setCurrentToken(token: string | null): void {
  _currentToken = token
}

function createClient(): AxiosInstance {
  const client = axios.create({ baseURL: BASE_URL, withCredentials: true })

  client.interceptors.request.use((config) => {
    if (_currentToken) {
      config.headers.Authorization = `Bearer ${_currentToken}`
    }
    return config
  })

  client.interceptors.response.use(
    (r) => r,
    async (error) => {
      const original = error.config
      if (error.response?.status === 401 && !original._retry) {
        original._retry = true
        try {
          // Refresh token is in httpOnly cookie — no body needed
          const { data } = await axios.post(
            `${BASE_URL}/auth/refresh`,
            {},
            { withCredentials: true },
          )
          const newToken: string = data.access_token
          _currentToken = newToken
          // Sync to localStorage so auth store picks it up on next page load
          localStorage.setItem('fdns_access_token', newToken)
          original.headers.Authorization = `Bearer ${newToken}`
          return client(original)
        } catch {
          _currentToken = null
          localStorage.removeItem('fdns_access_token')
          window.location.href = '/login'
        }
      }
      return Promise.reject(error)
    },
  )

  return client
}

const _client = createClient()

export const api = {
  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const { data } = await _client.get<T>(url, config)
    return data
  },
  async post<T>(url: string, body?: unknown, config?: AxiosRequestConfig): Promise<T> {
    const { data } = await _client.post<T>(url, body, config)
    return data
  },
  async put<T>(url: string, body?: unknown): Promise<T> {
    const { data } = await _client.put<T>(url, body)
    return data
  },
  async patch<T>(url: string, body?: unknown): Promise<T> {
    const { data } = await _client.patch<T>(url, body)
    return data
  },
  async delete(url: string): Promise<void> {
    await _client.delete(url)
  },
}

export function useApiError(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return String(error)
  }

  // No response object means the request never reached the server
  if (!error.response) {
    if (error.code === 'ECONNABORTED' || error.message.toLowerCase().includes('timeout')) {
      return 'Request timed out. The server took too long to respond.'
    }
    return 'Cannot reach the server. Check your network connection.'
  }

  const { status, data } = error.response
  const detail = data?.detail

  // FastAPI validation errors return detail as an array of {loc, msg, type}
  if (Array.isArray(detail)) {
    const messages = detail.map((d: { loc?: string[]; msg?: string }) => {
      const field = d.loc?.slice(-1)[0] ?? 'field'
      return `${field}: ${d.msg ?? 'invalid'}`
    })
    return `Validation failed — ${messages.join('; ')}`
  }

  // Backend returned a readable detail string → use it directly
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }

  // Generic fallback by HTTP status code
  switch (status) {
    case 400: return 'Bad request. Please check your input.'
    case 401: return 'Your session has expired. Please log in again.'
    case 403: return 'You do not have permission to perform this action.'
    case 404: return 'The requested resource was not found.'
    case 409: return 'Conflict — this resource already exists.'
    case 422: return 'Validation failed. Please check your input and try again.'
    case 429: return 'Too many requests. Please wait a moment before trying again.'
    case 500: return 'Internal server error. Please contact your administrator or check the server logs.'
    case 502: return 'PowerDNS is unreachable. Please check the PowerDNS connection in Settings.'
    case 503: return 'Service temporarily unavailable. Please try again in a moment.'
    case 504: return 'Gateway timeout — PowerDNS did not respond in time.'
    default:  return `Unexpected error (HTTP ${status}). Please try again.`
  }
}

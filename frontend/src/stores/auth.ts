import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, LoginResponse } from '@/types'
import { api } from '@/composables/useApi'
import { setCurrentToken } from '@/composables/useApi'

const ACCESS_TOKEN_KEY = 'fdns_access_token'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  // Access token is kept in memory and localStorage (30-min lifetime).
  // Refresh token is stored in an httpOnly cookie — not accessible to JS.
  const accessToken = ref<string | null>(localStorage.getItem(ACCESS_TOKEN_KEY))
  const totpToken = ref<string | null>(null)

  if (accessToken.value) {
    setCurrentToken(accessToken.value)
  }

  const isAuthenticated = computed(() => !!accessToken.value && !!user.value)
  const isAdmin = computed(() =>
    ['superadmin', 'admin'].includes(user.value?.role ?? ''),
  )
  const isSuperadmin = computed(() => user.value?.role === 'superadmin')

  function _storeAccessToken(token: string) {
    accessToken.value = token
    localStorage.setItem(ACCESS_TOKEN_KEY, token)
    setCurrentToken(token)
  }

  function clearTokens() {
    accessToken.value = null
    user.value = null
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    setCurrentToken(null)
  }

  // Returns 'done' when fully logged in, 'totp' when TOTP step is needed.
  async function login(username: string, password: string): Promise<'done' | 'totp'> {
    const resp = await api.post<LoginResponse>('/auth/login', { username, password })
    if (resp.token_type === 'totp_required') {
      totpToken.value = resp.totp_token
      return 'totp'
    }
    _storeAccessToken(resp.access_token!)
    await fetchMe()
    return 'done'
  }

  async function verifyTotp(code: string): Promise<void> {
    if (!totpToken.value) throw new Error('No TOTP session active')
    const resp = await api.post<LoginResponse>('/auth/totp', {
      totp_token: totpToken.value,
      code,
    })
    totpToken.value = null
    _storeAccessToken(resp.access_token!)
    await fetchMe()
  }

  async function fetchMe(): Promise<void> {
    try {
      user.value = await api.get<User>('/users/me')
    } catch {
      clearTokens()
    }
  }

  async function refreshAccessToken(): Promise<boolean> {
    try {
      // No body needed — refresh token is in the httpOnly cookie
      const tokens = await api.post<{ access_token: string }>('/auth/refresh', undefined, {
        withCredentials: true,
      })
      _storeAccessToken(tokens.access_token)
      return true
    } catch {
      clearTokens()
      return false
    }
  }

  async function logout(): Promise<void> {
    try {
      // Cookie is sent automatically; backend revokes it and increments token_version
      await api.post('/auth/logout', undefined, { withCredentials: true })
    } catch {
      // best-effort server-side revocation
    }
    clearTokens()
  }

  async function handleOidcResponse(resp: LoginResponse): Promise<'done' | 'totp'> {
    if (resp.token_type === 'totp_required') {
      totpToken.value = resp.totp_token ?? null
      return 'totp'
    }
    _storeAccessToken(resp.access_token!)
    await fetchMe()
    return 'done'
  }

  async function loginWithPasskey(resp: LoginResponse): Promise<void> {
    _storeAccessToken(resp.access_token!)
    await fetchMe()
  }

  return {
    user,
    accessToken,
    totpToken,
    isAuthenticated,
    isAdmin,
    isSuperadmin,
    login,
    verifyTotp,
    logout,
    fetchMe,
    refreshAccessToken,
    handleOidcResponse,
    loginWithPasskey,
  }
})

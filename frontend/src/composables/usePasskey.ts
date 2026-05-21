import { startAuthentication, startRegistration } from '@simplewebauthn/browser'
import { api } from '@/composables/useApi'
import type { LoginResponse } from '@/types'

export function usePasskey() {
  async function registerPasskey(name: string): Promise<void> {
    const { session_id, options } = await api.get<{ session_id: string; options: object }>(
      '/auth/passkey/register/begin',
    )
    const credential = await startRegistration({ optionsJSON: options as never })
    await api.post('/auth/passkey/register/complete', {
      session_id,
      credential,
      name: name.trim() || null,
    })
  }

  async function beginPasskeyLogin(): Promise<LoginResponse> {
    const { session_id, options } = await api.get<{ session_id: string; options: object }>(
      '/auth/passkey/login/begin',
    )
    const credential = await startAuthentication({ optionsJSON: options as never })
    return api.post<LoginResponse>('/auth/passkey/login/complete', { session_id, credential })
  }

  return { registerPasskey, beginPasskeyLogin }
}

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/composables/useApi'

export interface SlaveServer {
  name: string
  url: string
  api_key: string
  ssl_verify: boolean
}

export interface PdnsPrimary {
  url: string
  api_key: string
  ssl_verify: boolean
}

export interface LdapGroupMapping {
  group_dn: string
  role: string
}

export interface LdapConfig {
  enabled: boolean
  url: string
  bind_dn: string
  bind_password: string
  base_dn: string
  user_attr: string
  email_attr: string
  tls: 'none' | 'starttls' | 'ldaps'
  group_attr: string
  group_mapping: LdapGroupMapping[]
}

export interface OidcRoleMapping {
  claim_value: string
  role: string
}

export interface OidcConfig {
  enabled: boolean
  issuer_url: string
  client_id: string
  client_secret: string
  redirect_uri: string
  scopes: string
  role_claim: string
  role_mapping: OidcRoleMapping[]
}

export interface AppSettings {
  allowed_record_types_operator?: string[]
  allowed_record_types_viewer?: string[]
  slave_servers?: SlaveServer[]
  pdns_primary?: PdnsPrimary
  zone_history_enabled?: boolean
  require_totp?: boolean
  ldap_config?: LdapConfig
  oidc_config?: OidcConfig
  dyndns_enabled?: boolean
}

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<AppSettings>({})
  const loaded = ref(false)
  const loading = ref(false)
  const dyndnsEnabled = ref(true)

  async function fetchSettings(): Promise<void> {
    if (loaded.value) return
    loading.value = true
    try {
      const raw = await api.get<Record<string, unknown>>('/settings')
      settings.value = raw as AppSettings
      loaded.value = true
    } catch {
      // Non-admin users get 403 — ignore silently
    } finally {
      loading.value = false
    }
  }

  async function fetchPublicSettings(): Promise<void> {
    try {
      const raw = await api.get<{ dyndns_enabled: boolean }>('/settings/public')
      dyndnsEnabled.value = raw.dyndns_enabled
    } catch {
      dyndnsEnabled.value = true
    }
  }

  async function updateSetting(key: string, value: unknown): Promise<void> {
    await api.put(`/settings/${key}`, { value })
    const raw = await api.get<Record<string, unknown>>('/settings')
    settings.value = raw as AppSettings
  }

  function getAllowedRecordTypes(role: string): string[] | null {
    if (role === 'operator') return settings.value.allowed_record_types_operator ?? null
    if (role === 'viewer') return settings.value.allowed_record_types_viewer ?? null
    return null
  }

  return {
    settings,
    loaded,
    loading,
    dyndnsEnabled,
    fetchSettings,
    fetchPublicSettings,
    updateSetting,
    getAllowedRecordTypes,
  }
})

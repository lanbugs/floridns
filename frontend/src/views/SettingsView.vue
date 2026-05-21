<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { IconPlus, IconTrash } from '@tabler/icons-vue'
import { useToast } from '@/composables/useToast'
import { useApiError } from '@/composables/useApi'
import { useSettingsStore } from '@/stores/settings'
import { useAuthStore } from '@/stores/auth'
import type { SlaveServer, LdapConfig, OidcConfig } from '@/stores/settings'

const auth = useAuthStore()

const historyEnabled = ref(false)
const savingHistory = ref(false)
const requireTotp = ref(false)
const savingTotp = ref(false)
const dyndnsEnabled = ref(true)
const savingDyndns = ref(false)

const ldapConfig = ref<LdapConfig>({
  enabled: false, url: '', bind_dn: '', bind_password: '',
  base_dn: '', user_attr: 'uid', email_attr: 'mail', tls: 'none',
  group_attr: 'memberOf', group_mapping: [],
})
const savingLdap = ref(false)

const oidcConfig = ref<OidcConfig>({
  enabled: false, issuer_url: '', client_id: '', client_secret: '',
  redirect_uri: typeof window !== 'undefined' ? window.location.origin + '/auth/callback' : '',
  scopes: 'openid email profile',
  role_claim: '', role_mapping: [],
})
const savingOidc = ref(false)

const FLORIDNS_ROLES = ['viewer', 'operator', 'admin', 'superadmin']

function addLdapMapping() {
  ldapConfig.value.group_mapping.push({ group_dn: '', role: 'viewer' })
}
function removeLdapMapping(i: number) {
  ldapConfig.value.group_mapping.splice(i, 1)
}
function addOidcMapping() {
  oidcConfig.value.role_mapping.push({ claim_value: '', role: 'viewer' })
}
function removeOidcMapping(i: number) {
  oidcConfig.value.role_mapping.splice(i, 1)
}

const toast = useToast()
const settingsStore = useSettingsStore()

const saving = ref(false)

const ALL_RECORD_TYPES = [
  'A', 'AAAA', 'CNAME', 'MX', 'NS', 'TXT', 'SRV', 'CAA',
  'TLSA', 'PTR', 'SOA', 'NAPTR', 'SSHFP', 'DNSKEY', 'DS', 'ALIAS',
]

const operatorTypes = ref<Set<string>>(new Set(ALL_RECORD_TYPES))
const primaryServer = ref({ url: '', api_key: '', ssl_verify: true })
const savingPrimary = ref(false)
const slaveServers = ref<SlaveServer[]>([])
const newSlave = ref<SlaveServer>({ name: '', url: '', api_key: '', ssl_verify: true })
const addingServer = ref(false)

onMounted(async () => {
  await settingsStore.fetchSettings()
  const allowed = settingsStore.settings.allowed_record_types_operator
  if (allowed) operatorTypes.value = new Set(allowed)
  const primary = settingsStore.settings.pdns_primary
  if (primary) primaryServer.value = { url: primary.url, api_key: primary.api_key, ssl_verify: primary.ssl_verify ?? true }
  slaveServers.value = (settingsStore.settings.slave_servers ?? []).map((s) => ({ ...s, ssl_verify: s.ssl_verify ?? true }))
  historyEnabled.value = settingsStore.settings.zone_history_enabled ?? false
  requireTotp.value = settingsStore.settings.require_totp ?? false
  dyndnsEnabled.value = settingsStore.settings.dyndns_enabled ?? true
  if (settingsStore.settings.ldap_config) {
    ldapConfig.value = { ...ldapConfig.value, ...settingsStore.settings.ldap_config }
  }
  if (settingsStore.settings.oidc_config) {
    oidcConfig.value = { ...oidcConfig.value, ...settingsStore.settings.oidc_config }
  }
})

async function saveRequireTotp(): Promise<void> {
  savingTotp.value = true
  try {
    await settingsStore.updateSetting('require_totp', requireTotp.value)
    toast.success('TOTP requirement setting saved')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    savingTotp.value = false
  }
}

async function saveHistoryEnabled(): Promise<void> {
  savingHistory.value = true
  try {
    await settingsStore.updateSetting('zone_history_enabled', historyEnabled.value)
    toast.success('Zone history setting saved')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    savingHistory.value = false
  }
}

async function saveDyndnsEnabled(): Promise<void> {
  savingDyndns.value = true
  try {
    await settingsStore.updateSetting('dyndns_enabled', dyndnsEnabled.value)
    await settingsStore.fetchPublicSettings()
    toast.success('Dynamic DNS setting saved')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    savingDyndns.value = false
  }
}

function toggleType(type: string): void {
  if (operatorTypes.value.has(type)) {
    operatorTypes.value.delete(type)
  } else {
    operatorTypes.value.add(type)
  }
  operatorTypes.value = new Set(operatorTypes.value)
}

async function saveOperatorTypes(): Promise<void> {
  saving.value = true
  try {
    await settingsStore.updateSetting('allowed_record_types_operator', [...operatorTypes.value])
    toast.success('Operator record types saved')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    saving.value = false
  }
}

async function savePrimaryServer(): Promise<void> {
  if (!primaryServer.value.url) return
  savingPrimary.value = true
  try {
    await settingsStore.updateSetting('pdns_primary', primaryServer.value)
    toast.success('Primary server saved')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    savingPrimary.value = false
  }
}

async function saveSlaveServers(): Promise<void> {
  saving.value = true
  try {
    await settingsStore.updateSetting('slave_servers', slaveServers.value)
    toast.success('Slave servers saved')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    saving.value = false
  }
}

function addServer(): void {
  if (!newSlave.value.name || !newSlave.value.url) return
  slaveServers.value.push({ ...newSlave.value })
  newSlave.value = { name: '', url: '', api_key: '', ssl_verify: true }
  addingServer.value = false
}

function removeServer(index: number): void {
  slaveServers.value.splice(index, 1)
}

const operatorCount = computed(() => operatorTypes.value.size)

async function saveLdap(): Promise<void> {
  savingLdap.value = true
  try {
    await settingsStore.updateSetting('ldap_config', ldapConfig.value)
    toast.success('LDAP settings saved')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    savingLdap.value = false
  }
}

async function saveOidc(): Promise<void> {
  savingOidc.value = true
  try {
    await settingsStore.updateSetting('oidc_config', oidcConfig.value)
    toast.success('OIDC settings saved')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    savingOidc.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header d-print-none">
      <div class="container-xl">
        <div class="row g-2 align-items-center">
          <div class="col">
            <div class="page-pretitle">Administration</div>
            <h2 class="page-title">Settings</h2>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">
        <div v-if="!auth.isSuperadmin" class="alert alert-info mb-3">
          Settings are read-only for your role. Only superadmins can change global settings.
        </div>

        <!-- Primary PowerDNS server -->
        <div class="card mb-3">
          <div class="card-header">
            <h3 class="card-title">Primary PowerDNS server</h3>
            <div v-if="auth.isSuperadmin" class="card-options">
              <button
                class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1"
                :disabled="savingPrimary"
                @click="savePrimaryServer"
              >
                <span v-if="savingPrimary" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                Save
              </button>
            </div>
          </div>
          <div class="card-body">
            <p class="text-muted mb-3">
              Override the URL and API key set via environment variables. Leave empty to use the defaults.
            </p>
            <div class="row g-3">
              <div class="col-sm-6">
                <label class="form-label">API URL</label>
                <input v-model="primaryServer.url" placeholder="http://pdns:8081" class="form-control" />
              </div>
              <div class="col-sm-6">
                <label class="form-label">API Key</label>
                <input v-model="primaryServer.api_key" type="password" placeholder="••••••••" class="form-control" />
              </div>
              <div class="col-12">
                <label class="form-check">
                  <input v-model="primaryServer.ssl_verify" type="checkbox" class="form-check-input" />
                  <span class="form-check-label">Verify SSL certificate</span>
                </label>
                <div class="form-text">Disable only when using self-signed certificates.</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Allowed record types for operator -->
        <div class="card mb-3">
          <div class="card-header">
            <h3 class="card-title">Allowed record types — Operator role</h3>
            <div v-if="auth.isSuperadmin" class="card-options">
              <button
                class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1"
                :disabled="saving"
                @click="saveOperatorTypes"
              >
                <span v-if="saving" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                Save
              </button>
            </div>
          </div>
          <div class="card-body">
            <p class="text-muted mb-3">
              Choose which record types operators may create or edit.
              {{ operatorCount }} of {{ ALL_RECORD_TYPES.length }} types selected.
            </p>
            <div class="d-flex flex-wrap gap-2">
              <button
                v-for="type in ALL_RECORD_TYPES"
                :key="type"
                type="button"
                class="btn btn-sm"
                :class="operatorTypes.has(type) ? 'btn-primary' : 'btn-outline-secondary'"
                @click="toggleType(type)"
              >
                {{ type }}
              </button>
            </div>
          </div>
        </div>

        <!-- Two-factor authentication -->
        <div class="card mb-3">
          <div class="card-header">
            <h3 class="card-title">Two-factor authentication (TOTP)</h3>
            <div v-if="auth.isSuperadmin" class="card-options">
              <button
                class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1"
                :disabled="savingTotp"
                @click="saveRequireTotp"
              >
                <span v-if="savingTotp" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                Save
              </button>
            </div>
          </div>
          <div class="card-body">
            <p class="text-muted mb-3">
              When enabled, all users must set up and use TOTP before they can access the application.
              Users who have not yet configured 2FA will be redirected to the security page on login.
            </p>
            <label class="form-check form-switch">
              <input v-model="requireTotp" type="checkbox" class="form-check-input" role="switch" />
              <span class="form-check-label">Require two-factor authentication for all users</span>
            </label>
          </div>
        </div>

        <!-- Zone history -->
        <div class="card mb-3">
          <div class="card-header">
            <h3 class="card-title">Zone history</h3>
            <div v-if="auth.isSuperadmin" class="card-options">
              <button
                class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1"
                :disabled="savingHistory"
                @click="saveHistoryEnabled"
              >
                <span v-if="savingHistory" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                Save
              </button>
            </div>
          </div>
          <div class="card-body">
            <p class="text-muted mb-3">
              When enabled, a full snapshot of all DNS records is captured before and after every change.
              You can then review the history and restore any zone to a previous state.
            </p>
            <label class="form-check form-switch">
              <input v-model="historyEnabled" type="checkbox" class="form-check-input" role="switch" />
              <span class="form-check-label">Enable zone history &amp; rollback</span>
            </label>
          </div>
        </div>

        <!-- Dynamic DNS -->
        <div class="card mb-3">
          <div class="card-header">
            <h3 class="card-title">Dynamic DNS</h3>
            <div v-if="auth.isSuperadmin" class="card-options">
              <button
                class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1"
                :disabled="savingDyndns"
                @click="saveDyndnsEnabled"
              >
                <span v-if="savingDyndns" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                Save
              </button>
            </div>
          </div>
          <div class="card-body">
            <p class="text-muted mb-3">
              When disabled, all DynDNS CRUD endpoints and <code>/nic/update</code> are blocked.
              Existing host registrations are preserved and can be re-activated by enabling the feature again.
            </p>
            <label class="form-check form-switch">
              <input v-model="dyndnsEnabled" type="checkbox" class="form-check-input" role="switch" />
              <span class="form-check-label">Enable Dynamic DNS</span>
            </label>
          </div>
        </div>

        <!-- LDAP -->
        <div class="card mb-3">
          <div class="card-header">
            <h3 class="card-title">LDAP / Active Directory</h3>
            <div v-if="auth.isSuperadmin" class="card-options">
              <button
                class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1"
                :disabled="savingLdap"
                @click="saveLdap"
              >
                <span v-if="savingLdap" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                Save
              </button>
            </div>
          </div>
          <div class="card-body">
            <p class="text-muted mb-3">
              Allow users to sign in with their LDAP or Active Directory credentials.
              Users are provisioned automatically on first login with the <strong>viewer</strong> role.
            </p>
            <label class="form-check form-switch mb-3">
              <input v-model="ldapConfig.enabled" type="checkbox" class="form-check-input" role="switch" />
              <span class="form-check-label">Enable LDAP authentication</span>
            </label>
            <div class="row g-3">
              <div class="col-sm-6">
                <label class="form-label">Server URL</label>
                <input v-model="ldapConfig.url" class="form-control font-monospace" placeholder="ldap://ldap.example.com" />
              </div>
              <div class="col-sm-6">
                <label class="form-label">TLS mode</label>
                <select v-model="ldapConfig.tls" class="form-select">
                  <option value="none">None (plain LDAP)</option>
                  <option value="starttls">STARTTLS</option>
                  <option value="ldaps">LDAPS (ldaps://)</option>
                </select>
              </div>
              <div class="col-sm-6">
                <label class="form-label">Service account DN (Bind DN)</label>
                <input v-model="ldapConfig.bind_dn" class="form-control font-monospace" placeholder="cn=reader,dc=example,dc=com" />
              </div>
              <div class="col-sm-6">
                <label class="form-label">Service account password</label>
                <input v-model="ldapConfig.bind_password" type="password" class="form-control" placeholder="••••••••" />
              </div>
              <div class="col-sm-12">
                <label class="form-label">Base DN</label>
                <input v-model="ldapConfig.base_dn" class="form-control font-monospace" placeholder="ou=users,dc=example,dc=com" />
              </div>
              <div class="col-sm-6">
                <label class="form-label">Username attribute</label>
                <input v-model="ldapConfig.user_attr" class="form-control font-monospace" placeholder="uid" />
                <div class="form-text">Use <code>sAMAccountName</code> for Active Directory.</div>
              </div>
              <div class="col-sm-6">
                <label class="form-label">Email attribute</label>
                <input v-model="ldapConfig.email_attr" class="form-control font-monospace" placeholder="mail" />
                <div class="form-text">Use <code>userPrincipalName</code> for Active Directory.</div>
              </div>
              <div class="col-12">
                <div class="d-flex align-items-center justify-content-between mb-2">
                  <div>
                    <label class="form-label mb-0">Group → Role mapping</label>
                    <div class="form-text mt-0">
                      Groups are read from the <input v-model="ldapConfig.group_attr" class="form-control form-control-sm d-inline-block font-monospace" style="width:9rem;" placeholder="memberOf" /> attribute on the user entry.
                      If no mapping is configured, role is set to <strong>viewer</strong> on first login and managed manually thereafter.
                    </div>
                  </div>
                  <button type="button" class="btn btn-sm btn-outline-secondary d-inline-flex align-items-center gap-1 ms-3 flex-shrink-0" @click="addLdapMapping">
                    <IconPlus :size="14" /> Add
                  </button>
                </div>
                <table v-if="ldapConfig.group_mapping.length" class="table table-sm table-vcenter mb-0">
                  <thead>
                    <tr>
                      <th>Group DN</th>
                      <th style="width:9rem;">FloriDNS role</th>
                      <th class="w-1" />
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(m, i) in ldapConfig.group_mapping" :key="i">
                      <td><input v-model="m.group_dn" class="form-control form-control-sm font-monospace" placeholder="CN=DNS-Admins,DC=example,DC=com" /></td>
                      <td>
                        <select v-model="m.role" class="form-select form-select-sm">
                          <option v-for="r in FLORIDNS_ROLES" :key="r" :value="r">{{ r }}</option>
                        </select>
                      </td>
                      <td><button type="button" class="btn btn-ghost-secondary btn-icon btn-sm text-danger" @click="removeLdapMapping(i)"><IconTrash :size="16" /></button></td>
                    </tr>
                  </tbody>
                </table>
                <div v-else class="text-muted small">No group mappings — role is managed manually in FloriDNS.</div>
              </div>
            </div>
          </div>
        </div>

        <!-- OIDC -->
        <div class="card mb-3">
          <div class="card-header">
            <h3 class="card-title">SSO / OpenID Connect</h3>
            <div v-if="auth.isSuperadmin" class="card-options">
              <button
                class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1"
                :disabled="savingOidc"
                @click="saveOidc"
              >
                <span v-if="savingOidc" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                Save
              </button>
            </div>
          </div>
          <div class="card-body">
            <p class="text-muted mb-3">
              Enable single sign-on via any OpenID Connect provider (Keycloak, Auth0, Azure AD, Google Workspace, …).
              Users are provisioned automatically on first login with the <strong>viewer</strong> role.
              The redirect URI must be registered in your identity provider.
            </p>
            <label class="form-check form-switch mb-3">
              <input v-model="oidcConfig.enabled" type="checkbox" class="form-check-input" role="switch" />
              <span class="form-check-label">Enable SSO login</span>
            </label>
            <div class="row g-3">
              <div class="col-12">
                <label class="form-label">Issuer URL</label>
                <input v-model="oidcConfig.issuer_url" class="form-control font-monospace" placeholder="https://accounts.example.com/realms/myrealm" />
                <div class="form-text">The discovery document will be fetched from <code>&lt;issuer&gt;/.well-known/openid-configuration</code>.</div>
              </div>
              <div class="col-sm-6">
                <label class="form-label">Client ID</label>
                <input v-model="oidcConfig.client_id" class="form-control font-monospace" />
              </div>
              <div class="col-sm-6">
                <label class="form-label">Client Secret</label>
                <input v-model="oidcConfig.client_secret" type="password" class="form-control" placeholder="••••••••" />
              </div>
              <div class="col-12">
                <label class="form-label">Redirect URI</label>
                <input v-model="oidcConfig.redirect_uri" class="form-control font-monospace" />
                <div class="form-text">Register exactly this URL as an allowed redirect in your identity provider.</div>
              </div>
              <div class="col-sm-6">
                <label class="form-label">Scopes</label>
                <input v-model="oidcConfig.scopes" class="form-control font-monospace" placeholder="openid email profile" />
              </div>
              <div class="col-12">
                <div class="d-flex align-items-center justify-content-between mb-2">
                  <div>
                    <label class="form-label mb-0">Claim → Role mapping</label>
                    <div class="form-text mt-0">
                      Role claim name:
                      <input v-model="oidcConfig.role_claim" class="form-control form-control-sm d-inline-block font-monospace" style="width:9rem;" placeholder="roles" />
                      — the claim may be a string or an array of strings.
                      If no mapping is configured, role is set to <strong>viewer</strong> on first login and managed manually thereafter.
                    </div>
                  </div>
                  <button type="button" class="btn btn-sm btn-outline-secondary d-inline-flex align-items-center gap-1 ms-3 flex-shrink-0" @click="addOidcMapping">
                    <IconPlus :size="14" /> Add
                  </button>
                </div>
                <table v-if="oidcConfig.role_mapping.length" class="table table-sm table-vcenter mb-0">
                  <thead>
                    <tr>
                      <th>Claim value</th>
                      <th style="width:9rem;">FloriDNS role</th>
                      <th class="w-1" />
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(m, i) in oidcConfig.role_mapping" :key="i">
                      <td><input v-model="m.claim_value" class="form-control form-control-sm font-monospace" placeholder="dns-admin" /></td>
                      <td>
                        <select v-model="m.role" class="form-select form-select-sm">
                          <option v-for="r in FLORIDNS_ROLES" :key="r" :value="r">{{ r }}</option>
                        </select>
                      </td>
                      <td><button type="button" class="btn btn-ghost-secondary btn-icon btn-sm text-danger" @click="removeOidcMapping(i)"><IconTrash :size="16" /></button></td>
                    </tr>
                  </tbody>
                </table>
                <div v-else class="text-muted small">No role mappings — role is managed manually in FloriDNS.</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Slave servers -->
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Slave / secondary servers</h3>
            <div v-if="auth.isSuperadmin" class="card-options d-flex gap-2">
              <button
                class="btn btn-secondary btn-sm d-inline-flex align-items-center gap-1"
                @click="addingServer = !addingServer"
              >
                <IconPlus :size="16" />
                Add server
              </button>
              <button
                class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1"
                :disabled="saving"
                @click="saveSlaveServers"
              >
                <span v-if="saving" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                Save
              </button>
            </div>
          </div>
          <div class="card-body">
            <p class="text-muted mb-3">
              Additional PowerDNS servers whose statistics can be queried from the Statistics view.
            </p>
            <div v-if="addingServer" class="card mb-3">
              <div class="card-body">
                <h4 class="card-title mb-3">New server</h4>
                <div class="row g-3">
                  <div class="col-sm-4">
                    <label class="form-label">Name</label>
                    <input v-model="newSlave.name" placeholder="ns2" class="form-control" />
                  </div>
                  <div class="col-sm-4">
                    <label class="form-label">URL</label>
                    <input v-model="newSlave.url" placeholder="http://ns2.example.com:8081" class="form-control" />
                  </div>
                  <div class="col-sm-4">
                    <label class="form-label">API Key</label>
                    <input v-model="newSlave.api_key" type="password" placeholder="••••••••" class="form-control" />
                  </div>
                  <div class="col-12">
                    <label class="form-check">
                      <input v-model="newSlave.ssl_verify" type="checkbox" class="form-check-input" />
                      <span class="form-check-label">Verify SSL certificate</span>
                    </label>
                  </div>
                </div>
                <div class="d-flex justify-content-end gap-2 mt-3">
                  <button class="btn btn-secondary btn-sm" @click="addingServer = false">Cancel</button>
                  <button class="btn btn-primary btn-sm" :disabled="!newSlave.name || !newSlave.url" @click="addServer">Add</button>
                </div>
              </div>
            </div>
            <div v-if="slaveServers.length" class="table-responsive">
              <table class="table table-vcenter">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>URL</th>
                    <th>API Key</th>
                    <th>SSL</th>
                    <th class="w-1" />
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(srv, idx) in slaveServers" :key="idx">
                    <td>{{ srv.name }}</td>
                    <td class="font-monospace">{{ srv.url }}</td>
                    <td class="text-muted">••••••••</td>
                    <td>
                      <span :class="['badge', srv.ssl_verify ? 'bg-green text-green-fg' : 'bg-yellow text-yellow-fg']">
                        {{ srv.ssl_verify ? 'verify' : 'skip' }}
                      </span>
                    </td>
                    <td>
                      <button v-if="auth.isSuperadmin" class="btn btn-ghost-secondary btn-icon btn-sm text-danger" @click="removeServer(idx)">
                        <IconTrash :size="16" />
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="text-muted">No slave servers configured.</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

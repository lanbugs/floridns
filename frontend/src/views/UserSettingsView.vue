<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import QRCode from 'qrcode'
import {
  IconPlus, IconTrash, IconKey, IconCopy, IconCheck,
  IconShieldCheck, IconShieldOff, IconShieldLock, IconFingerprint, IconEdit,
} from '@tabler/icons-vue'
import { api, useApiError } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'
import { usePasskey } from '@/composables/usePasskey'
import type { Zone } from '@/types'

const toast = useToast()
const auth = useAuthStore()
const { registerPasskey } = usePasskey()

// ── Passkeys ────────────────────────────────────────────────────────────────

interface PasskeyEntry {
  id: string
  name: string | null
  transports: string | null
  created_at: string
  last_used_at: string | null
}

const passkeys = ref<PasskeyEntry[]>([])
const passkeysLoading = ref(false)
const addingPasskey = ref(false)
const newPasskeyName = ref('')
const editingPasskeyId = ref<string | null>(null)
const editingPasskeyName = ref('')

async function loadPasskeys() {
  passkeysLoading.value = true
  try {
    passkeys.value = await api.get<PasskeyEntry[]>('/users/me/passkeys')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    passkeysLoading.value = false
  }
}

async function addPasskey() {
  addingPasskey.value = true
  try {
    await registerPasskey(newPasskeyName.value)
    newPasskeyName.value = ''
    await loadPasskeys()
    toast.success('Passkey registered successfully')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    addingPasskey.value = false
  }
}

function startRenamePasskey(pk: PasskeyEntry) {
  editingPasskeyId.value = pk.id
  editingPasskeyName.value = pk.name ?? ''
}

function cancelRenamePasskey() {
  editingPasskeyId.value = null
  editingPasskeyName.value = ''
}

async function saveRenamePasskey(pk: PasskeyEntry) {
  try {
    await api.patch(`/users/me/passkeys/${pk.id}`, { name: editingPasskeyName.value })
    await loadPasskeys()
    cancelRenamePasskey()
    toast.success('Passkey renamed')
  } catch (e) {
    toast.error(useApiError(e))
  }
}

async function deletePasskey(pk: PasskeyEntry) {
  if (!confirm(`Remove passkey "${pk.name ?? 'unnamed'}"?`)) return
  try {
    await api.delete(`/users/me/passkeys/${pk.id}`)
    passkeys.value = passkeys.value.filter(p => p.id !== pk.id)
    toast.success('Passkey removed')
  } catch (e) {
    toast.error(useApiError(e))
  }
}

// ── API Tokens ──────────────────────────────────────────────────────────────

interface ApiKey {
  id: string
  name: string
  scope: string
  zone_restriction: string | null
  is_active: boolean
  created_at: string
}
interface ApiKeyCreated extends ApiKey { key: string }

const keys = ref<ApiKey[]>([])
const zones = ref<Zone[]>([])
const keysLoading = ref(false)
const creating = ref(false)
const newKeyForm = ref({ name: '', scope: 'read-write', zone_restriction: '' })
const showForm = ref(false)
const newKeySecret = ref<ApiKeyCreated | null>(null)
const copied = ref(false)

const isAcmeScope = computed(() => newKeyForm.value.scope === 'acme')

async function loadKeys() {
  if (!auth.user) return
  keysLoading.value = true
  try {
    keys.value = await api.get<ApiKey[]>(`/users/${auth.user.id}/api-keys`)
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    keysLoading.value = false
  }
}

async function loadZones() {
  try {
    const resp = await api.get<{ items: Zone[] }>('/zones?page_size=500')
    zones.value = resp.items
  } catch {
    zones.value = []
  }
}

watch(() => newKeyForm.value.scope, (scope) => {
  if (scope !== 'acme') newKeyForm.value.zone_restriction = ''
})

async function createKey() {
  if (!auth.user || !newKeyForm.value.name.trim()) return
  creating.value = true
  try {
    const payload: Record<string, unknown> = {
      name: newKeyForm.value.name,
      scope: newKeyForm.value.scope,
    }
    if (isAcmeScope.value && newKeyForm.value.zone_restriction) {
      payload.zone_restriction = newKeyForm.value.zone_restriction
    }
    const created = await api.post<ApiKeyCreated>(`/users/${auth.user.id}/api-keys`, payload)
    newKeySecret.value = created
    keys.value.push(created)
    newKeyForm.value = { name: '', scope: 'read-write', zone_restriction: '' }
    showForm.value = false
    toast.success('API token created — copy the key now, it will not be shown again')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    creating.value = false
  }
}

async function deleteKey(key: ApiKey) {
  if (!auth.user) return
  if (!confirm(`Delete token "${key.name}"?`)) return
  try {
    await api.delete(`/users/${auth.user.id}/api-keys/${key.id}`)
    keys.value = keys.value.filter(k => k.id !== key.id)
    if (newKeySecret.value?.id === key.id) newKeySecret.value = null
    toast.success('Token deleted')
  } catch (e) {
    toast.error(useApiError(e))
  }
}

async function copyKey() {
  if (!newKeySecret.value) return
  await navigator.clipboard.writeText(newKeySecret.value.key)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('en-GB')
}

const origin = window.location.origin

// ── TOTP ────────────────────────────────────────────────────────────────────

const setupMode = ref(false)
const setupSecret = ref('')
const setupUri = ref('')
const setupCode = ref('')
const enabling = ref(false)
const canvasRef = ref<HTMLCanvasElement | null>(null)

const disableMode = ref(false)
const disableCode = ref('')
const disabling = ref(false)

async function startSetup() {
  try {
    const data = await api.get<{ secret: string; uri: string }>('/users/me/totp/setup')
    setupSecret.value = data.secret
    setupUri.value = data.uri
    setupMode.value = true
    await nextTick()
    if (canvasRef.value) {
      await QRCode.toCanvas(canvasRef.value, data.uri, { width: 200, margin: 2 })
    }
  } catch (e) {
    toast.error(useApiError(e))
  }
}

function cancelSetup() {
  setupMode.value = false
  setupSecret.value = ''
  setupUri.value = ''
  setupCode.value = ''
}

async function enableTotp() {
  enabling.value = true
  try {
    await api.post('/users/me/totp/enable', { secret: setupSecret.value, code: setupCode.value })
    await auth.fetchMe()
    cancelSetup()
    toast.success('Two-factor authentication enabled')
  } catch (e) {
    toast.error(useApiError(e))
    setupCode.value = ''
  } finally {
    enabling.value = false
  }
}

function startDisable() { disableMode.value = true }
function cancelDisable() { disableMode.value = false; disableCode.value = '' }

async function disableTotp() {
  disabling.value = true
  try {
    await api.post('/users/me/totp/disable', { code: disableCode.value })
    await auth.fetchMe()
    cancelDisable()
    toast.success('Two-factor authentication disabled')
  } catch (e) {
    toast.error(useApiError(e))
    disableCode.value = ''
  } finally {
    disabling.value = false
  }
}

function copySecret() {
  navigator.clipboard.writeText(setupSecret.value)
}

onMounted(async () => {
  await auth.fetchMe()
  await Promise.all([loadKeys(), loadPasskeys()])
  loadZones()
})
</script>

<template>
  <div>
    <div class="page-header d-print-none">
      <div class="container-xl">
        <div class="row g-2 align-items-center">
          <div class="col">
            <div class="page-pretitle">Account</div>
            <h2 class="page-title">User Settings</h2>
          </div>
          <div class="col-auto ms-auto d-print-none">
            <button
              class="btn btn-primary d-inline-flex align-items-center gap-1"
              @click="showForm = !showForm"
            >
              <IconPlus :size="16" />
              New API token
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">

        <!-- ── Two-factor authentication ── -->
        <div class="card mb-3">
          <div class="card-header">
            <h3 class="card-title">Two-factor authentication (TOTP)</h3>
            <div class="card-options">
              <span
                :class="['badge', auth.user?.totp_enabled ? 'bg-green text-green-fg' : 'bg-secondary text-secondary-fg']"
              >
                {{ auth.user?.totp_enabled ? 'Enabled' : 'Not enabled' }}
              </span>
            </div>
          </div>
          <div class="card-body">

            <!-- Forced TOTP banner -->
            <div v-if="auth.user?.totp_required && !auth.user?.totp_enabled" class="alert alert-warning d-flex align-items-center gap-2 mb-3">
              <IconShieldLock :size="18" class="flex-shrink-0" />
              <span>
                <strong>Two-factor authentication is required by your administrator.</strong>
                Please set it up below.
              </span>
            </div>

            <div class="d-flex align-items-center gap-3 mb-3">
              <span
                class="avatar"
                :style="auth.user?.totp_enabled
                  ? 'background-color: var(--tblr-green); color: #fff;'
                  : 'background-color: var(--tblr-secondary); color: #fff;'"
              >
                <IconShieldCheck v-if="auth.user?.totp_enabled" :size="22" />
                <IconShieldOff v-else :size="22" />
              </span>
              <div class="text-muted small">
                {{ auth.user?.totp_enabled
                  ? 'Your account is protected with a time-based one-time password.'
                  : 'Add an extra layer of security to your account.' }}
              </div>
            </div>

            <!-- Enable flow -->
            <template v-if="!auth.user?.totp_enabled">
              <button
                v-if="!setupMode"
                class="btn btn-primary d-inline-flex align-items-center gap-1"
                @click="startSetup"
              >
                Set up 2FA
              </button>

              <div v-else>
                <p class="text-muted mb-3">
                  Scan this QR code with your authenticator app (Google Authenticator, Aegis, Bitwarden, etc.),
                  then enter the 6-digit code to confirm.
                </p>
                <div class="row g-3 align-items-start">
                  <div class="col-auto">
                    <canvas ref="canvasRef" style="border-radius: 8px;" />
                  </div>
                  <div class="col">
                    <div class="mb-3">
                      <label class="form-label">Manual entry key</label>
                      <div class="input-group">
                        <input :value="setupSecret" readonly class="form-control font-monospace small" />
                        <button class="btn btn-outline-secondary" type="button" @click="copySecret">Copy</button>
                      </div>
                    </div>
                    <div class="mb-3">
                      <label class="form-label">Verification code</label>
                      <input
                        v-model="setupCode"
                        type="text"
                        inputmode="numeric"
                        pattern="[0-9]{6}"
                        maxlength="6"
                        class="form-control font-monospace"
                        placeholder="000000"
                        autocomplete="one-time-code"
                      />
                    </div>
                    <div class="d-flex gap-2">
                      <button class="btn btn-secondary" @click="cancelSetup">Cancel</button>
                      <button
                        class="btn btn-primary d-inline-flex align-items-center gap-1"
                        :disabled="enabling || setupCode.length !== 6"
                        @click="enableTotp"
                      >
                        <span v-if="enabling" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                        Enable 2FA
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </template>

            <!-- Disable flow -->
            <template v-else>
              <button
                v-if="!disableMode"
                class="btn btn-outline-danger"
                @click="startDisable"
              >
                Disable 2FA
              </button>

              <div v-else>
                <p class="text-muted mb-3">
                  Enter your current authenticator code to confirm disabling two-factor authentication.
                </p>
                <div class="row g-3">
                  <div class="col-sm-6">
                    <label class="form-label">Current code</label>
                    <input
                      v-model="disableCode"
                      type="text"
                      inputmode="numeric"
                      pattern="[0-9]{6}"
                      maxlength="6"
                      class="form-control font-monospace"
                      placeholder="000000"
                      autocomplete="one-time-code"
                    />
                  </div>
                </div>
                <div class="d-flex gap-2 mt-3">
                  <button class="btn btn-secondary" @click="cancelDisable">Cancel</button>
                  <button
                    class="btn btn-danger d-inline-flex align-items-center gap-1"
                    :disabled="disabling || disableCode.length !== 6"
                    @click="disableTotp"
                  >
                    <span v-if="disabling" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                    Disable 2FA
                  </button>
                </div>
              </div>
            </template>
          </div>
        </div>

        <!-- ── Passkeys ── -->
        <div class="card mb-3">
          <div class="card-header">
            <h3 class="card-title d-inline-flex align-items-center gap-2">
              <IconFingerprint :size="18" class="text-muted" />
              Passkeys
            </h3>
          </div>
          <div class="card-body pb-0">
            <p class="text-muted small mb-3">
              Passkeys let you sign in without a password using Face ID, Touch ID, or a hardware security key.
            </p>

            <!-- Add passkey -->
            <div class="row g-2 align-items-end mb-3">
              <div class="col">
                <label class="form-label">Passkey name <span class="text-muted">(optional)</span></label>
                <input
                  v-model="newPasskeyName"
                  type="text"
                  class="form-control"
                  placeholder="e.g. MacBook Touch ID, YubiKey"
                  :disabled="addingPasskey"
                />
              </div>
              <div class="col-auto">
                <button
                  class="btn btn-primary d-inline-flex align-items-center gap-1"
                  :disabled="addingPasskey"
                  @click="addPasskey"
                >
                  <span v-if="addingPasskey" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                  <IconPlus v-else :size="16" />
                  Add passkey
                </button>
              </div>
            </div>
          </div>

          <div class="table-responsive">
            <table class="table table-vcenter card-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Transports</th>
                  <th>Last used</th>
                  <th>Added</th>
                  <th class="w-1" />
                </tr>
              </thead>
              <tbody>
                <tr v-if="passkeysLoading">
                  <td colspan="5" class="text-center py-4">
                    <div class="spinner-border text-primary" />
                  </td>
                </tr>
                <tr v-else-if="passkeys.length === 0">
                  <td colspan="5" class="text-center text-muted py-4">
                    No passkeys registered yet.
                  </td>
                </tr>
                <tr v-for="pk in passkeys" :key="pk.id">
                  <td>
                    <template v-if="editingPasskeyId === pk.id">
                      <div class="input-group input-group-sm">
                        <input
                          v-model="editingPasskeyName"
                          class="form-control"
                          @keydown.enter="saveRenamePasskey(pk)"
                          @keydown.escape="cancelRenamePasskey"
                          autofocus
                        />
                        <button class="btn btn-primary btn-sm" @click="saveRenamePasskey(pk)">Save</button>
                        <button class="btn btn-secondary btn-sm" @click="cancelRenamePasskey">Cancel</button>
                      </div>
                    </template>
                    <template v-else>
                      <div class="d-flex align-items-center gap-2">
                        <IconFingerprint :size="16" class="text-muted flex-shrink-0" />
                        <span class="fw-medium">{{ pk.name ?? 'Unnamed passkey' }}</span>
                      </div>
                    </template>
                  </td>
                  <td class="text-muted small">{{ pk.transports ?? '—' }}</td>
                  <td class="text-muted small">{{ pk.last_used_at ? formatDate(pk.last_used_at) : 'Never' }}</td>
                  <td class="text-muted small">{{ formatDate(pk.created_at) }}</td>
                  <td>
                    <div class="d-flex gap-1">
                      <button
                        class="btn btn-ghost-secondary btn-icon btn-sm"
                        title="Rename passkey"
                        @click="startRenamePasskey(pk)"
                      >
                        <IconEdit :size="16" />
                      </button>
                      <button
                        class="btn btn-ghost-secondary btn-icon btn-sm text-danger"
                        title="Remove passkey"
                        @click="deletePasskey(pk)"
                      >
                        <IconTrash :size="16" />
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- ── API Tokens ── -->

        <!-- Newly created key banner -->
        <div v-if="newKeySecret" class="alert alert-warning d-flex align-items-start gap-3 mb-3">
          <IconKey :size="20" class="flex-shrink-0 mt-1" />
          <div class="flex-grow-1">
            <h4 class="alert-title">Copy your token now</h4>
            <p class="mb-2 text-muted small">This key will only be shown once. Store it in a safe place.</p>
            <div class="input-group">
              <input
                :value="newKeySecret.key"
                readonly
                class="form-control font-monospace"
                style="font-size: 0.8125rem"
              />
              <button class="btn btn-outline-secondary d-inline-flex align-items-center gap-1" @click="copyKey">
                <IconCheck v-if="copied" :size="16" class="text-success" />
                <IconCopy v-else :size="16" />
                {{ copied ? 'Copied' : 'Copy' }}
              </button>
            </div>
          </div>
          <button type="button" class="btn-close" @click="newKeySecret = null" />
        </div>

        <!-- Create form -->
        <div v-if="showForm" class="card mb-3">
          <div class="card-header">
            <h3 class="card-title">New API token</h3>
          </div>
          <div class="card-body">
            <div class="row g-3">
              <div class="col-sm-6">
                <label class="form-label">Name</label>
                <input
                  v-model="newKeyForm.name"
                  placeholder="e.g. Terraform, CI/CD pipeline"
                  class="form-control"
                  @keydown.enter="createKey"
                />
              </div>
              <div class="col-sm-6">
                <label class="form-label">Scope</label>
                <select v-model="newKeyForm.scope" class="form-select">
                  <option value="read-write">read-write — full access</option>
                  <option value="read-only">read-only — list and read only</option>
                  <option value="acme">acme — ACME DNS-01 challenges only</option>
                </select>
              </div>
              <div v-if="isAcmeScope" class="col-12">
                <label class="form-label">Zone restriction <span class="text-muted">(optional)</span></label>
                <select v-model="newKeyForm.zone_restriction" class="form-select">
                  <option value="">All zones (no restriction)</option>
                  <option v-for="z in zones" :key="z.id" :value="z.id">{{ z.name }}</option>
                </select>
                <div class="form-hint">When set, the key may only modify <code>_acme-challenge</code> TXT records in this zone.</div>
              </div>
            </div>
          </div>
          <div class="card-footer d-flex justify-content-end gap-2">
            <button class="btn btn-secondary" @click="showForm = false; newKeyForm = { name: '', scope: 'read-write', zone_restriction: '' }">Cancel</button>
            <button
              class="btn btn-primary d-inline-flex align-items-center gap-1"
              :disabled="creating || !newKeyForm.name.trim()"
              @click="createKey"
            >
              <span v-if="creating" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
              Create token
            </button>
          </div>
        </div>

        <!-- Token list -->
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">API Tokens</h3>
          </div>
          <div class="table-responsive">
            <table class="table table-vcenter card-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Scope</th>
                  <th>Zone restriction</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th class="w-1" />
                </tr>
              </thead>
              <tbody>
                <tr v-if="keysLoading">
                  <td colspan="6" class="text-center py-4">
                    <div class="spinner-border text-primary" />
                  </td>
                </tr>
                <tr v-else-if="keys.length === 0">
                  <td colspan="6" class="text-center text-muted py-4">
                    No API tokens yet. Create one to get started.
                  </td>
                </tr>
                <tr v-for="key in keys" :key="key.id">
                  <td>
                    <div class="d-flex align-items-center gap-2">
                      <IconKey :size="16" class="text-muted flex-shrink-0" />
                      <span class="fw-medium">{{ key.name }}</span>
                      <span v-if="newKeySecret?.id === key.id" class="badge bg-green text-green-fg">new</span>
                    </div>
                  </td>
                  <td>
                    <span :class="['badge', key.scope === 'read-write' ? 'bg-blue text-blue-fg' : key.scope === 'acme' ? 'bg-orange text-orange-fg' : 'bg-secondary text-secondary-fg']">
                      {{ key.scope }}
                    </span>
                  </td>
                  <td class="text-muted small">{{ key.zone_restriction ?? '—' }}</td>
                  <td>
                    <span :class="['badge', key.is_active ? 'bg-green text-green-fg' : 'bg-secondary text-secondary-fg']">
                      {{ key.is_active ? 'Active' : 'Inactive' }}
                    </span>
                  </td>
                  <td class="text-muted small">{{ formatDate(key.created_at) }}</td>
                  <td>
                    <button
                      class="btn btn-ghost-secondary btn-icon btn-sm text-danger"
                      title="Delete token"
                      @click="deleteKey(key)"
                    >
                      <IconTrash :size="16" />
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card mt-3">
          <div class="card-body">
            <h4 class="subheader mb-2">Using API tokens</h4>
            <p class="text-muted small mb-2">
              Pass the token in the <code>Authorization</code> header as a Bearer token:
            </p>
            <pre class="p-3 rounded font-monospace small mb-0" style="background: var(--tblr-code-bg, #f1f5f9); color: var(--tblr-code-color, #1e293b);">curl -H "Authorization: Bearer &lt;your-token&gt;" {{ origin }}/api/v1/zones</pre>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

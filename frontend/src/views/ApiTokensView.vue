<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { IconPlus, IconTrash, IconKey, IconCopy, IconCheck } from '@tabler/icons-vue'
import { api, useApiError } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'
import type { Zone } from '@/types'

const toast = useToast()
const auth = useAuthStore()

interface ApiKey {
  id: string
  name: string
  scope: string
  zone_restriction: string | null
  is_active: boolean
  created_at: string
}

interface ApiKeyCreated extends ApiKey {
  key: string
}

const keys = ref<ApiKey[]>([])
const zones = ref<Zone[]>([])
const loading = ref(false)
const creating = ref(false)
const newKeyForm = ref({ name: '', scope: 'read-write', zone_restriction: '' })
const showForm = ref(false)
const newKeySecret = ref<ApiKeyCreated | null>(null)
const copied = ref(false)

async function load() {
  if (!auth.user) return
  loading.value = true
  try {
    keys.value = await api.get<ApiKey[]>(`/users/${auth.user.id}/api-keys`)
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    loading.value = false
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

onMounted(() => {
  load()
  loadZones()
})

// Reset zone_restriction when scope changes away from acme
watch(() => newKeyForm.value.scope, (scope) => {
  if (scope !== 'acme') newKeyForm.value.zone_restriction = ''
})

const isAcmeScope = computed(() => newKeyForm.value.scope === 'acme')

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

function scopeBadgeClass(scope: string) {
  if (scope === 'read-write') return 'bg-blue text-blue-fg'
  if (scope === 'acme') return 'bg-purple text-purple-fg'
  return 'bg-secondary text-secondary-fg'
}

const origin = window.location.origin
</script>

<template>
  <div>
    <div class="page-header d-print-none">
      <div class="container-xl">
        <div class="row g-2 align-items-center">
          <div class="col">
            <div class="page-pretitle">Account</div>
            <h2 class="page-title">API Tokens</h2>
          </div>
          <div class="col-auto ms-auto d-print-none">
            <div class="btn-list">
              <button
                class="btn btn-primary d-inline-flex align-items-center gap-1"
                @click="showForm = !showForm"
              >
                <IconPlus :size="16" />
                New token
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">

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
                  placeholder="e.g. Terraform, certbot hook"
                  class="form-control"
                  @keydown.enter="createKey"
                />
              </div>
              <div class="col-sm-6">
                <label class="form-label">Scope</label>
                <select v-model="newKeyForm.scope" class="form-select">
                  <option value="read-write">read-write — full access</option>
                  <option value="read-only">read-only — list and read only</option>
                  <option value="acme">acme — ACME DNS-01 challenge only</option>
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
                <tr v-if="loading">
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
                    <span :class="['badge', scopeBadgeClass(key.scope)]">{{ key.scope }}</span>
                  </td>
                  <td class="text-muted small font-monospace">
                    {{ key.zone_restriction ?? '—' }}
                  </td>
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

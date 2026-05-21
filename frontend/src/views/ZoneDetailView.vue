<script setup lang="ts">
import { onMounted, ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  IconPlus, IconTrash, IconDownload, IconChevronLeft, IconPencil,
  IconShieldCheck, IconShieldOff, IconHistory, IconSearch,
  IconChevronUp, IconChevronDown, IconTemplate,
} from '@tabler/icons-vue'
import { useZonesStore } from '@/stores/zones'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import { useApiError, api } from '@/composables/useApi'
import type { RRSet, ZoneTemplate } from '@/types'

const props = defineProps<{ id: string }>()
const router = useRouter()
const zonesStore = useZonesStore()
const auth = useAuthStore()
const settingsStore = useSettingsStore()
const toast = useToast()

const showAddRecord = ref(false)
const saving = ref(false)

// --- Apply template ---
const showTemplateModal = ref(false)
const templates = ref<ZoneTemplate[]>([])
const selectedTemplateId = ref('')
const applyingTemplate = ref(false)

async function openTemplateModal() {
  try {
    templates.value = await api.get<ZoneTemplate[]>('/templates')
  } catch {
    templates.value = []
  }
  selectedTemplateId.value = ''
  showTemplateModal.value = true
}

async function applyTemplate() {
  if (!selectedTemplateId.value) return
  applyingTemplate.value = true
  try {
    await api.post(`/templates/${selectedTemplateId.value}/apply/${props.id}`, {})
    showTemplateModal.value = false
    await zonesStore.fetchZone(props.id)
    toast.success('Template applied successfully')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    applyingTemplate.value = false
  }
}

const editingRrset = ref<RRSet | null>(null)
const modalTitle = computed(() => (editingRrset.value ? 'Edit record' : 'Add record'))

const recordForm = ref({
  name: '',
  type: 'A',
  ttl: 3600,
  records: [''],
})

// Structured sub-fields for types that aren't a single free-text string
const mxEntries   = ref<{ priority: number; target: string }[]>([])
const srvEntries  = ref<{ priority: number; weight: number; port: number; target: string }[]>([])
const caaEntries  = ref<{ flag: number; tag: string; value: string }[]>([])
const tlsaEntries = ref<{ usage: number; selector: number; mtype: number; data: string }[]>([])


function _initDefaults(type: string): void {
  if (type === 'MX')   { mxEntries.value   = [{ priority: 10, target: '' }]; return }
  if (type === 'SRV')  { srvEntries.value  = [{ priority: 10, weight: 0, port: 443, target: '' }]; return }
  if (type === 'CAA')  { caaEntries.value  = [{ flag: 0, tag: 'issue', value: '' }]; return }
  if (type === 'TLSA') { tlsaEntries.value = [{ usage: 3, selector: 1, mtype: 1, data: '' }]; return }
  recordForm.value.records = ['']
}

function _parseToStructured(type: string, contents: string[]): void {
  if (type === 'MX') {
    mxEntries.value = contents.map((c) => {
      const p = c.split(/\s+/)
      return { priority: parseInt(p[0]) || 10, target: p[1] ?? '' }
    })
  } else if (type === 'SRV') {
    srvEntries.value = contents.map((c) => {
      const p = c.split(/\s+/)
      return { priority: parseInt(p[0]) || 10, weight: parseInt(p[1]) || 0, port: parseInt(p[2]) || 0, target: p[3] ?? '' }
    })
  } else if (type === 'CAA') {
    caaEntries.value = contents.map((c) => {
      const p = c.split(/\s+/, 3)
      return { flag: parseInt(p[0]) || 0, tag: p[1] ?? 'issue', value: (p[2] ?? '').replace(/^"|"$/g, '') }
    })
  } else if (type === 'TLSA') {
    tlsaEntries.value = contents.map((c) => {
      const p = c.split(/\s+/)
      return { usage: parseInt(p[0]) || 3, selector: parseInt(p[1]) || 1, mtype: parseInt(p[2]) || 1, data: p[3] ?? '' }
    })
  }
}

function _assembleContents(type: string): string[] {
  if (type === 'MX')   return mxEntries.value.filter(e => e.target).map(e => `${e.priority} ${e.target}`)
  if (type === 'SRV')  return srvEntries.value.filter(e => e.target).map(e => `${e.priority} ${e.weight} ${e.port} ${e.target}`)
  if (type === 'CAA')  return caaEntries.value.filter(e => e.value).map(e => `${e.flag} ${e.tag} "${e.value}"`)
  if (type === 'TLSA') return tlsaEntries.value.filter(e => e.data).map(e => `${e.usage} ${e.selector} ${e.mtype} ${e.data}`)
  return recordForm.value.records.filter(c => c.trim() !== '')
}

// Reset structured fields when type changes while creating a new record
watch(() => recordForm.value.type, (t) => {
  if (!editingRrset.value) _initDefaults(t)
})

const ALL_RECORD_TYPES = ['A', 'AAAA', 'CNAME', 'MX', 'NS', 'TXT', 'SRV', 'CAA', 'TLSA', 'PTR', 'ALIAS']

const recordTypes = computed((): string[] => {
  if (auth.isAdmin) return ALL_RECORD_TYPES
  const role = auth.user?.role ?? 'viewer'
  const allowed = settingsStore.getAllowedRecordTypes(role)
  if (!allowed) return ALL_RECORD_TYPES
  return ALL_RECORD_TYPES.filter((t) => allowed.includes(t))
})

const ttlPresets = [60, 300, 3600, 86400]

// --- Table controls ---
const recordSearch = ref('')
const typeFilter = ref('')
const sortKey = ref<'name' | 'type' | 'ttl'>('name')
const sortDir = ref<'asc' | 'desc'>('asc')
const pageSize = ref(25)
const page = ref(1)
const PAGE_SIZE_OPTIONS = [10, 25, 50, 100]

const filteredRrsets = computed(() => {
  const rrsets = zonesStore.currentZone?.rrsets ?? []
  let result = rrsets

  if (typeFilter.value) {
    result = result.filter((r) => r.type === typeFilter.value)
  }

  if (recordSearch.value.trim()) {
    const q = recordSearch.value.trim().toLowerCase()
    result = result.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        r.type.toLowerCase().includes(q) ||
        r.records.some((rec) => rec.content.toLowerCase().includes(q)),
    )
  }

  const dir = sortDir.value === 'asc' ? 1 : -1
  result = [...result].sort((a, b) => {
    const av = a[sortKey.value] ?? ''
    const bv = b[sortKey.value] ?? ''
    if (av < bv) return -dir
    if (av > bv) return dir
    return 0
  })

  return result
})

const totalPages = computed(() => Math.ceil(filteredRrsets.value.length / pageSize.value))

const pagedRrsets = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRrsets.value.slice(start, start + pageSize.value)
})

function sort(key: 'name' | 'type' | 'ttl'): void {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
  page.value = 1
}

// --- DNSSEC ---
interface DnssecKey {
  id: number
  type: string
  active: boolean
  algorithm: string
  bits: number
  dnskey: string
  ds?: string[]
}

interface DnssecExpiry {
  expiry: string | null
  days_remaining: number | null
  warning: boolean
  critical: boolean
}

const dnssecKeys = ref<DnssecKey[]>([])
const dnssecExpiry = ref<DnssecExpiry | null>(null)
const loadingDnssec = ref(false)
const togglingDnssec = ref(false)

async function loadDnssecKeys(): Promise<void> {
  if (!zonesStore.currentZone?.dnssec) {
    dnssecKeys.value = []
    dnssecExpiry.value = null
    return
  }
  loadingDnssec.value = true
  try {
    const [keysData, expiryData] = await Promise.all([
      api.get<{ cryptokeys: DnssecKey[] }>(`/zones/${props.id}/dnssec`),
      api.get<DnssecExpiry>(`/zones/${props.id}/dnssec/expiry`),
    ])
    dnssecKeys.value = Array.isArray(keysData?.cryptokeys) ? keysData.cryptokeys : []
    dnssecExpiry.value = expiryData
  } catch {
    dnssecKeys.value = []
    dnssecExpiry.value = null
  } finally {
    loadingDnssec.value = false
  }
}

async function toggleDnssec(): Promise<void> {
  if (!zonesStore.currentZone) return
  const action = zonesStore.currentZone.dnssec ? 'disable' : 'enable'
  if (!confirm(`${action === 'enable' ? 'Enable' : 'Disable'} DNSSEC for ${zonesStore.currentZone.name}?`)) return
  togglingDnssec.value = true
  try {
    await api.post(`/zones/${props.id}/dnssec/${action}`, {})
    toast.success(`DNSSEC ${action === 'enable' ? 'enabled' : 'disabled'}`)
    await zonesStore.fetchZone(props.id)
    await loadDnssecKeys()
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    togglingDnssec.value = false
  }
}

onMounted(async () => {
  await zonesStore.fetchZone(props.id)
  if (!auth.isAdmin) {
    await settingsStore.fetchSettings()
  }
  await loadDnssecKeys()
})

function normalizeName(name: string): string {
  const zoneName = zonesStore.currentZone?.name ?? ''
  if (!name || name === '@') return zoneName
  if (name.endsWith('.')) return name
  return `${name}.${zoneName}`
}

function openAddModal(): void {
  editingRrset.value = null
  const type = recordTypes.value[0] ?? 'A'
  recordForm.value = { name: '', type, ttl: 3600, records: [''] }
  _initDefaults(type)
  showAddRecord.value = true
}

function openEditModal(rrset: RRSet): void {
  editingRrset.value = rrset
  const contents = rrset.records.map((r) => r.content)
  recordForm.value = { name: rrset.name, type: rrset.type, ttl: rrset.ttl, records: contents }
  _parseToStructured(rrset.type, contents)
  showAddRecord.value = true
}

function closeModal(): void {
  showAddRecord.value = false
  editingRrset.value = null
}

function addRecordValue(): void {
  recordForm.value.records.push('')
}

function removeRecordValue(i: number): void {
  recordForm.value.records.splice(i, 1)
}

async function saveRecord(): Promise<void> {
  saving.value = true
  try {
    const newName = normalizeName(recordForm.value.name)
    const rrsets: object[] = []

    if (editingRrset.value && editingRrset.value.name !== newName) {
      rrsets.push({ name: editingRrset.value.name, type: editingRrset.value.type, changetype: 'DELETE' })
    }

    rrsets.push({
      name: newName,
      type: recordForm.value.type,
      ttl: recordForm.value.ttl,
      records: _assembleContents(recordForm.value.type).map((content) => ({ content, disabled: false })),
      changetype: 'REPLACE',
    })

    await api.patch(`/zones/${props.id}/records`, { rrsets })
    toast.success(editingRrset.value ? 'Record updated' : 'Record saved')
    closeModal()
    await zonesStore.fetchZone(props.id)
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    saving.value = false
  }
}

async function deleteRrset(rrset: RRSet) {
  if (!confirm(`Delete ${rrset.name} ${rrset.type}?`)) return
  try {
    await api.patch(`/zones/${props.id}/records`, {
      rrsets: [{ name: rrset.name, type: rrset.type, changetype: 'DELETE' }],
    })
    toast.success('Record deleted')
    await zonesStore.fetchZone(props.id)
  } catch (e) {
    toast.error(useApiError(e))
  }
}

async function exportZone() {
  try {
    const data = await api.get<string>(`/zones/${props.id}/export`)
    const blob = new Blob([data as unknown as string], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${zonesStore.currentZone?.name ?? 'zone'}.zone`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    toast.error(useApiError(e))
  }
}

</script>

<template>
  <div>
    <div class="page-header d-print-none">
      <div class="container-xl">
        <div class="row g-2 align-items-center">
          <div class="col-auto">
            <button class="btn btn-ghost-secondary btn-sm d-inline-flex align-items-center gap-1" @click="router.push('/zones')">
              <IconChevronLeft :size="16" />
              Back
            </button>
          </div>
          <div class="col">
            <div class="page-pretitle">DNS Management</div>
            <h2 class="page-title font-monospace">
              {{ zonesStore.currentZone?.name ?? '…' }}
            </h2>
            <div v-if="zonesStore.currentZone" class="d-flex align-items-center gap-2 mt-1">
              <span class="badge bg-blue text-blue-fg">{{ zonesStore.currentZone.kind }}</span>
              <span :class="['badge', zonesStore.currentZone.dnssec ? 'bg-green text-green-fg' : 'bg-secondary text-secondary-fg']">
                DNSSEC {{ zonesStore.currentZone.dnssec ? 'active' : 'inactive' }}
              </span>
              <span class="text-muted small font-monospace">
                Serial: {{ zonesStore.currentZone.serial }}
              </span>
            </div>
          </div>
          <div class="col-auto ms-auto d-print-none">
            <div class="btn-list">
              <button
                v-if="auth.isAdmin && zonesStore.currentZone"
                class="btn d-inline-flex align-items-center gap-1"
                :class="zonesStore.currentZone.dnssec ? 'btn-warning' : 'btn-success'"
                :disabled="togglingDnssec"
                @click="toggleDnssec"
              >
                <span v-if="togglingDnssec" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                <IconShieldOff v-else-if="zonesStore.currentZone.dnssec" :size="16" />
                <IconShieldCheck v-else :size="16" />
                {{ zonesStore.currentZone.dnssec ? 'Disable DNSSEC' : 'Enable DNSSEC' }}
              </button>
              <button class="btn btn-secondary d-inline-flex align-items-center gap-1" @click="router.push(`/zones/${props.id}/history`)">
                <IconHistory :size="16" />
                History
              </button>
              <button class="btn btn-secondary d-inline-flex align-items-center gap-1" @click="exportZone">
                <IconDownload :size="16" />
                Export
              </button>
              <button
                v-if="auth.isAdmin"
                class="btn btn-secondary d-inline-flex align-items-center gap-1"
                @click="openTemplateModal"
              >
                <IconTemplate :size="16" />
                Apply template
              </button>
              <button
                v-if="zonesStore.currentZone?.can_edit"
                class="btn btn-primary d-inline-flex align-items-center gap-1"
                @click="openAddModal"
              >
                <IconPlus :size="16" />
                Add record
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">

        <!-- DNSSEC status info (only when active) -->
        <div v-if="zonesStore.currentZone?.dnssec" class="card mb-3">
          <div class="card-header">
            <h3 class="card-title d-flex align-items-center gap-2">
              <IconShieldCheck :size="18" class="text-success" />
              DNSSEC — Active
            </h3>
            <!-- Expiry badge -->
            <div v-if="dnssecExpiry?.expiry" class="card-options">
              <span
                :class="[
                  'badge d-inline-flex align-items-center gap-1',
                  dnssecExpiry.critical ? 'bg-red text-red-fg' :
                  dnssecExpiry.warning  ? 'bg-yellow text-yellow-fg' :
                                          'bg-green text-green-fg',
                ]"
              >
                Signatures expire in {{ dnssecExpiry.days_remaining }} day{{ dnssecExpiry.days_remaining === 1 ? '' : 's' }}
              </span>
            </div>
          </div>

          <!-- Expiry warning alert -->
          <div
            v-if="dnssecExpiry?.warning && !loadingDnssec"
            :class="['alert m-3 mb-0', dnssecExpiry.critical ? 'alert-danger' : 'alert-warning']"
            role="alert"
          >
            <strong>{{ dnssecExpiry.critical ? 'Critical:' : 'Warning:' }}</strong>
            DNSSEC signatures expire on {{ new Date(dnssecExpiry.expiry!).toLocaleString() }}
            ({{ dnssecExpiry.days_remaining }} day{{ dnssecExpiry.days_remaining === 1 ? '' : 's' }} remaining).
            Make sure PowerDNS is re-signing the zone automatically.
          </div>

          <div v-if="loadingDnssec" class="card-body text-center py-3">
            <div class="spinner-border spinner-border-sm text-primary" />
          </div>
          <div v-else-if="dnssecKeys.length" class="table-responsive">
            <table class="table table-vcenter card-table">
              <thead>
                <tr>
                  <th>Key type</th>
                  <th>Algorithm</th>
                  <th>Bits</th>
                  <th>Status</th>
                  <th>Signature expiry</th>
                  <th>DS records</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="key in dnssecKeys" :key="key.id">
                  <td><span class="badge bg-blue text-blue-fg">{{ key.type }}</span></td>
                  <td class="font-monospace small">{{ key.algorithm }}</td>
                  <td class="text-muted">{{ key.bits }}</td>
                  <td>
                    <span :class="['badge', key.active ? 'bg-green text-green-fg' : 'bg-secondary text-secondary-fg']">
                      {{ key.active ? 'Active' : 'Inactive' }}
                    </span>
                  </td>
                  <td class="text-muted small">
                    <template v-if="dnssecExpiry?.expiry">
                      {{ new Date(dnssecExpiry.expiry).toLocaleDateString() }}
                    </template>
                    <span v-else class="text-muted">–</span>
                  </td>
                  <td>
                    <div v-if="key.ds?.length" class="font-monospace small">
                      <div v-for="(ds, i) in key.ds" :key="i" class="text-truncate" style="max-width: 400px;" :title="ds">{{ ds }}</div>
                    </div>
                    <span v-else class="text-muted">–</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="card-body text-muted small">No key details available.</div>
        </div>

        <!-- Records card -->
        <div class="card">
          <div class="card-header gap-2 flex-wrap">
            <!-- Record search -->
            <div class="input-group" style="max-width: 260px;">
              <span class="input-group-text"><IconSearch :size="16" /></span>
              <input
                v-model="recordSearch"
                type="search"
                placeholder="Search records…"
                class="form-control"
                @input="page = 1"
              />
            </div>
            <!-- Type filter -->
            <div class="btn-group" role="group" aria-label="Filter by record type">
              <button
                v-for="t in ['', 'A', 'AAAA', 'CNAME', 'MX', 'NS', 'TXT', 'SOA']"
                :key="t"
                type="button"
                class="btn btn-sm"
                :class="typeFilter === t ? 'btn-primary' : 'btn-outline-secondary'"
                @click="typeFilter = t; page = 1"
              >
                {{ t || 'All' }}
              </button>
            </div>
            <!-- Page size selector -->
            <div class="ms-auto d-flex align-items-center gap-2">
              <span class="text-muted small">Rows:</span>
              <select v-model="pageSize" class="form-select form-select-sm" style="width: auto;" @change="page = 1">
                <option v-for="n in PAGE_SIZE_OPTIONS" :key="n" :value="n">{{ n }}</option>
              </select>
            </div>
          </div>

          <div class="table-responsive">
            <table class="table table-vcenter card-table">
              <thead>
                <tr>
                  <th style="cursor:pointer;" @click="sort('name')">
                    <div class="d-flex align-items-center gap-1">
                      Name
                      <IconChevronUp v-if="sortKey === 'name' && sortDir === 'asc'" :size="12" />
                      <IconChevronDown v-else-if="sortKey === 'name' && sortDir === 'desc'" :size="12" />
                      <span v-else class="opacity-0"><IconChevronUp :size="12" /></span>
                    </div>
                  </th>
                  <th style="cursor:pointer;" @click="sort('type')">
                    <div class="d-flex align-items-center gap-1">
                      Type
                      <IconChevronUp v-if="sortKey === 'type' && sortDir === 'asc'" :size="12" />
                      <IconChevronDown v-else-if="sortKey === 'type' && sortDir === 'desc'" :size="12" />
                      <span v-else class="opacity-0"><IconChevronUp :size="12" /></span>
                    </div>
                  </th>
                  <th style="cursor:pointer;" @click="sort('ttl')">
                    <div class="d-flex align-items-center gap-1">
                      TTL
                      <IconChevronUp v-if="sortKey === 'ttl' && sortDir === 'asc'" :size="12" />
                      <IconChevronDown v-else-if="sortKey === 'ttl' && sortDir === 'desc'" :size="12" />
                      <span v-else class="opacity-0"><IconChevronUp :size="12" /></span>
                    </div>
                  </th>
                  <th>Content</th>
                  <th class="w-1" />
                </tr>
              </thead>
              <tbody>
                <tr v-if="zonesStore.loading">
                  <td colspan="5" class="text-center py-4">
                    <div class="spinner-border text-primary" />
                  </td>
                </tr>
                <tr v-else-if="pagedRrsets.length === 0">
                  <td colspan="5" class="text-center text-muted py-4">No records found.</td>
                </tr>
                <template v-else>
                  <template v-for="rrset in pagedRrsets" :key="`${rrset.name}-${rrset.type}`">
                    <tr v-for="(record, i) in rrset.records" :key="i">
                      <td>
                        <code v-if="i === 0" class="font-monospace">{{ rrset.name }}</code>
                      </td>
                      <td>
                        <span v-if="i === 0" class="badge bg-secondary text-secondary-fg">{{ rrset.type }}</span>
                      </td>
                      <td class="text-muted">{{ i === 0 ? rrset.ttl : '' }}</td>
                      <td>
                        <span
                          class="font-monospace"
                          :class="{ 'opacity-50 text-decoration-line-through': record.disabled }"
                        >{{ record.content }}</span>
                      </td>
                      <td v-if="i === 0" :rowspan="rrset.records.length">
                        <div class="d-flex align-items-center gap-1">
                          <button
                            v-if="zonesStore.currentZone?.can_edit"
                            class="btn btn-ghost-secondary btn-icon btn-sm"
                            @click="openEditModal(rrset)"
                          >
                            <IconPencil :size="16" />
                          </button>
                          <button
                            v-if="zonesStore.currentZone?.can_edit"
                            class="btn btn-ghost-secondary btn-icon btn-sm text-danger"
                            @click="deleteRrset(rrset)"
                          >
                            <IconTrash :size="16" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  </template>
                </template>
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div v-if="filteredRrsets.length > pageSize" class="card-footer d-flex align-items-center">
            <p class="m-0 text-muted small">
              Showing
              {{ (page - 1) * pageSize + 1 }}–{{ Math.min(page * pageSize, filteredRrsets.length) }}
              of {{ filteredRrsets.length }} records
            </p>
            <ul class="pagination m-0 ms-auto">
              <li class="page-item" :class="{ disabled: page <= 1 }">
                <button class="page-link" @click="page--">prev</button>
              </li>
              <li
                v-for="p in totalPages"
                :key="p"
                class="page-item"
                :class="{ active: p === page }"
              >
                <button class="page-link" @click="page = p">{{ p }}</button>
              </li>
              <li class="page-item" :class="{ disabled: page >= totalPages }">
                <button class="page-link" @click="page++">next</button>
              </li>
            </ul>
          </div>
        </div>

      </div>
    </div>

    <Teleport to="body">
      <template v-if="showAddRecord">
        <div class="modal modal-blur fade show" style="display: block;" tabindex="-1" role="dialog" @click.self="closeModal">
          <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">{{ modalTitle }}</h5>
                <button type="button" class="btn-close" @click="closeModal" />
              </div>
              <div class="modal-body">
                <div class="row g-3 mb-3">
                  <div class="col">
                    <label class="form-label">Name</label>
                    <input
                      v-model="recordForm.name"
                      :placeholder="zonesStore.currentZone?.name"
                      class="form-control"
                    />
                    <div class="form-text">
                      Leave empty or use @ for apex. Relative names are auto-completed.
                    </div>
                  </div>
                  <div class="col-auto">
                    <label class="form-label">Type</label>
                    <select v-model="recordForm.type" :disabled="!!editingRrset" class="form-select">
                      <option v-for="t in recordTypes" :key="t">{{ t }}</option>
                    </select>
                  </div>
                </div>

                <div class="mb-3">
                  <label class="form-label">TTL</label>
                  <div class="d-flex align-items-center gap-2">
                    <div class="btn-group" role="group" aria-label="TTL presets">
                      <button
                        v-for="preset in ttlPresets"
                        :key="preset"
                        type="button"
                        class="btn btn-sm"
                        :class="recordForm.ttl === preset ? 'btn-primary' : 'btn-outline-secondary'"
                        @click="recordForm.ttl = preset"
                      >
                        {{ preset >= 3600 ? preset / 3600 + 'h' : preset + 's' }}
                      </button>
                    </div>
                    <input
                      v-model.number="recordForm.ttl"
                      type="number"
                      min="0"
                      class="form-control w-auto"
                      style="max-width: 6rem;"
                    />
                  </div>
                </div>

                <!-- MX -->
                <template v-if="recordForm.type === 'MX'">
                  <div class="mb-1 d-flex align-items-center justify-content-between">
                    <label class="form-label mb-0">Mail Servers</label>
                    <button type="button" class="btn btn-sm btn-link p-0 d-flex align-items-center gap-1" @click="mxEntries.push({ priority: 10, target: '' })">
                      <IconPlus :size="14" /> Add
                    </button>
                  </div>
                  <div class="d-flex flex-column gap-2 mb-3">
                    <div v-for="(mx, i) in mxEntries" :key="i" class="input-group">
                      <input v-model.number="mx.priority" type="number" min="0" max="65535" class="form-control font-monospace" style="max-width:5rem;" placeholder="Prio" required />
                      <input v-model="mx.target" type="text" class="form-control font-monospace" placeholder="mail.example.com" required />
                      <button v-if="mxEntries.length > 1" type="button" class="btn btn-outline-secondary" @click="mxEntries.splice(i, 1)"><IconTrash :size="16" /></button>
                    </div>
                  </div>
                </template>

                <!-- SRV -->
                <template v-else-if="recordForm.type === 'SRV'">
                  <div class="mb-1 d-flex align-items-center justify-content-between">
                    <label class="form-label mb-0">SRV Records</label>
                    <button type="button" class="btn btn-sm btn-link p-0 d-flex align-items-center gap-1" @click="srvEntries.push({ priority: 10, weight: 10, port: 443, target: '' })">
                      <IconPlus :size="14" /> Add
                    </button>
                  </div>
                  <div class="d-flex flex-column gap-2 mb-3">
                    <div v-for="(srv, i) in srvEntries" :key="i" class="d-flex flex-column gap-1">
                      <div class="input-group">
                        <span class="input-group-text" style="min-width:4.5rem;">Priority</span>
                        <input v-model.number="srv.priority" type="number" min="0" max="65535" class="form-control font-monospace" required />
                        <span class="input-group-text" style="min-width:4.5rem;">Weight</span>
                        <input v-model.number="srv.weight" type="number" min="0" max="65535" class="form-control font-monospace" required />
                        <span class="input-group-text" style="min-width:3.5rem;">Port</span>
                        <input v-model.number="srv.port" type="number" min="0" max="65535" class="form-control font-monospace" required />
                        <button v-if="srvEntries.length > 1" type="button" class="btn btn-outline-secondary" @click="srvEntries.splice(i, 1)"><IconTrash :size="16" /></button>
                      </div>
                      <div class="input-group">
                        <span class="input-group-text" style="min-width:4.5rem;">Target</span>
                        <input v-model="srv.target" type="text" class="form-control font-monospace" placeholder="service.example.com" required />
                      </div>
                    </div>
                  </div>
                </template>

                <!-- CAA -->
                <template v-else-if="recordForm.type === 'CAA'">
                  <div class="mb-1 d-flex align-items-center justify-content-between">
                    <label class="form-label mb-0">CAA Records</label>
                    <button type="button" class="btn btn-sm btn-link p-0 d-flex align-items-center gap-1" @click="caaEntries.push({ flag: 0, tag: 'issue', value: '' })">
                      <IconPlus :size="14" /> Add
                    </button>
                  </div>
                  <div class="d-flex flex-column gap-2 mb-3">
                    <div v-for="(caa, i) in caaEntries" :key="i" class="input-group">
                      <input v-model.number="caa.flag" type="number" min="0" max="255" class="form-control font-monospace" style="max-width:4.5rem;" placeholder="Flag" required />
                      <select v-model="caa.tag" class="form-select" style="max-width:8rem;" required>
                        <option value="issue">issue</option>
                        <option value="issuewild">issuewild</option>
                        <option value="iodef">iodef</option>
                      </select>
                      <input v-model="caa.value" type="text" class="form-control font-monospace" placeholder='"letsencrypt.org"' required />
                      <button v-if="caaEntries.length > 1" type="button" class="btn btn-outline-secondary" @click="caaEntries.splice(i, 1)"><IconTrash :size="16" /></button>
                    </div>
                  </div>
                </template>

                <!-- TLSA -->
                <template v-else-if="recordForm.type === 'TLSA'">
                  <div class="mb-1 d-flex align-items-center justify-content-between">
                    <label class="form-label mb-0">TLSA Records</label>
                    <button type="button" class="btn btn-sm btn-link p-0 d-flex align-items-center gap-1" @click="tlsaEntries.push({ usage: 3, selector: 1, mtype: 1, data: '' })">
                      <IconPlus :size="14" /> Add
                    </button>
                  </div>
                  <div class="d-flex flex-column gap-2 mb-3">
                    <div v-for="(tlsa, i) in tlsaEntries" :key="i" class="d-flex flex-column gap-1">
                      <div class="input-group">
                        <span class="input-group-text" style="min-width:5.5rem;">Usage</span>
                        <input v-model.number="tlsa.usage" type="number" min="0" max="255" class="form-control font-monospace" required />
                        <span class="input-group-text" style="min-width:5.5rem;">Selector</span>
                        <input v-model.number="tlsa.selector" type="number" min="0" max="255" class="form-control font-monospace" required />
                        <span class="input-group-text" style="min-width:4.5rem;">Type</span>
                        <input v-model.number="tlsa.mtype" type="number" min="0" max="255" class="form-control font-monospace" required />
                        <button v-if="tlsaEntries.length > 1" type="button" class="btn btn-outline-secondary" @click="tlsaEntries.splice(i, 1)"><IconTrash :size="16" /></button>
                      </div>
                      <div class="input-group">
                        <span class="input-group-text" style="min-width:5.5rem;">Data (hex)</span>
                        <input v-model="tlsa.data" type="text" class="form-control font-monospace" placeholder="a0b1c2d3..." required />
                      </div>
                    </div>
                  </div>
                </template>

                <!-- TXT -->
                <template v-else-if="recordForm.type === 'TXT'">
                  <div class="mb-1 d-flex align-items-center justify-content-between">
                    <label class="form-label mb-0">Content{{ recordForm.records.length > 1 ? ' (multiple values)' : '' }}</label>
                    <button type="button" class="btn btn-sm btn-link p-0 d-flex align-items-center gap-1" @click="addRecordValue">
                      <IconPlus :size="14" /> Add value
                    </button>
                  </div>
                  <div class="d-flex flex-column gap-2 mb-3">
                    <div v-for="(_, i) in recordForm.records" :key="i" class="input-group align-items-start">
                      <textarea v-model="recordForm.records[i]" rows="3" class="form-control font-monospace" required />
                      <button v-if="recordForm.records.length > 1" type="button" class="btn btn-outline-secondary" @click="removeRecordValue(i)"><IconTrash :size="16" /></button>
                    </div>
                  </div>
                </template>

                <!-- CNAME / PTR / ALIAS — single hostname -->
                <template v-else-if="['CNAME', 'PTR', 'ALIAS'].includes(recordForm.type)">
                  <div class="mb-3">
                    <label class="form-label">Target</label>
                    <input v-model="recordForm.records[0]" type="text" class="form-control font-monospace" placeholder="target.example.com" required />
                  </div>
                </template>

                <!-- A / AAAA / NS / default — multi-value free text -->
                <template v-else>
                  <div class="mb-1 d-flex align-items-center justify-content-between">
                    <label class="form-label mb-0">Content{{ recordForm.records.length > 1 ? ' (multiple values)' : '' }}</label>
                    <button type="button" class="btn btn-sm btn-link p-0 d-flex align-items-center gap-1" @click="addRecordValue">
                      <IconPlus :size="14" /> Add value
                    </button>
                  </div>
                  <div class="d-flex flex-column gap-2 mb-3">
                    <div v-for="(_, i) in recordForm.records" :key="i" class="input-group">
                      <input v-model="recordForm.records[i]" required class="form-control font-monospace" />
                      <button v-if="recordForm.records.length > 1" type="button" class="btn btn-outline-secondary" @click="removeRecordValue(i)"><IconTrash :size="16" /></button>
                    </div>
                  </div>
                </template>
              </div>
              <div class="modal-footer">
                <button class="btn btn-secondary" @click="closeModal">Cancel</button>
                <button
                  class="btn btn-primary d-inline-flex align-items-center gap-1"
                  :disabled="saving"
                  @click="saveRecord"
                >
                  <span v-if="saving" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                  {{ editingRrset ? 'Update' : 'Save' }}
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-backdrop fade show" @click="closeModal" />
      </template>

      <!-- Apply template modal -->
      <template v-if="showTemplateModal">
        <div class="modal modal-blur fade show" style="display:block;" tabindex="-1" @click.self="showTemplateModal = false">
          <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">Apply template</h5>
                <button type="button" class="btn-close" @click="showTemplateModal = false" />
              </div>
              <div class="modal-body">
                <div v-if="templates.length === 0" class="text-muted text-center py-3">
                  No templates defined. Create templates under Administration → Templates.
                </div>
                <template v-else>
                  <p class="text-muted mb-3">
                    Select a template to apply to <strong>{{ zonesStore.currentZone?.name }}</strong>.
                    Existing records with the same name and type will be replaced.
                  </p>
                  <div class="mb-3">
                    <label class="form-label">Template</label>
                    <select v-model="selectedTemplateId" class="form-select">
                      <option value="">— Select a template —</option>
                      <option v-for="tpl in templates" :key="tpl.id" :value="tpl.id">
                        {{ tpl.name }}{{ tpl.description ? ` — ${tpl.description}` : '' }}
                        ({{ tpl.records.length }} records)
                      </option>
                    </select>
                  </div>
                  <div v-if="selectedTemplateId" class="table-responsive" style="max-height:240px;overflow-y:auto;">
                    <table class="table table-vcenter table-sm mb-0">
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Type</th>
                          <th>TTL</th>
                          <th>Content</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="r in templates.find(t => t.id === selectedTemplateId)?.records" :key="r.id">
                          <td class="font-monospace small">{{ r.name }}</td>
                          <td><span class="badge bg-secondary text-secondary-fg">{{ r.type }}</span></td>
                          <td class="text-muted small">{{ r.ttl }}</td>
                          <td class="font-monospace small text-truncate" style="max-width:200px;" :title="r.content">{{ r.content }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </template>
              </div>
              <div class="modal-footer">
                <button class="btn btn-secondary" @click="showTemplateModal = false">Cancel</button>
                <button
                  v-if="templates.length > 0"
                  class="btn btn-primary d-inline-flex align-items-center gap-1"
                  :disabled="!selectedTemplateId || applyingTemplate"
                  @click="applyTemplate"
                >
                  <span v-if="applyingTemplate" class="spinner-border spinner-border-sm" style="width:.9em;height:.9em;" />
                  Apply
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-backdrop fade show" @click="showTemplateModal = false" />
      </template>

    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  IconPlus, IconTrash, IconSearch, IconChevronRight,
  IconShieldCheck, IconShieldOff, IconChevronUp, IconChevronDown,
  IconUpload, IconAlertTriangle, IconCircleCheck, IconEdit,
} from '@tabler/icons-vue'
import { useZonesStore } from '@/stores/zones'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useApiError, api } from '@/composables/useApi'
import type { Zone, Account, ZoneTemplate } from '@/types'

const router = useRouter()
const zonesStore = useZonesStore()
const auth = useAuthStore()
const toast = useToast()

const search = ref('')
const page = ref(1)
const pageSize = ref(25)
const sortKey = ref<keyof Zone>('name')
const sortDir = ref<'asc' | 'desc'>('asc')
const showCreateModal = ref(false)
const showImportModal = ref(false)

const form = ref({ name: '', kind: 'Master' as 'Native' | 'Master' | 'Slave', nameservers: '', masters: '', accountId: '', templateId: '' })
const creating = ref(false)
const accounts = ref<Account[]>([])
const templates = ref<ZoneTemplate[]>([])

async function loadAccounts(): Promise<void> {
  try {
    accounts.value = await api.get<Account[]>('/accounts')
  } catch {
    accounts.value = []
  }
}

async function loadTemplates(): Promise<void> {
  try {
    templates.value = await api.get<ZoneTemplate[]>('/templates')
  } catch {
    templates.value = []
  }
}

// --- Import ---
type ImportStep = 'upload' | 'preview' | 'done'
const importStep = ref<ImportStep>('upload')
const importFormat = ref<'bind' | 'csv'>('bind')
const importKind = ref<'Native' | 'Master' | 'Slave'>('Master')
const importZoneName = ref('')
const importFile = ref<File | null>(null)
const importFileInput = ref<HTMLInputElement | null>(null)
const importLoading = ref(false)
const importError = ref('')

interface ImportPreview {
  zone_name: string
  kind: string
  already_exists: boolean
  rrset_count: number
  record_count: number
  errors: string[]
  preview: { name: string; type: string; ttl: number; record_count: number }[]
}
const importPreview = ref<ImportPreview | null>(null)

function openImport(): void {
  importStep.value = 'upload'
  importFormat.value = 'bind'
  importKind.value = 'Master'
  importZoneName.value = ''
  importFile.value = null
  importError.value = ''
  importPreview.value = null
  showImportModal.value = true
}

function onFileChange(e: Event): void {
  const target = e.target as HTMLInputElement
  importFile.value = target.files?.[0] ?? null
}

async function runPreview(): Promise<void> {
  if (!importFile.value) {
    importError.value = 'Please select a file.'
    return
  }
  if (importFormat.value === 'csv' && !importZoneName.value.trim()) {
    importError.value = 'Zone name is required for CSV import.'
    return
  }
  importError.value = ''
  importLoading.value = true
  try {
    const fd = new FormData()
    fd.append('file', importFile.value)
    fd.append('format', importFormat.value)
    fd.append('zone_name', importZoneName.value.trim())
    fd.append('kind', importKind.value)
    fd.append('dry_run', 'true')
    importPreview.value = await api.post<ImportPreview>('/zones/import', fd)
    importStep.value = 'preview'
  } catch (e) {
    importError.value = useApiError(e)
  } finally {
    importLoading.value = false
  }
}

async function confirmImport(): Promise<void> {
  if (!importFile.value || !importPreview.value) return
  importLoading.value = true
  try {
    const fd = new FormData()
    fd.append('file', importFile.value)
    fd.append('format', importFormat.value)
    fd.append('zone_name', importZoneName.value.trim())
    fd.append('kind', importKind.value)
    fd.append('dry_run', 'false')
    importPreview.value = await api.post<ImportPreview>('/zones/import', fd)
    importStep.value = 'done'
    await load()
  } catch (e) {
    importError.value = useApiError(e)
    importStep.value = 'upload'
  } finally {
    importLoading.value = false
  }
}

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100]

const totalPages = computed(() => Math.ceil(zonesStore.total / pageSize.value))

const sortedZones = computed(() => {
  const key = sortKey.value
  const dir = sortDir.value === 'asc' ? 1 : -1
  return [...zonesStore.zones].sort((a, b) => {
    const av = a[key] ?? ''
    const bv = b[key] ?? ''
    if (av < bv) return -dir
    if (av > bv) return dir
    return 0
  })
})

async function load() {
  page.value = Math.max(1, page.value)
  await zonesStore.fetchZones({ page: page.value, page_size: pageSize.value, search: search.value || undefined })
}

onMounted(load)
watch(page, load)
watch([search, pageSize], () => {
  page.value = 1
  load()
})

function sort(key: keyof Zone): void {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

function kindBadgeClass(kind: string): string {
  const map: Record<string, string> = {
    Native: 'bg-blue text-blue-fg',
    Master: 'bg-green text-green-fg',
    Slave: 'bg-yellow text-yellow-fg',
  }
  return `badge ${map[kind] ?? 'bg-secondary text-secondary-fg'}`
}

async function createZone() {
  creating.value = true
  try {
    const ns = form.value.nameservers.split(',').map((s) => s.trim()).filter(Boolean)
    const masters = form.value.masters.split(',').map((s) => s.trim()).filter(Boolean)
    await zonesStore.createZone({
      name: form.value.name,
      kind: form.value.kind,
      nameservers: ns,
      masters,
      account_id: form.value.accountId || null,
      template_id: form.value.templateId || null,
    })
    toast.success(`Zone ${form.value.name} created`)
    showCreateModal.value = false
    form.value = { name: '', kind: 'Master', nameservers: '', masters: '', accountId: '', templateId: '' }
    await load()
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    creating.value = false
  }
}

async function deleteZone(zone: Zone) {
  if (!confirm(`Delete zone ${zone.name}?`)) return
  try {
    await zonesStore.deleteZone(zone.id)
    toast.success(`Zone ${zone.name} deleted`)
  } catch (e) {
    toast.error(useApiError(e))
  }
}

// --- Edit Zone modal ---
const showEditModal = ref(false)
const editingZone = ref<Zone | null>(null)
const editForm = ref({ kind: 'Master' as 'Native' | 'Master' | 'Slave', masters: '', autoPtr: false })
const savingEdit = ref(false)
const loadingEditSettings = ref(false)

async function openEdit(zone: Zone): Promise<void> {
  editingZone.value = zone
  editForm.value = {
    kind: zone.kind as 'Native' | 'Master' | 'Slave',
    masters: '',
    autoPtr: false,
  }
  showEditModal.value = true
  loadingEditSettings.value = true
  try {
    const data = await api.get<{ zone_name: string; auto_ptr: boolean }>(`/zones/${zone.id}/settings`)
    editForm.value.autoPtr = data.auto_ptr
  } catch {
    editForm.value.autoPtr = false
  } finally {
    loadingEditSettings.value = false
  }
}

async function saveEdit(): Promise<void> {
  if (!editingZone.value) return
  savingEdit.value = true
  try {
    const masters = editForm.value.kind === 'Slave'
      ? editForm.value.masters.split(',').map(s => s.trim()).filter(Boolean)
      : []
    await Promise.all([
      api.put(`/zones/${editingZone.value.id}`, { kind: editForm.value.kind, masters }),
      api.put(`/zones/${editingZone.value.id}/settings`, { auto_ptr: editForm.value.autoPtr }),
    ])
    toast.success('Zone saved')
    showEditModal.value = false
    await load()
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    savingEdit.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header d-print-none">
      <div class="container-xl">
        <div class="row g-2 align-items-center">
          <div class="col">
            <div class="page-pretitle">DNS Management</div>
            <h2 class="page-title">Zones</h2>
          </div>
          <div class="col-auto ms-auto d-print-none">
            <div class="btn-list">
              <button
                v-if="auth.isAdmin"
                class="btn btn-secondary d-inline-flex align-items-center gap-1"
                @click="openImport"
              >
                <IconUpload :size="16" />
                Import
              </button>
              <button
                v-if="auth.isAdmin"
                class="btn btn-primary d-inline-flex align-items-center gap-1"
                @click="showCreateModal = true; loadAccounts(); loadTemplates()"
              >
                <IconPlus :size="16" />
                Create zone
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">
        <div class="card">
          <div class="card-header gap-2">
            <div class="input-group" style="max-width: 320px;">
              <span class="input-group-text">
                <IconSearch :size="16" />
              </span>
              <input
                v-model="search"
                type="search"
                placeholder="Search zones…"
                class="form-control"
              />
            </div>
            <div class="ms-auto d-flex align-items-center gap-2">
              <span class="text-muted small">Rows:</span>
              <select v-model="pageSize" class="form-select form-select-sm" style="width: auto;">
                <option v-for="n in PAGE_SIZE_OPTIONS" :key="n" :value="n">{{ n }}</option>
              </select>
            </div>
          </div>

          <div class="table-responsive">
            <table class="table table-vcenter card-table table-hover">
              <thead>
                <tr>
                  <th style="cursor:pointer;" @click="sort('name')">
                    <div class="d-flex align-items-center gap-1">
                      Zone
                      <IconChevronUp v-if="sortKey === 'name' && sortDir === 'asc'" :size="12" />
                      <IconChevronDown v-else-if="sortKey === 'name' && sortDir === 'desc'" :size="12" />
                      <span v-else class="opacity-0"><IconChevronUp :size="12" /></span>
                    </div>
                  </th>
                  <th style="cursor:pointer;" @click="sort('kind')">
                    <div class="d-flex align-items-center gap-1">
                      Type
                      <IconChevronUp v-if="sortKey === 'kind' && sortDir === 'asc'" :size="12" />
                      <IconChevronDown v-else-if="sortKey === 'kind' && sortDir === 'desc'" :size="12" />
                      <span v-else class="opacity-0"><IconChevronUp :size="12" /></span>
                    </div>
                  </th>
                  <th style="cursor:pointer;" @click="sort('serial')">
                    <div class="d-flex align-items-center gap-1">
                      Serial
                      <IconChevronUp v-if="sortKey === 'serial' && sortDir === 'asc'" :size="12" />
                      <IconChevronDown v-else-if="sortKey === 'serial' && sortDir === 'desc'" :size="12" />
                      <span v-else class="opacity-0"><IconChevronUp :size="12" /></span>
                    </div>
                  </th>
                  <th style="cursor:pointer;" @click="sort('dnssec')">
                    <div class="d-flex align-items-center gap-1">
                      DNSSEC
                      <IconChevronUp v-if="sortKey === 'dnssec' && sortDir === 'asc'" :size="12" />
                      <IconChevronDown v-else-if="sortKey === 'dnssec' && sortDir === 'desc'" :size="12" />
                      <span v-else class="opacity-0"><IconChevronUp :size="12" /></span>
                    </div>
                  </th>
                  <th class="w-1" />
                </tr>
              </thead>
              <tbody>
                <tr v-if="zonesStore.loading">
                  <td colspan="5" class="text-center py-4">
                    <div class="spinner-border text-primary" />
                  </td>
                </tr>
                <tr v-else-if="sortedZones.length === 0">
                  <td colspan="5" class="text-center text-muted py-4">No zones found.</td>
                </tr>
                <template v-else>
                  <tr
                    v-for="zone in sortedZones"
                    :key="zone.id"
                    style="cursor: pointer"
                    @click="router.push(`/zones/${zone.id}`)"
                  >
                    <td>
                      <div class="d-flex align-items-center gap-2">
                        <IconChevronRight :size="14" class="text-muted flex-shrink-0" />
                        <code class="font-monospace">{{ zone.name }}</code>
                      </div>
                    </td>
                    <td><span :class="kindBadgeClass(zone.kind)">{{ zone.kind }}</span></td>
                    <td class="text-muted font-monospace">{{ zone.serial ?? '–' }}</td>
                    <td>
                      <span :class="['badge d-inline-flex align-items-center gap-1', zone.dnssec ? 'bg-green text-green-fg' : 'bg-secondary text-secondary-fg']">
                        <IconShieldCheck v-if="zone.dnssec" :size="12" />
                        <IconShieldOff v-else :size="12" />
                        {{ zone.dnssec ? 'Active' : 'Inactive' }}
                      </span>
                    </td>
                    <td @click.stop>
                      <div class="d-flex align-items-center gap-1">
                        <button
                          v-if="auth.isAdmin"
                          class="btn btn-ghost-secondary btn-icon btn-sm"
                          title="Edit zone"
                          @click="openEdit(zone)"
                        >
                          <IconEdit :size="16" />
                        </button>
                        <button
                          v-if="auth.isAdmin"
                          class="btn btn-ghost-secondary btn-icon btn-sm text-danger"
                          title="Delete zone"
                          @click="deleteZone(zone)"
                        >
                          <IconTrash :size="16" />
                        </button>
                      </div>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div v-if="zonesStore.total > 0" class="card-footer d-flex align-items-center">
            <p class="m-0 text-muted small">
              Showing
              {{ (page - 1) * pageSize + 1 }}–{{ Math.min(page * pageSize, zonesStore.total) }}
              of {{ zonesStore.total }} zones
            </p>
            <ul class="pagination m-0 ms-auto">
              <li class="page-item" :class="{ disabled: page <= 1 }">
                <button class="page-link" @click="page--">
                  <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M15 6l-6 6l6 6" /></svg>
                  prev
                </button>
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
                <button class="page-link" @click="page++">
                  next
                  <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M9 6l6 6l-6 6" /></svg>
                </button>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <!-- ── Import modal ── -->
      <template v-if="showImportModal">
        <div class="modal modal-blur fade show" style="display:block;" tabindex="-1" @click.self="showImportModal = false">
          <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">Import zone</h5>
                <button type="button" class="btn-close" @click="showImportModal = false" />
              </div>
              <div class="modal-body">

                <!-- Step indicator -->
                <ul class="steps steps-counter mb-4">
                  <li class="step-item" :class="{ active: importStep === 'upload', complete: importStep !== 'upload' }">Upload</li>
                  <li class="step-item" :class="{ active: importStep === 'preview', complete: importStep === 'done' }">Preview</li>
                  <li class="step-item" :class="{ active: importStep === 'done' }">Done</li>
                </ul>

                <!-- Step 1: Upload -->
                <template v-if="importStep === 'upload'">
                  <div class="mb-3">
                    <label class="form-label">Format</label>
                    <div class="btn-group w-100">
                      <button
                        type="button"
                        class="btn"
                        :class="importFormat === 'bind' ? 'btn-primary' : 'btn-outline-secondary'"
                        @click="importFormat = 'bind'"
                      >BIND zone file</button>
                      <button
                        type="button"
                        class="btn"
                        :class="importFormat === 'csv' ? 'btn-primary' : 'btn-outline-secondary'"
                        @click="importFormat = 'csv'"
                      >CSV</button>
                    </div>
                  </div>

                  <div class="mb-3">
                    <label class="form-label">Zone type</label>
                    <select v-model="importKind" class="form-select">
                      <option>Native</option>
                      <option>Master</option>
                      <option>Slave</option>
                    </select>
                  </div>

                  <div v-if="importFormat === 'csv'" class="mb-3">
                    <label class="form-label">Zone name <span class="text-danger">*</span></label>
                    <input v-model="importZoneName" placeholder="example.com." class="form-control font-monospace" />
                    <div class="form-text">Required for CSV — zone name is not embedded in the file.</div>
                  </div>
                  <div v-else class="mb-3">
                    <label class="form-label">Zone name hint <span class="text-muted">(optional)</span></label>
                    <input v-model="importZoneName" placeholder="example.com." class="form-control font-monospace" />
                    <div class="form-text">Only needed if the zone file has no <code>$ORIGIN</code> directive.</div>
                  </div>

                  <div class="mb-3">
                    <label class="form-label">File</label>
                    <input
                      ref="importFileInput"
                      type="file"
                      class="form-control"
                      :accept="importFormat === 'csv' ? '.csv,text/csv' : '.zone,.txt,text/plain'"
                      @change="onFileChange"
                    />
                    <div v-if="importFormat === 'csv'" class="form-text">
                      Expected columns: <code>name, type, ttl, content</code>
                    </div>
                  </div>

                  <div v-if="importError" class="alert alert-danger py-2">{{ importError }}</div>
                </template>

                <!-- Step 2: Preview -->
                <template v-else-if="importStep === 'preview' && importPreview">
                  <div class="d-flex flex-wrap gap-3 mb-3">
                    <div class="card flex-fill text-center p-3">
                      <div class="h3 mb-0">{{ importPreview.rrset_count }}</div>
                      <div class="text-muted small">RRsets</div>
                    </div>
                    <div class="card flex-fill text-center p-3">
                      <div class="h3 mb-0">{{ importPreview.record_count }}</div>
                      <div class="text-muted small">Records</div>
                    </div>
                    <div class="card flex-fill text-center p-3">
                      <div class="h3 mb-0 font-monospace small">{{ importPreview.zone_name }}</div>
                      <div class="text-muted small">Zone</div>
                    </div>
                  </div>

                  <div v-if="importPreview.already_exists" class="alert alert-warning d-flex align-items-center gap-2 py-2">
                    <IconAlertTriangle :size="18" class="flex-shrink-0" />
                    Zone <strong>{{ importPreview.zone_name }}</strong> already exists — records will be replaced.
                  </div>

                  <div v-if="importPreview.errors.length" class="alert alert-warning py-2 mb-3">
                    <strong>Parse warnings ({{ importPreview.errors.length }}):</strong>
                    <ul class="mb-0 mt-1 ps-3">
                      <li v-for="(err, i) in importPreview.errors" :key="i" class="small">{{ err }}</li>
                    </ul>
                  </div>

                  <div class="table-responsive" style="max-height: 320px; overflow-y: auto;">
                    <table class="table table-vcenter table-sm card-table mb-0">
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Type</th>
                          <th>TTL</th>
                          <th>Records</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="(rs, i) in importPreview.preview" :key="i">
                          <td class="font-monospace small text-truncate" style="max-width:260px;" :title="rs.name">{{ rs.name }}</td>
                          <td><span class="badge bg-secondary text-secondary-fg">{{ rs.type }}</span></td>
                          <td class="text-muted">{{ rs.ttl }}</td>
                          <td class="text-muted">{{ rs.record_count }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div v-if="importError" class="alert alert-danger mt-3 py-2">{{ importError }}</div>
                </template>

                <!-- Step 3: Done -->
                <template v-else-if="importStep === 'done' && importPreview">
                  <div class="text-center py-4">
                    <IconCircleCheck :size="48" class="text-success mb-3" />
                    <h4>Import successful</h4>
                    <p class="text-muted">
                      Imported <strong>{{ importPreview.record_count }} records</strong>
                      in <strong>{{ importPreview.rrset_count }} RRsets</strong>
                      into zone <code>{{ importPreview.zone_name }}</code>.
                    </p>
                  </div>
                </template>

              </div>
              <div class="modal-footer">
                <button class="btn btn-secondary" @click="showImportModal = false">
                  {{ importStep === 'done' ? 'Close' : 'Cancel' }}
                </button>
                <button
                  v-if="importStep === 'upload'"
                  class="btn btn-primary d-inline-flex align-items-center gap-1"
                  :disabled="importLoading || !importFile"
                  @click="runPreview"
                >
                  <span v-if="importLoading" class="spinner-border spinner-border-sm" style="width:.9em;height:.9em;" />
                  Preview
                </button>
                <button
                  v-else-if="importStep === 'preview'"
                  class="btn btn-secondary me-auto"
                  @click="importStep = 'upload'"
                >Back</button>
                <button
                  v-if="importStep === 'preview'"
                  class="btn btn-primary d-inline-flex align-items-center gap-1"
                  :disabled="importLoading"
                  @click="confirmImport"
                >
                  <span v-if="importLoading" class="spinner-border spinner-border-sm" style="width:.9em;height:.9em;" />
                  {{ importPreview?.already_exists ? 'Overwrite &amp; Import' : 'Import' }}
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-backdrop fade show" @click="showImportModal = false" />
      </template>

      <!-- ── Create modal ── -->
      <template v-if="showCreateModal">
        <div
          class="modal modal-blur fade show"
          style="display: block;"
          tabindex="-1"
          role="dialog"
          @click.self="showCreateModal = false"
        >
          <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">Create zone</h5>
                <button type="button" class="btn-close" @click="showCreateModal = false" />
              </div>
              <div class="modal-body">
                <div class="mb-3">
                  <label class="form-label">Zone name</label>
                  <input v-model="form.name" required placeholder="example.com." class="form-control" />
                </div>
                <div class="mb-3">
                  <label class="form-label">Type</label>
                  <select v-model="form.kind" class="form-select">
                    <option>Native</option>
                    <option>Master</option>
                    <option>Slave</option>
                  </select>
                </div>
                <div class="mb-3">
                  <label class="form-label">Account <span class="text-muted">(optional)</span></label>
                  <select v-model="form.accountId" class="form-select">
                    <option value="">— No account —</option>
                    <option v-for="acc in accounts" :key="acc.id" :value="acc.id">{{ acc.name }}</option>
                  </select>
                  <div class="form-text">Assign this zone to an account for group-based access control.</div>
                </div>
                <div v-if="templates.length > 0" class="mb-3">
                  <label class="form-label">Template <span class="text-muted">(optional)</span></label>
                  <select v-model="form.templateId" class="form-select">
                    <option value="">— No template —</option>
                    <option v-for="tpl in templates" :key="tpl.id" :value="tpl.id">
                      {{ tpl.name }}{{ tpl.description ? ` — ${tpl.description}` : '' }}
                    </option>
                  </select>
                  <div class="form-text">Apply a record template after zone creation.</div>
                </div>
                <div class="mb-3">
                  <label class="form-label">Nameservers (comma-separated)</label>
                  <input v-model="form.nameservers" placeholder="ns1.example.com, ns2.example.com" class="form-control" />
                </div>
                <div v-if="form.kind === 'Slave'" class="mb-3">
                  <label class="form-label">Master IPs (comma-separated)</label>
                  <input v-model="form.masters" placeholder="1.2.3.4" class="form-control" />
                </div>
              </div>
              <div class="modal-footer">
                <button class="btn btn-secondary" @click="showCreateModal = false">Cancel</button>
                <button
                  class="btn btn-primary d-inline-flex align-items-center gap-1"
                  :disabled="creating"
                  @click="createZone"
                >
                  <span v-if="creating" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                  Create
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-backdrop fade show" @click="showCreateModal = false" />
      </template>

      <!-- ── Edit Zone modal ── -->
      <template v-if="showEditModal && editingZone">
        <div class="modal modal-blur fade show" style="display:block;" tabindex="-1" role="dialog" @click.self="showEditModal = false">
          <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title d-flex align-items-center gap-2">
                  <IconEdit :size="18" />
                  Edit zone — <code class="font-monospace">{{ editingZone.name }}</code>
                </h5>
                <button type="button" class="btn-close" @click="showEditModal = false" />
              </div>
              <div class="modal-body">
                <div class="mb-3">
                  <label class="form-label">Zone type</label>
                  <select v-model="editForm.kind" class="form-select">
                    <option value="Master">Master (Primary)</option>
                    <option value="Slave">Slave (Secondary)</option>
                    <option value="Native">Native</option>
                  </select>
                </div>
                <div v-if="editForm.kind === 'Slave'" class="mb-3">
                  <label class="form-label">Master servers <span class="text-muted small">(comma-separated IPs)</span></label>
                  <input v-model="editForm.masters" class="form-control font-monospace" placeholder="192.0.2.1, 192.0.2.2" />
                </div>
                <hr class="my-3" />
                <div v-if="loadingEditSettings" class="text-center py-2">
                  <div class="spinner-border spinner-border-sm text-primary" />
                </div>
                <label v-else class="form-check form-switch">
                  <input v-model="editForm.autoPtr" class="form-check-input" type="checkbox" />
                  <span class="form-check-label">
                    <strong>Auto-create reverse PTR records</strong>
                    <span class="text-muted d-block small">
                      When A/AAAA records change, FloriDNS automatically creates, updates, or deletes
                      the matching PTR record in any existing <code>in-addr.arpa</code> / <code>ip6.arpa</code> zone.
                    </span>
                  </span>
                </label>
              </div>
              <div class="modal-footer">
                <button class="btn btn-secondary" @click="showEditModal = false">Cancel</button>
                <button
                  class="btn btn-primary d-inline-flex align-items-center gap-1"
                  :disabled="savingEdit"
                  @click="saveEdit"
                >
                  <span v-if="savingEdit" class="spinner-border spinner-border-sm" style="width:.9em;height:.9em;" />
                  Save
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-backdrop fade show" @click="showEditModal = false" />
      </template>
    </Teleport>
  </div>
</template>

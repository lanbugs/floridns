<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  IconPlus, IconTrash, IconEdit, IconChevronDown, IconChevronUp,
} from '@tabler/icons-vue'
import { api, useApiError } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import type { ZoneTemplate } from '@/types'

const toast = useToast()

const templates = ref<ZoneTemplate[]>([])
const loading = ref(false)

// ── Modal state ──────────────────────────────────────────────────────────────

type ModalMode = 'create' | 'edit'
const showModal = ref(false)
const modalMode = ref<ModalMode>('create')
const editingId = ref<string | null>(null)
const saving = ref(false)

interface RecordDraft {
  name: string
  type: string
  ttl: number
  content: string
}

const form = ref<{ name: string; description: string; records: RecordDraft[] }>({
  name: '',
  description: '',
  records: [],
})

const RECORD_TYPES = ['A', 'AAAA', 'CNAME', 'MX', 'NS', 'TXT', 'SRV', 'CAA', 'TLSA', 'PTR', 'ALIAS', 'NAPTR']

// ── Expanded rows ─────────────────────────────────────────────────────────────

const expandedId = ref<string | null>(null)
function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

// ── Load ──────────────────────────────────────────────────────────────────────

async function load() {
  loading.value = true
  try {
    templates.value = await api.get<ZoneTemplate[]>('/templates')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ── Modal helpers ─────────────────────────────────────────────────────────────

function openCreate() {
  modalMode.value = 'create'
  editingId.value = null
  form.value = { name: '', description: '', records: [] }
  showModal.value = true
}

function openEdit(t: ZoneTemplate) {
  modalMode.value = 'edit'
  editingId.value = t.id
  form.value = {
    name: t.name,
    description: t.description ?? '',
    records: t.records.map((r) => ({ name: r.name, type: r.type, ttl: r.ttl, content: r.content })),
  }
  showModal.value = true
}

function addRecord() {
  form.value.records.push({ name: '@', type: 'A', ttl: 3600, content: '' })
}

function removeRecord(idx: number) {
  form.value.records.splice(idx, 1)
}

async function saveTemplate() {
  if (!form.value.name.trim()) return
  saving.value = true
  try {
    const payload = {
      name: form.value.name.trim(),
      description: form.value.description.trim() || null,
      records: form.value.records.filter((r) => r.name && r.type && r.content),
    }
    if (modalMode.value === 'create') {
      const created = await api.post<ZoneTemplate>('/templates', payload)
      templates.value.push(created)
      toast.success(`Template "${created.name}" created`)
    } else {
      const updated = await api.put<ZoneTemplate>(`/templates/${editingId.value}`, payload)
      const idx = templates.value.findIndex((t) => t.id === editingId.value)
      if (idx !== -1) templates.value[idx] = updated
      toast.success(`Template "${updated.name}" saved`)
    }
    showModal.value = false
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    saving.value = false
  }
}

async function deleteTemplate(t: ZoneTemplate) {
  if (!confirm(`Delete template "${t.name}"? This cannot be undone.`)) return
  try {
    await api.delete(`/templates/${t.id}`)
    templates.value = templates.value.filter((x) => x.id !== t.id)
    if (expandedId.value === t.id) expandedId.value = null
    toast.success(`Template "${t.name}" deleted`)
  } catch (e) {
    toast.error(useApiError(e))
  }
}

const validRecordCount = computed(() =>
  form.value.records.filter((r) => r.name && r.type && r.content).length
)
</script>

<template>
  <div>
    <div class="page-header d-print-none">
      <div class="container-xl">
        <div class="row g-2 align-items-center">
          <div class="col">
            <div class="page-pretitle">Administration</div>
            <h2 class="page-title">Zone Templates</h2>
          </div>
          <div class="col-auto ms-auto d-print-none">
            <button class="btn btn-primary d-inline-flex align-items-center gap-1" @click="openCreate">
              <IconPlus :size="16" />
              New template
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">
        <div v-if="loading" class="text-center py-5">
          <div class="spinner-border text-primary" />
        </div>

        <div v-else-if="templates.length === 0" class="card">
          <div class="card-body text-center text-muted py-5">
            No templates yet. Create one to speed up zone provisioning.
          </div>
        </div>

        <div v-else class="card">
          <div class="table-responsive">
            <table class="table table-vcenter card-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Description</th>
                  <th>Records</th>
                  <th class="w-1" />
                </tr>
              </thead>
              <tbody>
                <template v-for="t in templates" :key="t.id">
                  <tr
                    style="cursor:pointer;"
                    @click="toggleExpand(t.id)"
                  >
                    <td class="fw-medium">{{ t.name }}</td>
                    <td class="text-muted">{{ t.description ?? '–' }}</td>
                    <td>
                      <span class="badge bg-secondary text-secondary-fg">{{ t.records.length }} record{{ t.records.length !== 1 ? 's' : '' }}</span>
                    </td>
                    <td @click.stop>
                      <div class="d-flex align-items-center gap-1">
                        <button class="btn btn-ghost-secondary btn-icon btn-sm" title="Edit" @click="openEdit(t)">
                          <IconEdit :size="16" />
                        </button>
                        <button class="btn btn-ghost-secondary btn-icon btn-sm text-danger" title="Delete" @click="deleteTemplate(t)">
                          <IconTrash :size="16" />
                        </button>
                        <button class="btn btn-ghost-secondary btn-icon btn-sm" @click="toggleExpand(t.id)">
                          <IconChevronUp v-if="expandedId === t.id" :size="16" />
                          <IconChevronDown v-else :size="16" />
                        </button>
                      </div>
                    </td>
                  </tr>
                  <!-- Expanded record list -->
                  <tr v-if="expandedId === t.id">
                    <td colspan="4" class="p-0">
                      <div class="bg-light border-top border-bottom px-3 py-2">
                        <div v-if="t.records.length === 0" class="text-muted small py-2">
                          No records defined in this template.
                        </div>
                        <table v-else class="table table-sm table-vcenter mb-0">
                          <thead>
                            <tr>
                              <th class="text-muted fw-normal small">Name</th>
                              <th class="text-muted fw-normal small">Type</th>
                              <th class="text-muted fw-normal small">TTL</th>
                              <th class="text-muted fw-normal small">Content</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="r in t.records" :key="r.id">
                              <td class="font-monospace small">{{ r.name }}</td>
                              <td><span class="badge bg-secondary text-secondary-fg">{{ r.type }}</span></td>
                              <td class="text-muted small">{{ r.ttl }}</td>
                              <td class="font-monospace small text-truncate" style="max-width:360px;" :title="r.content">{{ r.content }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Create / Edit modal ── -->
    <Teleport to="body">
      <template v-if="showModal">
        <div class="modal modal-blur fade show" style="display:block;" tabindex="-1" @click.self="showModal = false">
          <div class="modal-dialog modal-xl modal-dialog-centered modal-dialog-scrollable">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">{{ modalMode === 'create' ? 'New template' : 'Edit template' }}</h5>
                <button type="button" class="btn-close" @click="showModal = false" />
              </div>
              <div class="modal-body">

                <div class="row g-3 mb-4">
                  <div class="col-sm-6">
                    <label class="form-label">Name <span class="text-danger">*</span></label>
                    <input v-model="form.name" class="form-control" placeholder="e.g. Standard web zone" />
                  </div>
                  <div class="col-sm-6">
                    <label class="form-label">Description</label>
                    <input v-model="form.description" class="form-control" placeholder="Optional description" />
                  </div>
                </div>

                <div class="d-flex align-items-center justify-content-between mb-2">
                  <h4 class="mb-0">Records <span class="text-muted small fw-normal">({{ validRecordCount }} valid)</span></h4>
                  <button class="btn btn-secondary btn-sm d-inline-flex align-items-center gap-1" @click="addRecord">
                    <IconPlus :size="14" />
                    Add record
                  </button>
                </div>

                <div class="form-text mb-3">
                  Use <code>@</code> as the zone apex. Use <code>{zone}</code> in content as a placeholder for the zone name (e.g. <code>10 mail.{zone}</code>).
                </div>

                <div v-if="form.records.length === 0" class="text-muted text-center py-3 border rounded">
                  No records yet — click "Add record" to start.
                </div>

                <div v-else class="table-responsive">
                  <table class="table table-vcenter table-sm mb-0">
                    <thead>
                      <tr>
                        <th style="width:160px;">Name</th>
                        <th style="width:110px;">Type</th>
                        <th style="width:90px;">TTL</th>
                        <th>Content</th>
                        <th class="w-1" />
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(rec, idx) in form.records" :key="idx">
                        <td>
                          <input v-model="rec.name" class="form-control form-control-sm font-monospace" placeholder="@" />
                        </td>
                        <td>
                          <select v-model="rec.type" class="form-select form-select-sm">
                            <option v-for="t in RECORD_TYPES" :key="t">{{ t }}</option>
                          </select>
                        </td>
                        <td>
                          <input v-model.number="rec.ttl" type="number" min="60" class="form-control form-control-sm" />
                        </td>
                        <td>
                          <input v-model="rec.content" class="form-control form-control-sm font-monospace" placeholder="record content" />
                        </td>
                        <td>
                          <button class="btn btn-ghost-secondary btn-icon btn-sm text-danger" @click="removeRecord(idx)">
                            <IconTrash :size="14" />
                          </button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

              </div>
              <div class="modal-footer">
                <button class="btn btn-secondary" @click="showModal = false">Cancel</button>
                <button
                  class="btn btn-primary d-inline-flex align-items-center gap-1"
                  :disabled="saving || !form.name.trim()"
                  @click="saveTemplate"
                >
                  <span v-if="saving" class="spinner-border spinner-border-sm" style="width:.9em;height:.9em;" />
                  {{ modalMode === 'create' ? 'Create' : 'Save' }}
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-backdrop fade show" @click="showModal = false" />
      </template>
    </Teleport>
  </div>
</template>

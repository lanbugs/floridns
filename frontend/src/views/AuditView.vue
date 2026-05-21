<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { IconDownload, IconChevronDown, IconChevronRight } from '@tabler/icons-vue'
import { api, useApiError } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import type { AuditLog, PaginatedResponse } from '@/types'

const toast = useToast()
const logs = ref<AuditLog[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const filterAction = ref('')
const filterUser = ref('')
const expanded = ref<Set<string>>(new Set())

async function load() {
  loading.value = true
  expanded.value.clear()
  try {
    const query = new URLSearchParams({ page: String(page.value), page_size: '50' })
    if (filterAction.value) query.set('action', filterAction.value)
    if (filterUser.value) query.set('username', filterUser.value)
    const result = await api.get<PaginatedResponse<AuditLog>>(`/audit?${query}`)
    logs.value = result.items
    total.value = result.total
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    loading.value = false
  }
}

onMounted(load)

function toggleRow(id: string) {
  if (expanded.value.has(id)) {
    expanded.value.delete(id)
  } else {
    expanded.value.add(id)
  }
}

function hasDetails(log: AuditLog) {
  return log.before_value != null || log.after_value != null || log.comment != null
}

function parseJson(val: string | null): unknown {
  if (!val) return null
  try { return JSON.parse(val) } catch { return val }
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('de-DE', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function openExport(path: string) {
  window.open(path, '_blank')
}

// Render "records.patch" operations in a human-readable way
function renderRecordOps(after: unknown): string | null {
  if (!after || typeof after !== 'object') return null
  const a = after as Record<string, unknown>
  if (!Array.isArray(a.operations)) return null
  return (a.operations as Array<Record<string, unknown>>)
    .map((op) => {
      if (op.op === 'delete') return `DELETE  ${op.name}  ${op.type}`
      const records = (op.records as string[] | undefined)?.join(', ') ?? ''
      const comment = op.comment ? `  # ${op.comment}` : ''
      return `REPLACE  ${op.name}  ${op.type}  TTL ${op.ttl}\n         ${records}${comment}`
    })
    .join('\n')
}

</script>

<template>
  <div>
    <div class="page-header d-print-none">
      <div class="container-xl">
        <div class="row g-2 align-items-center">
          <div class="col">
            <div class="page-pretitle">Monitoring</div>
            <h2 class="page-title">Audit Log</h2>
          </div>
          <div class="col-auto ms-auto d-print-none">
            <div class="btn-list">
              <button class="btn btn-secondary d-inline-flex align-items-center gap-1" @click="openExport('/api/v1/audit/export/csv')">
                <IconDownload :size="16" /> CSV
              </button>
              <button class="btn btn-secondary d-inline-flex align-items-center gap-1" @click="openExport('/api/v1/audit/export/json')">
                <IconDownload :size="16" /> JSON
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">
        <div class="card">
          <div class="card-header">
            <div class="d-flex gap-2 flex-wrap">
              <input
                v-model="filterAction"
                placeholder="Filter by action…"
                class="form-control"
                style="max-width: 220px"
                @keyup.enter="load"
              />
              <input
                v-model="filterUser"
                placeholder="Filter by user…"
                class="form-control"
                style="max-width: 220px"
                @keyup.enter="load"
              />
              <button class="btn btn-secondary" @click="load">Search</button>
            </div>
          </div>

          <div class="table-responsive">
            <table class="table table-vcenter card-table">
              <thead>
                <tr>
                  <th style="width: 1.5rem;"></th>
                  <th>Time</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>Resource</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="loading">
                  <td colspan="6" class="text-center py-4">
                    <div class="spinner-border text-primary" />
                  </td>
                </tr>
                <tr v-else-if="logs.length === 0">
                  <td colspan="6" class="text-center text-muted py-4">No audit log entries.</td>
                </tr>
                <template v-else>
                  <template v-for="log in logs" :key="log.id">
                    <tr
                      :class="{ 'cursor-pointer': hasDetails(log) }"
                      @click="hasDetails(log) && toggleRow(log.id)"
                    >
                      <td class="text-muted" style="width:1.5rem;">
                        <template v-if="hasDetails(log)">
                          <IconChevronDown v-if="expanded.has(log.id)" :size="16" />
                          <IconChevronRight v-else :size="16" />
                        </template>
                      </td>
                      <td class="text-muted font-monospace text-nowrap" style="font-size: 0.8125rem">
                        {{ formatDate(log.timestamp) }}
                      </td>
                      <td>{{ log.username }}</td>
                      <td class="font-monospace text-primary">{{ log.action }}</td>
                      <td class="text-muted">
                        {{ log.resource_id ?? '–' }}
                        <span v-if="log.comment" class="ms-2 text-muted fst-italic" style="font-size:0.8em;">
                          "{{ log.comment }}"
                        </span>
                      </td>
                      <td class="font-monospace text-muted" style="font-size: 0.8125rem">{{ log.ip_address }}</td>
                    </tr>
                    <tr v-if="expanded.has(log.id)" class="bg-light">
                      <td colspan="6" class="px-4 py-3">
                        <div class="row g-3">
                          <div v-if="log.before_value" class="col-12 col-md-6">
                            <div class="text-muted small fw-medium mb-1">Before</div>
                            <pre class="bg-white text-dark border rounded p-2 mb-0 overflow-auto" style="font-size:0.8rem;max-height:20rem;">{{ JSON.stringify(parseJson(log.before_value), null, 2) }}</pre>
                          </div>
                          <div v-if="log.after_value" class="col-12 col-md-6">
                            <div class="text-muted small fw-medium mb-1">After</div>
                            <pre
                              v-if="renderRecordOps(parseJson(log.after_value))"
                              class="bg-white text-dark border rounded p-2 mb-0 overflow-auto"
                              style="font-size:0.8rem;max-height:20rem;"
                            >{{ renderRecordOps(parseJson(log.after_value)) }}</pre>
                            <pre v-else class="bg-white text-dark border rounded p-2 mb-0 overflow-auto" style="font-size:0.8rem;max-height:20rem;">{{ JSON.stringify(parseJson(log.after_value), null, 2) }}</pre>
                          </div>
                          <div v-if="!log.before_value && !log.after_value && log.comment" class="col-12">
                            <span class="text-muted fst-italic">"{{ log.comment }}"</span>
                          </div>
                        </div>
                      </td>
                    </tr>
                  </template>
                </template>
              </tbody>
            </table>
          </div>

          <div v-if="total > 50" class="card-footer d-flex justify-content-center gap-2">
            <button class="btn btn-secondary btn-sm" :disabled="page === 1" @click="page--; load()">Previous</button>
            <span class="d-flex align-items-center px-2 text-muted">Page {{ page }}</span>
            <button class="btn btn-secondary btn-sm" :disabled="page * 50 >= total" @click="page++; load()">Next</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cursor-pointer {
  cursor: pointer;
}
tr.cursor-pointer:hover td {
  background-color: var(--tblr-light);
}
</style>

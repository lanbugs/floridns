<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { IconChevronLeft, IconRestore, IconEye } from '@tabler/icons-vue'
import { useToast } from '@/composables/useToast'
import { useApiError, api } from '@/composables/useApi'

const props = defineProps<{ id: string }>()
const router = useRouter()
const toast = useToast()

interface HistoryEntry {
  id: string
  zone_name: string
  action: string
  username: string
  created_at: string
  record_count_before: number
  record_count_after: number
}

interface PaginatedHistory {
  total: number
  page: number
  page_size: number
  items: HistoryEntry[]
}

interface Snapshot {
  before: Record<string, unknown>[]
  after: Record<string, unknown>[]
}

const history = ref<PaginatedHistory>({ total: 0, page: 1, page_size: 25, items: [] })
const loading = ref(false)
const page = ref(1)

const snapshotEntry = ref<HistoryEntry | null>(null)
const snapshot = ref<Snapshot | null>(null)
const loadingSnapshot = ref(false)
const showSnapshotTab = ref<'before' | 'after'>('after')

const restoringId = ref<string | null>(null)

async function fetchHistory(): Promise<void> {
  loading.value = true
  try {
    history.value = await api.get<PaginatedHistory>(
      `/zones/${props.id}/history?page=${page.value}&page_size=25`,
    )
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    loading.value = false
  }
}

async function goToPage(p: number): Promise<void> {
  page.value = p
  await fetchHistory()
}

async function openSnapshot(entry: HistoryEntry): Promise<void> {
  snapshotEntry.value = entry
  loadingSnapshot.value = true
  showSnapshotTab.value = 'after'
  try {
    snapshot.value = await api.get<Snapshot>(`/zones/${props.id}/history/${entry.id}/snapshot`)
  } catch (e) {
    toast.error(useApiError(e))
    snapshotEntry.value = null
  } finally {
    loadingSnapshot.value = false
  }
}

function closeSnapshot(): void {
  snapshotEntry.value = null
  snapshot.value = null
}

async function restore(entry: HistoryEntry): Promise<void> {
  if (!confirm(`Restore zone to state before "${entry.action}" by ${entry.username}?\n\nThis will overwrite all current records (except SOA).`)) return
  restoringId.value = entry.id
  try {
    await api.post(`/zones/${props.id}/history/${entry.id}/restore`, {})
    toast.success('Zone restored to previous state')
    await fetchHistory()
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    restoringId.value = null
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

function actionLabel(action: string): string {
  const map: Record<string, string> = {
    'records.patch': 'Records changed',
    'zone.restore': 'Zone restored',
  }
  return map[action] ?? action
}

function badgeClass(action: string): string {
  if (action === 'zone.restore') return 'bg-purple text-purple-fg'
  return 'bg-blue text-blue-fg'
}

onMounted(fetchHistory)
</script>

<template>
  <div>
    <div class="page-header d-print-none">
      <div class="container-xl">
        <div class="row g-2 align-items-center">
          <div class="col-auto">
            <button
              class="btn btn-ghost-secondary btn-sm d-inline-flex align-items-center gap-1"
              @click="router.push(`/zones/${props.id}`)"
            >
              <IconChevronLeft :size="16" />
              Back
            </button>
          </div>
          <div class="col">
            <div class="page-pretitle">DNS Management</div>
            <h2 class="page-title font-monospace">{{ props.id }} — History</h2>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Change history</h3>
            <div class="card-options text-muted small">{{ history.total }} entries</div>
          </div>
          <div class="table-responsive">
            <table class="table table-vcenter card-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Action</th>
                  <th>User</th>
                  <th>Records before</th>
                  <th>Records after</th>
                  <th class="w-1" />
                </tr>
              </thead>
              <tbody>
                <tr v-if="loading">
                  <td colspan="6" class="text-center py-4">
                    <div class="spinner-border text-primary" />
                  </td>
                </tr>
                <tr v-else-if="history.items.length === 0">
                  <td colspan="6" class="text-center text-muted py-4">
                    No history entries yet. Enable zone history in Settings to start capturing changes.
                  </td>
                </tr>
                <tr v-for="entry in history.items" :key="entry.id">
                  <td class="text-muted small font-monospace">{{ formatDate(entry.created_at) }}</td>
                  <td>
                    <span :class="['badge', badgeClass(entry.action)]">{{ actionLabel(entry.action) }}</span>
                  </td>
                  <td>{{ entry.username }}</td>
                  <td class="text-muted">{{ entry.record_count_before }}</td>
                  <td class="text-muted">{{ entry.record_count_after }}</td>
                  <td>
                    <div class="d-flex align-items-center gap-1">
                      <button
                        class="btn btn-ghost-secondary btn-icon btn-sm"
                        title="View snapshot"
                        @click="openSnapshot(entry)"
                      >
                        <IconEye :size="16" />
                      </button>
                      <button
                        class="btn btn-ghost-warning btn-icon btn-sm"
                        title="Restore to state before this change"
                        :disabled="restoringId === entry.id"
                        @click="restore(entry)"
                      >
                        <span
                          v-if="restoringId === entry.id"
                          class="spinner-border spinner-border-sm"
                          style="width:0.9em;height:0.9em;"
                        />
                        <IconRestore v-else :size="16" />
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div v-if="history.total > history.page_size" class="card-footer d-flex align-items-center">
            <p class="m-0 text-muted small">
              Showing {{ (history.page - 1) * history.page_size + 1 }}–{{ Math.min(history.page * history.page_size, history.total) }}
              of {{ history.total }}
            </p>
            <ul class="pagination m-0 ms-auto">
              <li class="page-item" :class="{ disabled: history.page <= 1 }">
                <button class="page-link" @click="goToPage(history.page - 1)">prev</button>
              </li>
              <li
                v-for="p in Math.ceil(history.total / history.page_size)"
                :key="p"
                class="page-item"
                :class="{ active: p === history.page }"
              >
                <button class="page-link" @click="goToPage(p)">{{ p }}</button>
              </li>
              <li class="page-item" :class="{ disabled: history.page >= Math.ceil(history.total / history.page_size) }">
                <button class="page-link" @click="goToPage(history.page + 1)">next</button>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <!-- Snapshot modal -->
    <Teleport to="body">
      <template v-if="snapshotEntry">
        <div class="modal modal-blur fade show" style="display: block;" tabindex="-1" @click.self="closeSnapshot">
          <div class="modal-dialog modal-xl modal-dialog-centered modal-dialog-scrollable">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">
                  Snapshot — {{ actionLabel(snapshotEntry.action) }}
                  <span class="text-muted fw-normal small ms-2">{{ formatDate(snapshotEntry.created_at) }}</span>
                </h5>
                <button type="button" class="btn-close" @click="closeSnapshot" />
              </div>
              <div class="modal-body p-0">
                <div v-if="loadingSnapshot" class="text-center py-5">
                  <div class="spinner-border text-primary" />
                </div>
                <template v-else-if="snapshot">
                  <ul class="nav nav-tabs px-3 pt-2">
                    <li class="nav-item">
                      <button
                        class="nav-link"
                        :class="{ active: showSnapshotTab === 'before' }"
                        @click="showSnapshotTab = 'before'"
                      >
                        Before ({{ snapshot.before.length }} rrsets)
                      </button>
                    </li>
                    <li class="nav-item">
                      <button
                        class="nav-link"
                        :class="{ active: showSnapshotTab === 'after' }"
                        @click="showSnapshotTab = 'after'"
                      >
                        After ({{ snapshot.after.length }} rrsets)
                      </button>
                    </li>
                  </ul>
                  <div class="table-responsive" style="max-height: 60vh; overflow-y: auto;">
                    <table class="table table-vcenter table-sm mb-0">
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Type</th>
                          <th>TTL</th>
                          <th>Records</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-for="(rrset, i) in (showSnapshotTab === 'before' ? snapshot.before : snapshot.after)"
                          :key="i"
                        >
                          <td class="font-monospace small">{{ rrset.name }}</td>
                          <td><span class="badge bg-secondary text-secondary-fg">{{ rrset.type }}</span></td>
                          <td class="text-muted">{{ rrset.ttl }}</td>
                          <td class="font-monospace small">
                            <div
                              v-for="(rec, j) in (rrset.records as Record<string,unknown>[])"
                              :key="j"
                            >{{ rec.content }}</div>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </template>
              </div>
              <div class="modal-footer">
                <button class="btn btn-secondary" @click="closeSnapshot">Close</button>
                <button
                  class="btn btn-warning d-inline-flex align-items-center gap-1"
                  :disabled="restoringId === snapshotEntry.id"
                  @click="restore(snapshotEntry); closeSnapshot()"
                >
                  <IconRestore :size="16" />
                  Restore to this state
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-backdrop fade show" @click="closeSnapshot" />
      </template>
    </Teleport>
  </div>
</template>

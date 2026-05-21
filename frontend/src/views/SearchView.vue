<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IconSearch } from '@tabler/icons-vue'
import { useToast } from '@/composables/useToast'
import { useApiError, api } from '@/composables/useApi'
import type { SearchResult } from '@/types'

const route = useRoute()
const router = useRouter()
const toast = useToast()

const query = ref(String(route.query.q ?? ''))
const results = ref<SearchResult[]>([])
const loading = ref(false)
const searched = ref(false)

const zoneResults = computed(() => results.value.filter((r) => r.object_type === 'zone'))
const recordResults = computed(() => results.value.filter((r) => r.object_type === 'record'))
const commentResults = computed(() => results.value.filter((r) => r.object_type === 'comment'))

async function doSearch(): Promise<void> {
  const q = query.value.trim()
  if (!q) return
  await router.push({ path: '/search', query: { q } })
  loading.value = true
  searched.value = true
  try {
    results.value = await api.get<SearchResult[]>('/search', { params: { q, max: 100 } })
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    loading.value = false
  }
}

function zoneLink(zoneId: string): string {
  return `/zones/${encodeURIComponent(zoneId)}`
}

// Run search when component mounts if query param present
onMounted(() => {
  if (query.value) doSearch()
})

// Re-run if query param changes (e.g. browser back/forward)
watch(
  () => route.query.q,
  (q) => {
    if (q && q !== query.value) {
      query.value = String(q)
      doSearch()
    }
  },
)
</script>

<template>
  <div>
    <div class="page-header d-print-none">
      <div class="container-xl">
        <div class="row g-2 align-items-center">
          <div class="col">
            <div class="page-pretitle">DNS Management</div>
            <h2 class="page-title">Global Search</h2>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">
        <!-- Search input -->
        <div class="card mb-3">
          <div class="card-body">
            <form class="d-flex gap-2" @submit.prevent="doSearch">
              <div class="input-group flex-grow-1">
                <span class="input-group-text">
                  <IconSearch :size="16" />
                </span>
                <input
                  v-model="query"
                  type="search"
                  placeholder="Search zones, records…"
                  class="form-control"
                />
              </div>
              <button
                type="submit"
                :disabled="loading || !query.trim()"
                class="btn btn-primary d-inline-flex align-items-center gap-1"
              >
                <span v-if="loading" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                Search
              </button>
            </form>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="loading" class="d-flex justify-content-center py-5">
          <div class="spinner-border text-primary" />
        </div>

        <template v-else-if="searched">
          <!-- No results -->
          <div v-if="results.length === 0" class="empty">
            <div class="empty-icon">
              <IconSearch :size="40" />
            </div>
            <p class="empty-title">
              No results found for <strong>{{ query }}</strong>
            </p>
          </div>

          <template v-else>
            <!-- Summary -->
            <p class="text-muted mb-3">
              Found {{ results.length }} result{{ results.length !== 1 ? 's' : '' }} for
              <strong>{{ query }}</strong>
            </p>

            <!-- Zones -->
            <div v-if="zoneResults.length" class="card mb-3">
              <div class="card-header">
                <h3 class="card-title">Zones ({{ zoneResults.length }})</h3>
              </div>
              <div class="table-responsive">
                <table class="table table-vcenter table-hover">
                  <thead>
                    <tr>
                      <th>Zone name</th>
                      <th>Zone ID</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="r in zoneResults"
                      :key="r.zone_id + r.name"
                      style="cursor: pointer"
                      @click="$router.push(zoneLink(r.zone_id))"
                    >
                      <td class="font-monospace text-primary">{{ r.name }}</td>
                      <td class="font-monospace text-muted">{{ r.zone_id }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Records -->
            <div v-if="recordResults.length" class="card mb-3">
              <div class="card-header">
                <h3 class="card-title">Records ({{ recordResults.length }})</h3>
              </div>
              <div class="table-responsive">
                <table class="table table-vcenter table-hover">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Type</th>
                      <th>Content</th>
                      <th>Zone</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="r in recordResults"
                      :key="r.zone_id + r.name + r.type + r.content"
                      style="cursor: pointer"
                      @click="$router.push(zoneLink(r.zone_id))"
                    >
                      <td class="font-monospace">
                        <span :class="{ 'text-decoration-line-through opacity-50': r.disabled }">{{ r.name }}</span>
                      </td>
                      <td>
                        <span class="badge bg-secondary text-secondary-fg">{{ r.type }}</span>
                      </td>
                      <td class="font-monospace text-muted text-truncate" style="max-width: 250px">{{ r.content }}</td>
                      <td class="font-monospace text-primary">{{ r.zone }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Comments -->
            <div v-if="commentResults.length" class="card mb-3">
              <div class="card-header">
                <h3 class="card-title">Comments ({{ commentResults.length }})</h3>
              </div>
              <div class="table-responsive">
                <table class="table table-vcenter table-hover">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Content</th>
                      <th>Zone</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="r in commentResults"
                      :key="r.zone_id + r.name + r.content"
                      style="cursor: pointer"
                      @click="$router.push(zoneLink(r.zone_id))"
                    >
                      <td class="font-monospace">{{ r.name }}</td>
                      <td class="text-muted text-truncate" style="max-width: 250px">{{ r.content }}</td>
                      <td class="font-monospace text-primary">{{ r.zone }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </template>
        </template>
      </div>
    </div>
  </div>
</template>

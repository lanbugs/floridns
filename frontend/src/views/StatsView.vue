<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useToast } from '@/composables/useToast'
import { useApiError, api } from '@/composables/useApi'
import { useSettingsStore } from '@/stores/settings'
import type { PdnsStat } from '@/types'

const toast = useToast()
const settingsStore = useSettingsStore()

const stats = ref<PdnsStat[]>([])
const loading = ref(false)
const selectedServer = ref<string>('__default__')

const slaveServers = computed(() => settingsStore.settings.slave_servers ?? [])

const serverOptions = computed(() => [
  { label: 'Default (primary)', value: '__default__' },
  ...slaveServers.value.map((s) => ({ label: s.name, value: s.name })),
])

// Key stats to highlight in cards
const KEY_STATS = [
  'uptime',
  'queries',
  'tcp-queries',
  'cache-hits',
  'cache-misses',
  'packetcache-hit',
  'packetcache-miss',
  'latency',
  'sys-msec',
  'user-msec',
  'servfail-answers',
  'nxdomain-answers',
]

const keyStats = computed(() =>
  stats.value.filter((s) => KEY_STATS.includes(s.name) && isScalar(s.value)),
)

const otherStats = computed(() =>
  stats.value.filter((s) => !KEY_STATS.includes(s.name) && isScalar(s.value)),
)

const cacheHitRatio = computed(() => {
  const hits = Number(stats.value.find((s) => s.name === 'cache-hits')?.value ?? 0)
  const misses = Number(stats.value.find((s) => s.name === 'cache-misses')?.value ?? 0)
  const total = hits + misses
  if (total === 0) return 'N/A'
  return ((hits / total) * 100).toFixed(1) + '%'
})

async function loadStats(): Promise<void> {
  loading.value = true
  try {
    const params =
      selectedServer.value !== '__default__'
        ? { params: { server: selectedServer.value } }
        : undefined
    const data = await api.get<PdnsStat[]>('/stats', params)
    stats.value = data
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    loading.value = false
  }
}

function isScalar(v: unknown): boolean {
  return typeof v === 'string' || typeof v === 'number'
}

function formatStatValue(stat: PdnsStat): string {
  if (!isScalar(stat.value)) return '—'
  const v = String(stat.value)
  if (stat.name === 'uptime') {
    const secs = Number(v)
    const h = Math.floor(secs / 3600)
    const m = Math.floor((secs % 3600) / 60)
    const s = secs % 60
    return `${h}h ${m}m ${s}s`
  }
  if (stat.name === 'latency') return `${v} µs`
  return v
}

onMounted(async () => {
  await settingsStore.fetchSettings()
  await loadStats()
})
</script>

<template>
  <div>
    <div class="page-header d-print-none">
      <div class="container-xl">
        <div class="row g-2 align-items-center">
          <div class="col">
            <div class="page-pretitle">Monitoring</div>
            <h2 class="page-title">PowerDNS Statistics</h2>
          </div>
          <div class="col-auto ms-auto d-print-none">
            <div class="btn-list">
              <select
                v-if="serverOptions.length > 1"
                v-model="selectedServer"
                class="form-select"
                style="width: auto"
                @change="loadStats"
              >
                <option v-for="opt in serverOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
              <button
                class="btn btn-primary d-inline-flex align-items-center gap-1"
                :disabled="loading"
                @click="loadStats"
              >
                <span v-if="loading" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                Refresh
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">
        <!-- Cache hit ratio banner -->
        <div v-if="stats.length" class="card mb-3">
          <div class="card-body">
            <div class="subheader">Cache Hit Ratio</div>
            <div class="h1 mb-0">{{ cacheHitRatio }}</div>
          </div>
        </div>

        <!-- Loading state -->
        <div v-if="loading" class="d-flex justify-content-center py-5">
          <div class="spinner-border text-primary" />
        </div>

        <!-- Key stats cards -->
        <template v-else-if="stats.length">
          <div class="row row-cards g-3 mb-4">
            <div
              v-for="stat in keyStats"
              :key="stat.name"
              class="col-sm-6 col-lg-3"
            >
              <div class="card">
                <div class="card-body">
                  <div class="subheader">{{ stat.name }}</div>
                  <div class="h1 mb-0">{{ formatStatValue(stat) }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- All other stats table -->
          <div class="card">
            <div class="card-header">
              <h3 class="card-title">All Statistics</h3>
            </div>
            <div class="table-responsive">
              <table class="table table-vcenter">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th class="text-end">Value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="stat in otherStats" :key="stat.name">
                    <td class="font-monospace">{{ stat.name }}</td>
                    <td class="text-muted">{{ stat.type }}</td>
                    <td class="text-end font-monospace">{{ formatStatValue(stat) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </template>

        <div v-else-if="!loading" class="empty">
          <p class="empty-title">No statistics available.</p>
        </div>
      </div>
    </div>
  </div>
</template>

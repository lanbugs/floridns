<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { IconWorld, IconServer, IconShieldExclamation } from '@tabler/icons-vue'
import { api } from '@/composables/useApi'
import { useZonesStore } from '@/stores/zones'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const zonesStore = useZonesStore()
const auth = useAuthStore()

interface ServerStatus {
  name: string
  status: string
}
const primaryStatus = ref<string>('…')
const secondaryStatuses = ref<ServerStatus[]>([])

interface DnssecExpiryEntry {
  zone: string
  expiry: string
  days_remaining: number
  warning: boolean
  critical: boolean
}
const dnssecWarnings = ref<DnssecExpiryEntry[]>([])
const loadingDnssec = ref(false)

onMounted(async () => {
  await zonesStore.fetchZones({ page: 1, page_size: 1 })

  try {
    const servers = await api.get<ServerStatus[]>('/stats/servers')
    const primary = servers.find((s) => s.name === 'primary')
    primaryStatus.value = primary?.status ?? 'unknown'
    secondaryStatuses.value = servers.filter((s) => s.name !== 'primary')
  } catch {
    primaryStatus.value = 'unreachable'
  }

  if (auth.isAdmin) {
    loadingDnssec.value = true
    try {
      const entries = await api.get<DnssecExpiryEntry[]>('/admin/dnssec-expiry')
      dnssecWarnings.value = entries.filter((e) => e.warning)
    } catch {
      // non-critical — ignore silently
    } finally {
      loadingDnssec.value = false
    }
  }
})

function statusColor(status: string): string {
  if (status === 'reachable') return 'text-green'
  if (status === 'unreachable') return 'text-red'
  return 'text-muted'
}

function expiryBadgeClass(entry: DnssecExpiryEntry): string {
  if (entry.critical) return 'bg-red text-red-fg'
  if (entry.warning) return 'bg-yellow text-yellow-fg'
  return 'bg-green text-green-fg'
}
</script>

<template>
  <div>
    <div class="page-header d-print-none">
      <div class="container-xl">
        <div class="row g-2 align-items-center">
          <div class="col">
            <div class="page-pretitle">Overview</div>
            <h2 class="page-title">Dashboard</h2>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">
        <div class="row row-cards mb-4">
          <!-- Total zones -->
          <div class="col-12 col-sm-6 col-lg-3">
            <div class="card">
              <div class="card-body">
                <div class="d-flex align-items-center mb-3">
                  <IconWorld class="text-blue" :size="24" />
                  <div class="subheader ms-2">Total zones</div>
                </div>
                <div class="h1 mb-0">{{ zonesStore.total }}</div>
              </div>
            </div>
          </div>

          <!-- Primary PDNS status -->
          <div class="col-12 col-sm-6 col-lg-3">
            <div class="card">
              <div class="card-body">
                <div class="d-flex align-items-center mb-3">
                  <IconServer :class="statusColor(primaryStatus)" :size="24" />
                  <div class="subheader ms-2">Primary</div>
                </div>
                <div class="h1 mb-0">{{ primaryStatus }}</div>
              </div>
            </div>
          </div>

          <!-- Secondary server status cards -->
          <div
            v-for="srv in secondaryStatuses"
            :key="srv.name"
            class="col-12 col-sm-6 col-lg-3"
          >
            <div class="card">
              <div class="card-body">
                <div class="d-flex align-items-center mb-3">
                  <IconServer :class="statusColor(srv.status)" :size="24" />
                  <div class="subheader ms-2">{{ srv.name }}</div>
                </div>
                <div class="h1 mb-0">{{ srv.status }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- DNSSEC expiry warnings (admin only) -->
        <div v-if="auth.isAdmin" class="row row-cards mb-4">
          <div class="col-12">
            <div class="card">
              <div class="card-header">
                <h3 class="card-title d-flex align-items-center gap-2">
                  <IconShieldExclamation :size="18" />
                  DNSSEC Signature Expiry
                </h3>
              </div>
              <div v-if="loadingDnssec" class="card-body text-center py-3">
                <div class="spinner-border spinner-border-sm text-primary" />
                <div class="text-muted small mt-2">Checking DNSSEC signatures…</div>
              </div>
              <div v-else-if="dnssecWarnings.length === 0" class="card-body text-muted small">
                All DNSSEC signatures are valid (no zones expiring within 7 days).
              </div>
              <div v-else class="table-responsive">
                <table class="table table-vcenter card-table">
                  <thead>
                    <tr>
                      <th>Zone</th>
                      <th>Expires</th>
                      <th>Days remaining</th>
                      <th>Status</th>
                      <th class="w-1" />
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="entry in dnssecWarnings" :key="entry.zone">
                      <td class="font-monospace">{{ entry.zone }}</td>
                      <td class="text-muted">{{ new Date(entry.expiry).toLocaleString() }}</td>
                      <td>{{ entry.days_remaining }} day{{ entry.days_remaining === 1 ? '' : 's' }}</td>
                      <td>
                        <span :class="['badge', expiryBadgeClass(entry)]">
                          {{ entry.critical ? 'Critical' : 'Warning' }}
                        </span>
                      </td>
                      <td>
                        <button
                          class="btn btn-sm btn-ghost-secondary"
                          @click="router.push(`/zones/${entry.zone}`)"
                        >
                          Open zone
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        <div class="row row-cards">
          <div class="col-12">
            <div class="card">
              <div class="card-header">
                <h3 class="card-title">Quick access</h3>
              </div>
              <div class="card-body">
                <div class="btn-list">
                  <RouterLink to="/zones" class="btn btn-primary">
                    <IconWorld :size="16" class="me-1" />
                    View all zones
                  </RouterLink>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

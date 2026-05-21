<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { IconChevronDown, IconChevronRight, IconShield, IconBuilding, IconRefresh } from '@tabler/icons-vue'
import { api, useApiError } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import type { UserPermissionSummary } from '@/types'

const toast = useToast()
const users = ref<UserPermissionSummary[]>([])
const loading = ref(false)
const expanded = ref<Set<string>>(new Set())

async function load() {
  loading.value = true
  try {
    users.value = await api.get<UserPermissionSummary[]>('/admin/permissions-overview')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    loading.value = false
  }
}

onMounted(load)

function toggle(id: string) {
  if (expanded.value.has(id)) {
    expanded.value.delete(id)
  } else {
    expanded.value.add(id)
  }
  expanded.value = new Set(expanded.value)
}

function roleBadgeClass(role: string): string {
  const map: Record<string, string> = {
    superadmin: 'bg-red text-red-fg',
    admin: 'bg-blue text-blue-fg',
    operator: 'bg-green text-green-fg',
    viewer: 'bg-secondary text-secondary-fg',
  }
  return `badge ${map[role] ?? 'bg-secondary text-secondary-fg'}`
}

function hasPermissions(user: UserPermissionSummary): boolean {
  return user.direct_permissions.length > 0 || user.account_permissions.length > 0
}

function totalZones(user: UserPermissionSummary): number {
  const direct = new Set(user.direct_permissions.map(p => p.zone_name))
  for (const a of user.account_permissions) {
    for (const z of a.zones) direct.add(z)
  }
  return direct.size
}
</script>

<template>
  <div>
    <div class="page-header d-print-none">
      <div class="container-xl">
        <div class="row g-2 align-items-center">
          <div class="col">
            <div class="page-pretitle">Administration</div>
            <h2 class="page-title">Permissions Overview</h2>
          </div>
          <div class="col-auto ms-auto d-print-none">
            <div class="btn-list">
              <button class="btn btn-secondary d-inline-flex align-items-center gap-1" :disabled="loading" @click="load">
                <span v-if="loading" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                <IconRefresh v-else :size="16" />
                Refresh
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">
        <div class="card">
          <div class="table-responsive">
            <table class="table table-vcenter card-table">
              <thead>
                <tr>
                  <th class="w-1" />
                  <th>User</th>
                  <th>Global role</th>
                  <th>Status</th>
                  <th>Zone access</th>
                  <th>Sources</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="loading">
                  <td colspan="6" class="text-center py-4">
                    <div class="spinner-border text-primary" />
                  </td>
                </tr>
                <tr v-else-if="users.length === 0">
                  <td colspan="6" class="text-center text-muted py-4">No users found.</td>
                </tr>
                <template v-else v-for="user in users" :key="user.id">
                  <!-- Main row -->
                  <tr
                    :class="{ 'table-active': expanded.has(user.id) }"
                    style="cursor: pointer"
                    @click="hasPermissions(user) ? toggle(user.id) : undefined"
                  >
                    <td>
                      <span v-if="hasPermissions(user)" class="text-muted">
                        <IconChevronDown v-if="expanded.has(user.id)" :size="16" />
                        <IconChevronRight v-else :size="16" />
                      </span>
                    </td>
                    <td>
                      <div class="fw-bold">{{ user.username }}</div>
                      <div class="text-muted small">{{ user.email }}</div>
                    </td>
                    <td><span :class="roleBadgeClass(user.role)">{{ user.role }}</span></td>
                    <td>
                      <span :class="['badge', user.is_active ? 'bg-green text-green-fg' : 'bg-secondary text-secondary-fg']">
                        {{ user.is_active ? 'Active' : 'Disabled' }}
                      </span>
                    </td>
                    <td>
                      <span v-if="user.role === 'superadmin' || user.role === 'admin'" class="text-muted small">
                        all zones (global role)
                      </span>
                      <span v-else-if="totalZones(user) > 0" class="text-muted small">
                        {{ totalZones(user) }} zone{{ totalZones(user) !== 1 ? 's' : '' }}
                      </span>
                      <span v-else class="text-muted small">—</span>
                    </td>
                    <td>
                      <div class="d-flex gap-1 flex-wrap">
                        <span v-if="user.direct_permissions.length" class="badge bg-azure-lt d-inline-flex align-items-center gap-1">
                          <IconShield :size="10" />
                          {{ user.direct_permissions.length }} direct
                        </span>
                        <span
                          v-for="a in user.account_permissions"
                          :key="a.account_id"
                          class="badge bg-purple-lt d-inline-flex align-items-center gap-1"
                        >
                          <IconBuilding :size="10" />
                          {{ a.account_name }}
                        </span>
                      </div>
                    </td>
                  </tr>

                  <!-- Expanded detail row -->
                  <tr v-if="expanded.has(user.id)">
                    <td />
                    <td colspan="5" class="bg-light py-3">
                      <div class="row g-3">

                        <!-- Direct permissions -->
                        <div v-if="user.direct_permissions.length" class="col-12 col-lg-6">
                          <div class="d-flex align-items-center gap-1 mb-2">
                            <IconShield :size="14" class="text-azure" />
                            <span class="fw-semibold small text-uppercase text-muted">Direct zone permissions</span>
                          </div>
                          <table class="table table-sm table-vcenter mb-0">
                            <thead>
                              <tr>
                                <th>Zone</th>
                                <th>Role</th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr v-for="perm in user.direct_permissions" :key="perm.zone_name">
                                <td class="font-monospace small">{{ perm.zone_name }}</td>
                                <td><span :class="roleBadgeClass(perm.role)">{{ perm.role }}</span></td>
                              </tr>
                            </tbody>
                          </table>
                        </div>

                        <!-- Account-based permissions -->
                        <div
                          v-for="acct in user.account_permissions"
                          :key="acct.account_id"
                          class="col-12 col-lg-6"
                        >
                          <div class="d-flex align-items-center gap-1 mb-2">
                            <IconBuilding :size="14" class="text-purple" />
                            <span class="fw-semibold small text-uppercase text-muted">
                              {{ acct.account_name }}
                              <span :class="['ms-1', roleBadgeClass(acct.member_role)]">{{ acct.member_role }}</span>
                            </span>
                          </div>
                          <div v-if="acct.zones.length" class="table-responsive">
                            <table class="table table-sm table-vcenter mb-0">
                              <thead>
                                <tr>
                                  <th>Zone (via account)</th>
                                  <th>Effective role</th>
                                </tr>
                              </thead>
                              <tbody>
                                <tr v-for="zone in acct.zones" :key="zone">
                                  <td class="font-monospace small">{{ zone }}</td>
                                  <td><span :class="roleBadgeClass(acct.member_role)">{{ acct.member_role }}</span></td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                          <p v-else class="text-muted small mb-0">No zones assigned to this account yet.</p>
                        </div>

                        <!-- No permissions -->
                        <div v-if="!user.direct_permissions.length && !user.account_permissions.length" class="col-12">
                          <p class="text-muted small mb-0">No zone-specific permissions assigned.</p>
                        </div>

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
  </div>
</template>

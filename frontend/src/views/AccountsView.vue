<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  IconPlus,
  IconTrash,
  IconPencil,
  IconWorld,
  IconUsers,
} from '@tabler/icons-vue'
import { api, useApiError } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import type { Account, User, Zone } from '@/types'

const toast = useToast()

const accounts = ref<Account[]>([])
const users = ref<User[]>([])
const zones = ref<Zone[]>([])
const loading = ref(false)

const showForm = ref(false)
const saving = ref(false)
const editingAccount = ref<Account | null>(null)
const form = ref({ name: '', description: '' })

const formTitle = computed(() => (editingAccount.value ? `Edit — ${editingAccount.value.name}` : 'Create account'))

const showZones = ref(false)
const managingAccount = ref<Account | null>(null)
const addingZone = ref(false)
const newZoneName = ref('')

const availableZones = computed(() => {
  const assigned = new Set(managingAccount.value?.zone_names ?? [])
  return zones.value.filter((z) => !assigned.has(z.name))
})

const showUsers = ref(false)
const addingUser = ref(false)
const newUserEntry = ref({ user_id: '', role: 'viewer' as 'operator' | 'viewer' })

const availableUsers = computed(() => {
  const assigned = new Set(managingAccount.value?.users.map((u) => u.user_id) ?? [])
  return users.value.filter((u) => !assigned.has(u.id))
})

function badgeClass(variant: string): string {
  const map: Record<string, string> = {
    operator: 'bg-green text-green-fg',
    viewer: 'bg-secondary text-secondary-fg',
    admin: 'bg-blue text-blue-fg',
    superadmin: 'bg-red text-red-fg',
  }
  return `badge ${map[variant] ?? 'bg-secondary text-secondary-fg'}`
}

async function load() {
  loading.value = true
  try {
    const [accts, usrs, zonesData] = await Promise.all([
      api.get<Account[]>('/accounts'),
      api.get<User[]>('/users'),
      api.get<{ items: Zone[] }>('/zones?page_size=500'),
    ])
    accounts.value = accts
    users.value = usrs
    zones.value = zonesData.items
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    loading.value = false
  }
}

onMounted(load)

function openCreate() {
  editingAccount.value = null
  form.value = { name: '', description: '' }
  showForm.value = true
}

function openEdit(account: Account) {
  editingAccount.value = account
  form.value = { name: account.name, description: account.description ?? '' }
  showForm.value = true
}

async function saveAccount() {
  saving.value = true
  try {
    if (editingAccount.value) {
      await api.patch(`/accounts/${editingAccount.value.id}`, form.value)
      toast.success(`Account ${form.value.name} updated`)
    } else {
      await api.post('/accounts', form.value)
      toast.success(`Account ${form.value.name} created`)
    }
    showForm.value = false
    await load()
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    saving.value = false
  }
}

async function deleteAccount(account: Account) {
  if (!confirm(`Delete account "${account.name}"? This removes all zone and user assignments.`)) return
  try {
    await api.delete(`/accounts/${account.id}`)
    toast.success(`Account ${account.name} deleted`)
    accounts.value = accounts.value.filter((a) => a.id !== account.id)
  } catch (e) {
    toast.error(useApiError(e))
  }
}

function openZones(account: Account) {
  managingAccount.value = { ...account }
  newZoneName.value = availableZones.value[0]?.name ?? ''
  showZones.value = true
}

async function addZone() {
  if (!managingAccount.value || !newZoneName.value) return
  addingZone.value = true
  try {
    const updated = await api.post<Account>(`/accounts/${managingAccount.value.id}/zones`, { zone_name: newZoneName.value })
    managingAccount.value = updated
    const idx = accounts.value.findIndex((a) => a.id === updated.id)
    if (idx !== -1) accounts.value[idx] = updated
    newZoneName.value = availableZones.value[0]?.name ?? ''
    toast.success('Zone added')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    addingZone.value = false
  }
}

async function removeZone(zoneName: string) {
  if (!managingAccount.value) return
  try {
    await api.delete(`/accounts/${managingAccount.value.id}/zones?zone_name=${encodeURIComponent(zoneName)}`)
    managingAccount.value = { ...managingAccount.value, zone_names: managingAccount.value.zone_names.filter((z) => z !== zoneName) }
    const idx = accounts.value.findIndex((a) => a.id === managingAccount.value!.id)
    if (idx !== -1) accounts.value[idx] = { ...accounts.value[idx], zone_names: managingAccount.value.zone_names }
    toast.success('Zone removed')
  } catch (e) {
    toast.error(useApiError(e))
  }
}

function openUsers(account: Account) {
  managingAccount.value = { ...account }
  newUserEntry.value = { user_id: availableUsers.value[0]?.id ?? '', role: 'viewer' }
  showUsers.value = true
}

async function addUser() {
  if (!managingAccount.value || !newUserEntry.value.user_id) return
  addingUser.value = true
  try {
    const updated = await api.post<Account>(`/accounts/${managingAccount.value.id}/users`, { user_id: newUserEntry.value.user_id, role: newUserEntry.value.role })
    managingAccount.value = updated
    const idx = accounts.value.findIndex((a) => a.id === updated.id)
    if (idx !== -1) accounts.value[idx] = updated
    newUserEntry.value = { user_id: availableUsers.value[0]?.id ?? '', role: 'viewer' }
    toast.success('User added')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    addingUser.value = false
  }
}

async function removeUser(userId: string) {
  if (!managingAccount.value) return
  try {
    await api.delete(`/accounts/${managingAccount.value.id}/users/${userId}`)
    managingAccount.value = { ...managingAccount.value, users: managingAccount.value.users.filter((u) => u.user_id !== userId) }
    const idx = accounts.value.findIndex((a) => a.id === managingAccount.value!.id)
    if (idx !== -1) accounts.value[idx] = { ...accounts.value[idx], users: managingAccount.value.users }
    toast.success('User removed')
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
          <div class="col">
            <div class="page-pretitle">Administration</div>
            <h2 class="page-title">Accounts</h2>
          </div>
          <div class="col-auto ms-auto d-print-none">
            <div class="btn-list">
              <button class="btn btn-primary d-inline-flex align-items-center gap-1" @click="openCreate">
                <IconPlus :size="16" />
                Create account
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">
        <p class="text-muted mb-3">
          Accounts group zones together and grant users access. Operators can edit records; viewers can only read.
        </p>

        <div class="card">
          <div class="table-responsive">
            <table class="table table-vcenter card-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Zones</th>
                  <th>Users</th>
                  <th class="w-1" />
                </tr>
              </thead>
              <tbody>
                <tr v-if="loading">
                  <td colspan="4" class="text-center py-4">
                    <div class="spinner-border text-primary" />
                  </td>
                </tr>
                <tr v-else-if="accounts.length === 0">
                  <td colspan="4" class="text-center text-muted py-4">No accounts yet.</td>
                </tr>
                <template v-else>
                  <tr v-for="account in accounts" :key="account.id">
                    <td>
                      <div class="fw-bold">{{ account.name }}</div>
                      <div v-if="account.description" class="small text-muted mt-1">{{ account.description }}</div>
                    </td>
                    <td class="text-muted">{{ account.zone_names.length }} zone{{ account.zone_names.length !== 1 ? 's' : '' }}</td>
                    <td class="text-muted">{{ account.users.length }} user{{ account.users.length !== 1 ? 's' : '' }}</td>
                    <td>
                      <div class="d-flex gap-1">
                        <button class="btn btn-ghost-secondary btn-icon btn-sm" title="Manage zones" @click="openZones(account)">
                          <IconWorld :size="16" class="text-blue" />
                        </button>
                        <button class="btn btn-ghost-secondary btn-icon btn-sm" title="Manage users" @click="openUsers(account)">
                          <IconUsers :size="16" class="text-green" />
                        </button>
                        <button class="btn btn-ghost-secondary btn-icon btn-sm" title="Edit" @click="openEdit(account)">
                          <IconPencil :size="16" />
                        </button>
                        <button class="btn btn-ghost-secondary btn-icon btn-sm" title="Delete" @click="deleteAccount(account)">
                          <IconTrash :size="16" class="text-danger" />
                        </button>
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

    <!-- Create / Edit modal -->
    <Teleport to="body">
      <template v-if="showForm">
        <div class="modal modal-blur fade show" style="display: block;" tabindex="-1" role="dialog" @click.self="showForm = false">
          <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">{{ formTitle }}</h5>
                <button type="button" class="btn-close" @click="showForm = false" />
              </div>
              <div class="modal-body">
                <div class="mb-3">
                  <label class="form-label">Name</label>
                  <input v-model="form.name" required class="form-control" />
                </div>
                <div class="mb-3">
                  <label class="form-label">Description <span class="fw-normal text-muted">(optional)</span></label>
                  <input v-model="form.description" class="form-control" />
                </div>
              </div>
              <div class="modal-footer">
                <button class="btn btn-secondary" @click="showForm = false">Cancel</button>
                <button class="btn btn-primary d-inline-flex align-items-center gap-1" :disabled="saving" @click="saveAccount">
                  <span v-if="saving" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                  {{ editingAccount ? 'Save' : 'Create' }}
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-backdrop fade show" @click="showForm = false" />
      </template>
    </Teleport>

    <!-- Zone management modal -->
    <Teleport to="body">
      <template v-if="showZones">
        <div class="modal modal-blur fade show" style="display: block;" tabindex="-1" role="dialog" @click.self="showZones = false">
          <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable modal-lg">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">Zones — {{ managingAccount?.name }}</h5>
                <button type="button" class="btn-close" @click="showZones = false" />
              </div>
              <div class="modal-body">
                <div v-if="managingAccount?.zone_names.length" class="list-group list-group-flush mb-3">
                  <div v-for="zoneName in managingAccount.zone_names" :key="zoneName" class="list-group-item d-flex align-items-center justify-content-between">
                    <span class="font-monospace small">{{ zoneName }}</span>
                    <button class="btn btn-ghost-secondary btn-icon btn-sm" @click="removeZone(zoneName)">
                      <IconTrash :size="14" class="text-danger" />
                    </button>
                  </div>
                </div>
                <p v-else class="text-muted small mb-3">No zones assigned yet.</p>
                <div class="card bg-light mb-0">
                  <div class="card-body p-3">
                    <p class="small fw-bold text-uppercase text-muted mb-2">Add zone</p>
                    <div v-if="availableZones.length" class="d-flex gap-2">
                      <select v-model="newZoneName" class="form-select form-select-sm flex-grow-1">
                        <option v-for="z in availableZones" :key="z.id" :value="z.name">{{ z.name }}</option>
                      </select>
                      <button class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1" :disabled="addingZone" @click="addZone">
                        <span v-if="addingZone" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                        <IconPlus v-else :size="16" />
                        Add
                      </button>
                    </div>
                    <p v-else class="text-muted small mb-0">All zones are already assigned.</p>
                  </div>
                </div>
              </div>
              <div class="modal-footer">
                <button class="btn btn-secondary" @click="showZones = false">Close</button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-backdrop fade show" @click="showZones = false" />
      </template>
    </Teleport>

    <!-- User management modal -->
    <Teleport to="body">
      <template v-if="showUsers">
        <div class="modal modal-blur fade show" style="display: block;" tabindex="-1" role="dialog" @click.self="showUsers = false">
          <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable modal-lg">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">Users — {{ managingAccount?.name }}</h5>
                <button type="button" class="btn-close" @click="showUsers = false" />
              </div>
              <div class="modal-body">
                <div v-if="managingAccount?.users.length" class="list-group list-group-flush mb-3">
                  <div v-for="entry in managingAccount.users" :key="entry.user_id" class="list-group-item d-flex align-items-center justify-content-between">
                    <span class="fw-bold small">{{ entry.username }}</span>
                    <div class="d-flex align-items-center gap-2">
                      <span :class="badgeClass(entry.role)">{{ entry.role }}</span>
                      <button class="btn btn-ghost-secondary btn-icon btn-sm" @click="removeUser(entry.user_id)">
                        <IconTrash :size="14" class="text-danger" />
                      </button>
                    </div>
                  </div>
                </div>
                <p v-else class="text-muted small mb-3">No users assigned yet.</p>
                <div class="card bg-light mb-0">
                  <div class="card-body p-3">
                    <p class="small fw-bold text-uppercase text-muted mb-2">Add user</p>
                    <div v-if="availableUsers.length" class="d-flex gap-2">
                      <select v-model="newUserEntry.user_id" class="form-select form-select-sm flex-grow-1">
                        <option v-for="u in availableUsers" :key="u.id" :value="u.id">{{ u.username }}</option>
                      </select>
                      <select v-model="newUserEntry.role" class="form-select form-select-sm" style="width: 7rem">
                        <option value="viewer">viewer</option>
                        <option value="operator">operator</option>
                      </select>
                      <button class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1" :disabled="addingUser" @click="addUser">
                        <span v-if="addingUser" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                        <IconPlus v-else :size="16" />
                        Add
                      </button>
                    </div>
                    <p v-else class="text-muted small mb-0">All users are already assigned.</p>
                  </div>
                </div>
              </div>
              <div class="modal-footer">
                <button class="btn btn-secondary" @click="showUsers = false">Close</button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-backdrop fade show" @click="showUsers = false" />
      </template>
    </Teleport>
  </div>
</template>

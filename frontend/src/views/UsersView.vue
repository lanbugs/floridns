<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { IconPlus, IconTrash, IconPencil, IconShield } from '@tabler/icons-vue'
import { api, useApiError } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import type { User, UserRole, ZonePermissionResponse, Zone } from '@/types'

const toast = useToast()
const users = ref<User[]>([])
const loading = ref(false)

const showCreate = ref(false)
const creating = ref(false)
const createForm = ref({ username: '', email: '', password: '', role: 'viewer' as UserRole })

const showEdit = ref(false)
const saving = ref(false)
const editingUser = ref<User | null>(null)
const editForm = ref({ email: '', role: 'viewer' as UserRole, is_active: true, password: '' })

const showPerms = ref(false)
const permUser = ref<User | null>(null)
const permissions = ref<ZonePermissionResponse[]>([])
const permsLoading = ref(false)
const zones = ref<Zone[]>([])
const newPerm = ref({ zone_name: '', role: 'viewer' as UserRole })
const addingPerm = ref(false)

function badgeClass(variant: string): string {
  const map: Record<string, string> = {
    red: 'bg-red text-red-fg',
    blue: 'bg-blue text-blue-fg',
    green: 'bg-green text-green-fg',
    gray: 'bg-secondary text-secondary-fg',
  }
  return `badge ${map[variant] ?? map['gray']}`
}

const roleBadge = (role: UserRole) =>
  ({ superadmin: 'red', admin: 'blue', operator: 'green', viewer: 'gray' } as const)[role]

async function load() {
  loading.value = true
  try {
    users.value = await api.get<User[]>('/users')
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function createUser() {
  creating.value = true
  try {
    await api.post('/users', createForm.value)
    toast.success(`User ${createForm.value.username} created`)
    showCreate.value = false
    createForm.value = { username: '', email: '', password: '', role: 'viewer' }
    await load()
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    creating.value = false
  }
}

function openEdit(user: User) {
  editingUser.value = user
  editForm.value = { email: user.email, role: user.role, is_active: user.is_active, password: '' }
  showEdit.value = true
}

async function saveUser() {
  if (!editingUser.value) return
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      email: editForm.value.email,
      role: editForm.value.role,
      is_active: editForm.value.is_active,
    }
    if (editForm.value.password) payload.password = editForm.value.password
    await api.patch(`/users/${editingUser.value.id}`, payload)
    toast.success(`User ${editingUser.value.username} updated`)
    showEdit.value = false
    await load()
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    saving.value = false
  }
}

async function deleteUser(user: User) {
  if (!confirm(`Delete user ${user.username}?`)) return
  try {
    await api.delete(`/users/${user.id}`)
    toast.success(`${user.username} deleted`)
    users.value = users.value.filter((u) => u.id !== user.id)
  } catch (e) {
    toast.error(useApiError(e))
  }
}

async function openPerms(user: User) {
  permUser.value = user
  showPerms.value = true
  permsLoading.value = true
  try {
    const [permsData, zonesData] = await Promise.all([
      api.get<ZonePermissionResponse[]>(`/users/${user.id}/zone-permissions`),
      api.get<{ items: Zone[] }>('/zones?page_size=500'),
    ])
    permissions.value = permsData
    zones.value = zonesData.items
    newPerm.value = { zone_name: zonesData.items[0]?.name ?? '', role: 'viewer' }
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    permsLoading.value = false
  }
}

async function addPermission() {
  if (!permUser.value || !newPerm.value.zone_name) return
  addingPerm.value = true
  try {
    const created = await api.post<ZonePermissionResponse>(
      `/users/${permUser.value.id}/zone-permissions`,
      newPerm.value,
    )
    permissions.value.push(created)
    toast.success(`Access to ${newPerm.value.zone_name} granted`)
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    addingPerm.value = false
  }
}

async function removePermission(permId: string) {
  if (!permUser.value) return
  try {
    await api.delete(`/users/${permUser.value.id}/zone-permissions/${permId}`)
    permissions.value = permissions.value.filter((p) => p.id !== permId)
    toast.success('Permission removed')
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
            <h2 class="page-title">Users</h2>
          </div>
          <div class="col-auto ms-auto d-print-none">
            <div class="btn-list">
              <button class="btn btn-primary d-inline-flex align-items-center gap-1" @click="showCreate = true">
                <IconPlus :size="16" />
                Create user
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
                  <th>Username</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th class="w-1" />
                </tr>
              </thead>
              <tbody>
                <tr v-if="loading">
                  <td colspan="5" class="text-center py-4">
                    <div class="spinner-border text-primary" />
                  </td>
                </tr>
                <tr v-else-if="users.length === 0">
                  <td colspan="5" class="text-center text-muted py-4">No users found.</td>
                </tr>
                <template v-else>
                  <tr v-for="user in users" :key="user.id">
                    <td class="fw-bold">{{ user.username }}</td>
                    <td class="text-muted">{{ user.email }}</td>
                    <td><span :class="badgeClass(roleBadge(user.role))">{{ user.role }}</span></td>
                    <td>
                      <span :class="['badge', user.is_active ? 'bg-green text-green-fg' : 'bg-secondary text-secondary-fg']">
                        {{ user.is_active ? 'Active' : 'Disabled' }}
                      </span>
                    </td>
                    <td>
                      <div class="d-flex gap-1">
                        <button class="btn btn-ghost-secondary btn-icon btn-sm" title="Zone permissions" @click="openPerms(user)">
                          <IconShield :size="16" class="text-blue" />
                        </button>
                        <button class="btn btn-ghost-secondary btn-icon btn-sm" title="Edit" @click="openEdit(user)">
                          <IconPencil :size="16" />
                        </button>
                        <button class="btn btn-ghost-secondary btn-icon btn-sm" title="Delete" @click="deleteUser(user)">
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

    <!-- Create modal -->
    <Teleport to="body">
      <template v-if="showCreate">
        <div class="modal modal-blur fade show" style="display: block;" tabindex="-1" role="dialog" @click.self="showCreate = false">
          <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">Create user</h5>
                <button type="button" class="btn-close" @click="showCreate = false" />
              </div>
              <div class="modal-body">
                <div class="mb-3">
                  <label class="form-label">Username</label>
                  <input v-model="createForm.username" required class="form-control" />
                </div>
                <div class="mb-3">
                  <label class="form-label">Email</label>
                  <input v-model="createForm.email" type="email" required class="form-control" />
                </div>
                <div class="mb-3">
                  <label class="form-label">Password</label>
                  <input v-model="createForm.password" type="password" required minlength="8" class="form-control" />
                </div>
                <div class="mb-3">
                  <label class="form-label">Role</label>
                  <select v-model="createForm.role" class="form-select">
                    <option value="viewer">viewer</option>
                    <option value="operator">operator</option>
                    <option value="admin">admin</option>
                    <option value="superadmin">superadmin</option>
                  </select>
                </div>
              </div>
              <div class="modal-footer">
                <button class="btn btn-secondary" @click="showCreate = false">Cancel</button>
                <button class="btn btn-primary d-inline-flex align-items-center gap-1" :disabled="creating" @click="createUser">
                  <span v-if="creating" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                  Create
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-backdrop fade show" @click="showCreate = false" />
      </template>
    </Teleport>

    <!-- Edit modal -->
    <Teleport to="body">
      <template v-if="showEdit">
        <div class="modal modal-blur fade show" style="display: block;" tabindex="-1" role="dialog" @click.self="showEdit = false">
          <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">Edit — {{ editingUser?.username }}</h5>
                <button type="button" class="btn-close" @click="showEdit = false" />
              </div>
              <div class="modal-body">
                <div class="mb-3">
                  <label class="form-label">Email</label>
                  <input v-model="editForm.email" type="email" required class="form-control" />
                </div>
                <div class="mb-3">
                  <label class="form-label">
                    New password
                    <span class="fw-normal text-muted">(leave blank to keep current)</span>
                  </label>
                  <input v-model="editForm.password" type="password" minlength="8" class="form-control" />
                </div>
                <div class="mb-3">
                  <label class="form-label">Role</label>
                  <select v-model="editForm.role" class="form-select">
                    <option value="viewer">viewer</option>
                    <option value="operator">operator</option>
                    <option value="admin">admin</option>
                    <option value="superadmin">superadmin</option>
                  </select>
                </div>
                <div class="mb-3">
                  <label class="form-check">
                    <input id="is_active" v-model="editForm.is_active" type="checkbox" class="form-check-input" />
                    <span class="form-check-label">Active</span>
                  </label>
                </div>
              </div>
              <div class="modal-footer">
                <button class="btn btn-secondary" @click="showEdit = false">Cancel</button>
                <button class="btn btn-primary d-inline-flex align-items-center gap-1" :disabled="saving" @click="saveUser">
                  <span v-if="saving" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                  Save
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-backdrop fade show" @click="showEdit = false" />
      </template>
    </Teleport>

    <!-- Zone permissions modal -->
    <Teleport to="body">
      <template v-if="showPerms">
        <div class="modal modal-blur fade show" style="display: block;" tabindex="-1" role="dialog" @click.self="showPerms = false">
          <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">Zone access — {{ permUser?.username }}</h5>
                <button type="button" class="btn-close" @click="showPerms = false" />
              </div>
              <div class="modal-body">
                <p class="text-muted small mb-3">
                  Grant this user access to specific zones. Overrides the global role for those zones.
                </p>
                <div v-if="permsLoading" class="py-4 text-center text-muted">Loading…</div>
                <div v-else>
                  <div v-if="permissions.length > 0" class="list-group list-group-flush mb-3">
                    <div
                      v-for="perm in permissions"
                      :key="perm.id"
                      class="list-group-item d-flex align-items-center justify-content-between"
                    >
                      <span class="font-monospace small">{{ perm.zone_name }}</span>
                      <div class="d-flex align-items-center gap-2">
                        <span :class="badgeClass(roleBadge(perm.role))">{{ perm.role }}</span>
                        <button class="btn btn-ghost-secondary btn-icon btn-sm" @click="removePermission(perm.id)">
                          <IconTrash :size="14" class="text-danger" />
                        </button>
                      </div>
                    </div>
                  </div>
                  <p v-else class="text-muted small mb-3">No zone-specific permissions yet.</p>
                  <div class="card bg-light mb-0">
                    <div class="card-body p-3">
                      <p class="small fw-bold text-uppercase text-muted mb-2">Add permission</p>
                      <div class="d-flex gap-2">
                        <select v-model="newPerm.zone_name" class="form-select form-select-sm flex-grow-1">
                          <option v-for="z in zones" :key="z.id" :value="z.name">{{ z.name }}</option>
                        </select>
                        <select v-model="newPerm.role" class="form-select form-select-sm" style="width: 7rem">
                          <option value="viewer">viewer</option>
                          <option value="operator">operator</option>
                          <option value="admin">admin</option>
                        </select>
                        <button
                          class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1"
                          :disabled="addingPerm"
                          @click="addPermission"
                        >
                          <span v-if="addingPerm" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                          <IconPlus v-else :size="16" />
                          Add
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div class="modal-footer">
                <button class="btn btn-secondary" @click="showPerms = false">Close</button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-backdrop fade show" @click="showPerms = false" />
      </template>
    </Teleport>
  </div>
</template>

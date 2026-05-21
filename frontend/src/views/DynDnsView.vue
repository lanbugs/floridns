<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  IconPlus, IconTrash, IconRefresh, IconCopy, IconCheck,
  IconWifi, IconWifiOff, IconKey,
} from '@tabler/icons-vue'
import { api, useApiError } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import type { DynDnsHost, DynDnsHostCreated, Zone } from '@/types'

const toast = useToast()

const hosts = ref<DynDnsHost[]>([])
const zones = ref<Zone[]>([])
const loading = ref(false)
const showForm = ref(false)
const creating = ref(false)
const newSecret = ref<DynDnsHostCreated | null>(null)
const copiedToken = ref(false)
const copiedUrl = ref<string | null>(null)

const form = ref({ hostname: '', zone_name: '', description: '' })

const origin = window.location.origin

async function load() {
  loading.value = true
  try {
    hosts.value = await api.get<DynDnsHost[]>('/dyndns/hosts')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    loading.value = false
  }
}

async function loadZones() {
  try {
    const resp = await api.get<{ items: Zone[] }>('/zones?page_size=500')
    zones.value = resp.items
  } catch {
    zones.value = []
  }
}

onMounted(() => {
  load()
  loadZones()
})

function displayHostname(host: DynDnsHost) {
  return host.hostname.replace(/\.$/, '')
}

function updateUrl(host: DynDnsHost) {
  return `${origin}/nic/update?hostname=${displayHostname(host)}&myip=<YOUR_IP>`
}

function fullFqdn(): string {
  const label = form.value.hostname.trim()
  const zone = form.value.zone_name.replace(/\.$/, '')
  return label && zone ? `${label}.${zone}` : ''
}

async function copyText(text: string, key: string) {
  await navigator.clipboard.writeText(text)
  copiedUrl.value = key
  setTimeout(() => { copiedUrl.value = null }, 2000)
}

async function copyToken() {
  if (!newSecret.value) return
  await navigator.clipboard.writeText(newSecret.value.token)
  copiedToken.value = true
  setTimeout(() => { copiedToken.value = false }, 2000)
}

async function createHost() {
  if (!form.value.hostname.trim() || !form.value.zone_name) return
  creating.value = true
  try {
    const created = await api.post<DynDnsHostCreated>('/dyndns/hosts', {
      hostname: form.value.hostname.trim(),
      zone_name: form.value.zone_name,
      description: form.value.description || null,
    })
    newSecret.value = created
    hosts.value.push(created)
    form.value = { hostname: '', zone_name: '', description: '' }
    showForm.value = false
    toast.success('DynDNS host created — copy the token now')
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    creating.value = false
  }
}

async function toggleActive(host: DynDnsHost) {
  try {
    const updated = await api.patch<DynDnsHost>(`/dyndns/hosts/${host.id}`, { is_active: !host.is_active })
    Object.assign(host, updated)
  } catch (e) {
    toast.error(useApiError(e))
  }
}

async function regenerateToken(host: DynDnsHost) {
  if (!confirm(`Regenerate token for "${host.hostname}"? The old token will stop working immediately.`)) return
  try {
    const created = await api.post<DynDnsHostCreated>(`/dyndns/hosts/${host.id}/regenerate-token`, {})
    newSecret.value = created
    Object.assign(host, created)
    toast.success('Token regenerated — copy it now')
  } catch (e) {
    toast.error(useApiError(e))
  }
}

async function deleteHost(host: DynDnsHost) {
  if (!confirm(`Delete "${host.hostname}"?`)) return
  try {
    await api.delete(`/dyndns/hosts/${host.id}`)
    hosts.value = hosts.value.filter(h => h.id !== host.id)
    if (newSecret.value?.id === host.id) newSecret.value = null
    toast.success('Host deleted')
  } catch (e) {
    toast.error(useApiError(e))
  }
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('en-GB')
}

</script>

<template>
  <div>
    <div class="page-header d-print-none">
      <div class="container-xl">
        <div class="row g-2 align-items-center">
          <div class="col">
            <div class="page-pretitle">DNS</div>
            <h2 class="page-title">Dynamic DNS</h2>
          </div>
          <div class="col-auto ms-auto">
            <button class="btn btn-primary d-inline-flex align-items-center gap-1" @click="showForm = !showForm">
              <IconPlus :size="16" />
              New host
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">

        <!-- New token banner -->
        <div v-if="newSecret" class="alert alert-warning d-flex align-items-start gap-3 mb-3">
          <IconKey :size="20" class="flex-shrink-0 mt-1" />
          <div class="flex-grow-1">
            <h4 class="alert-title">Copy your token now — it will not be shown again</h4>
            <p class="text-muted small mb-2">
              Hostname: <code>{{ displayHostname(newSecret) }}</code>
            </p>
            <div class="input-group mb-2">
              <input :value="newSecret.token" readonly class="form-control font-monospace" style="font-size:0.8125rem" />
              <button class="btn btn-outline-secondary d-inline-flex align-items-center gap-1" @click="copyToken">
                <IconCheck v-if="copiedToken" :size="16" class="text-success" />
                <IconCopy v-else :size="16" />
                {{ copiedToken ? 'Copied' : 'Copy' }}
              </button>
            </div>
            <div class="text-muted small">
              Update URL: <code>{{ updateUrl(newSecret) }}</code><br>
              Basic Auth — Username: <code>{{ displayHostname(newSecret) }}</code> &nbsp; Password: (token above)
            </div>
          </div>
          <button type="button" class="btn-close" @click="newSecret = null" />
        </div>

        <!-- Create form -->
        <div v-if="showForm" class="card mb-3">
          <div class="card-header">
            <h3 class="card-title">New DynDNS host</h3>
          </div>
          <div class="card-body">
            <div class="row g-3">
              <div class="col-sm-4">
                <label class="form-label">Zone <span class="text-danger">*</span></label>
                <select v-model="form.zone_name" class="form-select">
                  <option value="">Select zone…</option>
                  <option v-for="z in zones" :key="z.id" :value="z.name">{{ z.name.replace(/\.$/, '') }}</option>
                </select>
              </div>
              <div class="col-sm-4">
                <label class="form-label">Hostname <span class="text-danger">*</span></label>
                <div class="input-group">
                  <input
                    v-model="form.hostname"
                    class="form-control"
                    placeholder="home"
                  />
                  <span class="input-group-text text-muted" style="font-size:0.8125rem">
                    .{{ form.zone_name ? form.zone_name.replace(/\.$/, '') : 'zone' }}
                  </span>
                </div>
                <div v-if="fullFqdn()" class="form-hint">FQDN: <code>{{ fullFqdn() }}</code></div>
              </div>
              <div class="col-sm-3">
                <label class="form-label">Description</label>
                <input v-model="form.description" class="form-control" placeholder="Home router" />
              </div>
            </div>
          </div>
          <div class="card-footer d-flex justify-content-end gap-2">
            <button class="btn btn-secondary" @click="showForm = false; form = { hostname: '', zone_name: '', description: '' }">Cancel</button>
            <button
              class="btn btn-primary d-inline-flex align-items-center gap-1"
              :disabled="creating || !form.hostname.trim() || !form.zone_name"
              @click="createHost"
            >
              <span v-if="creating" class="spinner-border spinner-border-sm" style="width:.9em;height:.9em;" />
              Create host
            </button>
          </div>
        </div>

        <!-- Host list -->
        <div class="card mb-3">
          <div class="card-header">
            <h3 class="card-title">Registered hosts</h3>
          </div>
          <div class="table-responsive">
            <table class="table table-vcenter card-table">
              <thead>
                <tr>
                  <th>Hostname</th>
                  <th>Zone</th>
                  <th>Current IP</th>
                  <th>Last update</th>
                  <th>Status</th>
                  <th>Update URL</th>
                  <th class="w-1" />
                </tr>
              </thead>
              <tbody>
                <tr v-if="loading">
                  <td colspan="7" class="text-center py-4"><div class="spinner-border text-primary" /></td>
                </tr>
                <tr v-else-if="hosts.length === 0">
                  <td colspan="7" class="text-center text-muted py-4">No DynDNS hosts yet.</td>
                </tr>
                <tr v-for="host in hosts" :key="host.id">
                  <td>
                    <div class="d-flex align-items-center gap-2">
                      <component :is="host.offline ? IconWifiOff : IconWifi" :size="16" :class="host.offline ? 'text-danger' : 'text-success'" />
                      <span class="fw-medium">{{ displayHostname(host) }}</span>
                    </div>
                    <div v-if="host.description" class="text-muted small">{{ host.description }}</div>
                  </td>
                  <td class="text-muted small">{{ host.zone_name.replace(/\.$/, '') }}</td>
                  <td class="font-monospace small">
                    <div v-if="host.last_ip">{{ host.last_ip }}</div>
                    <div v-if="host.last_ip6" class="text-muted">{{ host.last_ip6 }}</div>
                    <span v-if="!host.last_ip && !host.last_ip6" class="text-muted">—</span>
                  </td>
                  <td class="text-muted small">{{ host.last_update ? formatDate(host.last_update) : '—' }}</td>
                  <td>
                    <span v-if="!host.is_active" class="badge bg-secondary text-secondary-fg">inactive</span>
                    <span v-else-if="host.offline" class="badge bg-danger text-danger-fg">offline</span>
                    <span v-else class="badge bg-success text-success-fg">active</span>
                  </td>
                  <td>
                    <div class="input-group input-group-sm" style="min-width:280px;max-width:400px;">
                      <input :value="updateUrl(host)" readonly class="form-control font-monospace" style="font-size:0.75rem" />
                      <button
                        class="btn btn-outline-secondary"
                        @click="copyText(updateUrl(host), host.id)"
                        title="Copy URL"
                      >
                        <IconCheck v-if="copiedUrl === host.id" :size="14" class="text-success" />
                        <IconCopy v-else :size="14" />
                      </button>
                    </div>
                  </td>
                  <td>
                    <div class="d-flex gap-1">
                      <button
                        class="btn btn-ghost-secondary btn-icon btn-sm"
                        :title="host.is_active ? 'Deactivate' : 'Activate'"
                        @click="toggleActive(host)"
                      >
                        <IconWifiOff v-if="host.is_active" :size="16" />
                        <IconWifi v-else :size="16" />
                      </button>
                      <button
                        class="btn btn-ghost-secondary btn-icon btn-sm"
                        title="Regenerate token"
                        @click="regenerateToken(host)"
                      >
                        <IconRefresh :size="16" />
                      </button>
                      <button
                        class="btn btn-ghost-secondary btn-icon btn-sm text-danger"
                        title="Delete"
                        @click="deleteHost(host)"
                      >
                        <IconTrash :size="16" />
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Router setup guide -->
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Router configuration</h3>
          </div>
          <div class="card-body">
            <p class="text-muted small mb-3">
              After creating a host, configure your router with the following settings.
              Use the hostname as username and the token as password.
            </p>

            <p class="text-muted small mb-3">
              Use the <strong>FQDN</strong> shown at host creation (e.g. <code>home.example.com</code>) — without a trailing dot — as both username and hostname in all examples below.
            </p>

            <!-- FRITZ!Box -->
            <h4 class="mb-2">FRITZ!Box</h4>
            <ol class="text-muted small mb-4">
              <li>Internet → Freigaben → DynDNS</li>
              <li>DynDNS aktivieren, Anbieter: <strong>Benutzerdefiniert</strong></li>
              <li>Update-URL: <code>{{ origin }}/nic/update?hostname=&lt;domain&gt;&amp;myip=&lt;ipaddr&gt;</code></li>
              <li>Domainname: FQDN of your host, e.g. <code>home.example.com</code></li>
              <li>Benutzername: same FQDN, e.g. <code>home.example.com</code></li>
              <li>Kennwort: your token</li>
            </ol>

            <!-- Synology -->
            <h4 class="mb-2">Synology DSM</h4>
            <ol class="text-muted small mb-4">
              <li>Control Panel → External Access → DDNS → Add</li>
              <li>Service provider: <strong>Customized</strong></li>
              <li>Query URL: <code>{{ origin }}/nic/update?hostname=__HOSTNAME__&amp;myip=__MYIP__</code></li>
              <li>Hostname: FQDN of your host, e.g. <code>home.example.com</code></li>
              <li>Username/Email: same FQDN &nbsp; Password: your token</li>
            </ol>

            <!-- OpenWrt / ddclient -->
            <h4 class="mb-2">ddclient / OpenWrt</h4>
            <pre class="bg-dark text-white rounded p-3 overflow-auto mb-4" style="font-size:0.78rem;">protocol=dyndns2
use=web, web=checkip.dyndns.org
server={{ origin.replace('https://', '').replace('http://', '') }}
login=home.example.com
password=&lt;your-token&gt;
home.example.com</pre>

            <!-- curl -->
            <h4 class="mb-2">Manual / curl</h4>
            <pre class="bg-dark text-white rounded p-3 overflow-auto" style="font-size:0.78rem;">curl -u "home.example.com:&lt;token&gt;" \
  "{{ origin }}/nic/update?hostname=home.example.com&amp;myip=1.2.3.4"</pre>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

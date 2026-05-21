<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import {
  IconHome,
  IconWorld,
  IconUsers,
  IconClipboardList,
  IconChartBar,
  IconSettings,
  IconBuilding,
  IconHelp,
  IconUserCog,
  IconShieldCheck,
  IconTemplate,
  IconWifi,
} from '@tabler/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'

const route = useRoute()
const auth = useAuthStore()
const settingsStore = useSettingsStore()

onMounted(() => {
  settingsStore.fetchPublicSettings()
})

const nav = computed(() => [
  { name: 'Dashboard', to: '/dashboard', icon: IconHome },
  { name: 'Zones', to: '/zones', icon: IconWorld },
  ...(auth.isAdmin ? [{ name: 'Zone Templates', to: '/templates', icon: IconTemplate }] : []),
  ...(auth.isAdmin
    ? [
        { name: 'Users', to: '/users', icon: IconUsers },
        { name: 'Accounts', to: '/accounts', icon: IconBuilding },
        { name: 'Permissions', to: '/admin/permissions', icon: IconShieldCheck },
        { name: 'Audit Log', to: '/audit', icon: IconClipboardList },
        { name: 'Statistics', to: '/stats', icon: IconChartBar },
        ...(auth.isSuperadmin ? [{ name: 'Global Settings', to: '/settings', icon: IconSettings }] : []),
      ]
    : []),
  ...(settingsStore.dyndnsEnabled ? [{ name: 'Dynamic DNS', to: '/dyndns', icon: IconWifi }] : []),
  { name: 'User Settings', to: '/user-settings', icon: IconUserCog },
  { name: 'Help', to: '/help', icon: IconHelp },
])

function isActive(to: string): boolean {
  return route.path === to || route.path.startsWith(to + '/')
}
</script>

<template>
  <aside class="navbar navbar-vertical navbar-expand-lg" data-bs-theme="dark">
    <div class="container-fluid">
      <button
        class="navbar-toggler"
        type="button"
        data-bs-toggle="collapse"
        data-bs-target="#sidebar-menu"
      >
        <span class="navbar-toggler-icon" />
      </button>

      <h1 class="navbar-brand navbar-brand-autodark">
        <RouterLink to="/dashboard" class="d-flex align-items-center gap-2 text-decoration-none text-white">
          <IconWorld :size="24" />
          <span class="fw-semibold">FloriDNS</span>
        </RouterLink>
      </h1>

      <div id="sidebar-menu" class="collapse navbar-collapse">
        <ul class="navbar-nav pt-lg-3">
          <li v-for="item in nav" :key="item.to" class="nav-item">
            <RouterLink
              :to="item.to"
              class="nav-link"
              :class="{ active: isActive(item.to) }"
            >
              <span class="nav-link-icon d-md-none d-lg-inline-block">
                <component :is="item.icon" :size="20" />
              </span>
              <span class="nav-link-title">{{ item.name }}</span>
            </RouterLink>
          </li>
        </ul>

        <div class="mt-auto">
          <div class="pt-3 pb-2 px-3 border-top">
            <div class="d-flex align-items-center gap-2">
              <span
                class="avatar avatar-sm"
                style="background-color: var(--tblr-primary); color: #fff; font-weight: 600;"
              >
                {{ auth.user?.username?.charAt(0).toUpperCase() ?? '?' }}
              </span>
              <div>
                <div class="fw-medium lh-1">{{ auth.user?.username }}</div>
                <div class="small text-secondary mt-1 text-uppercase">{{ auth.user?.role }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

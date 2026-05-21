<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { IconSun, IconMoon, IconLogout, IconSearch } from '@tabler/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'

const router = useRouter()
const auth = useAuthStore()
const theme = useThemeStore()
const searchQuery = ref('')

async function logout() {
  await auth.logout()
  router.push('/login')
}

function submitSearch() {
  const q = searchQuery.value.trim()
  if (!q) return
  router.push({ path: '/search', query: { q } })
  searchQuery.value = ''
}
</script>

<template>
  <header class="navbar navbar-expand-md d-none d-lg-flex d-print-none">
    <div class="container-xl">
      <!-- Search — left/center -->
      <div class="navbar-nav flex-fill">
        <form class="d-flex" style="max-width: 480px;" @submit.prevent="submitSearch">
          <div class="input-group">
            <span class="input-group-text">
              <IconSearch :size="16" class="text-muted" />
            </span>
            <input
              v-model="searchQuery"
              type="search"
              class="form-control"
              placeholder="Search zones and records…"
              @keydown.enter="submitSearch"
            />
          </div>
        </form>
      </div>

      <!-- Right actions -->
      <div class="navbar-nav flex-row flex-nowrap align-items-center order-md-last flex-shrink-0">
        <!-- Dark mode toggle -->
        <div class="nav-item d-flex align-items-center me-1">
          <a href="#" class="nav-link px-0" :title="theme.isDark ? 'Enable light mode' : 'Enable dark mode'" @click.prevent="theme.toggle()">
            <IconSun v-if="theme.isDark" :size="20" />
            <IconMoon v-else :size="20" />
          </a>
        </div>

        <!-- Logout -->
        <div class="nav-item d-flex align-items-center border-start ms-2 ps-3">
          <a
            href="#"
            class="nav-link px-0 text-secondary"
            title="Sign out"
            @click.prevent="logout"
          >
            <IconLogout :size="20" />
          </a>
        </div>
      </div>
    </div>
  </header>
</template>

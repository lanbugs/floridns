import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/auth/callback',
      name: 'oidc-callback',
      component: () => import('@/views/OidcCallbackView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('@/components/layout/AppLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          redirect: '/dashboard',
        },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
        },
        {
          path: 'zones',
          name: 'zones',
          component: () => import('@/views/ZonesView.vue'),
        },
        {
          path: 'zones/:id',
          name: 'zone-detail',
          component: () => import('@/views/ZoneDetailView.vue'),
          props: true,
        },
        {
          path: 'zones/:id/history',
          name: 'zone-history',
          component: () => import('@/views/ZoneHistoryView.vue'),
          props: true,
        },
        {
          path: 'search',
          name: 'search',
          component: () => import('@/views/SearchView.vue'),
        },
        {
          path: 'users',
          name: 'users',
          component: () => import('@/views/UsersView.vue'),
          meta: { requiresAdmin: true },
        },
        {
          path: 'accounts',
          name: 'accounts',
          component: () => import('@/views/AccountsView.vue'),
          meta: { requiresAdmin: true },
        },
        {
          path: 'audit',
          name: 'audit',
          component: () => import('@/views/AuditView.vue'),
          meta: { requiresAdmin: true },
        },
        {
          path: 'stats',
          name: 'stats',
          component: () => import('@/views/StatsView.vue'),
          meta: { requiresAdmin: true },
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/SettingsView.vue'),
          meta: { requiresSuperadmin: true },
        },
        {
          path: 'admin/permissions',
          name: 'admin-permissions',
          component: () => import('@/views/AdminPermissionsView.vue'),
          meta: { requiresAdmin: true },
        },
        {
          path: 'templates',
          name: 'templates',
          component: () => import('@/views/ZoneTemplatesView.vue'),
          meta: { requiresAdmin: true },
        },
        {
          path: 'dyndns',
          name: 'dyndns',
          component: () => import('@/views/DynDnsView.vue'),
        },
        {
          path: 'user-settings',
          name: 'user-settings',
          component: () => import('@/views/UserSettingsView.vue'),
        },
        {
          path: 'api-tokens',
          redirect: '/user-settings',
        },
        {
          path: 'security',
          redirect: '/user-settings',
        },
        {
          path: 'help',
          name: 'help',
          component: () => import('@/views/HelpView.vue'),
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.meta.public) return true

  if (!auth.accessToken) {
    // Try refreshing via httpOnly cookie before sending to login
    const refreshed = await auth.refreshAccessToken()
    if (!refreshed) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }

  if (!auth.user) {
    await auth.fetchMe()
    if (!auth.user) {
      return { name: 'login' }
    }
  }

  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { name: 'dashboard' }
  }

  if (to.meta.requiresSuperadmin && !auth.isSuperadmin) {
    return { name: 'dashboard' }
  }

  if (auth.user?.totp_required && to.name !== 'user-settings') {
    return { name: 'user-settings' }
  }

  return true
})

export default router

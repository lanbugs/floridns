<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { IconWorld } from '@tabler/icons-vue'
import { api, useApiError } from '@/composables/useApi'
import { useAuthStore } from '@/stores/auth'
import type { LoginResponse } from '@/types'

const router = useRouter()
const auth = useAuthStore()
const error = ref('')

onMounted(async () => {
  const params = new URLSearchParams(window.location.search)
  const code = params.get('code')
  const state = params.get('state')
  const codeVerifier = sessionStorage.getItem('oidc_code_verifier')
  const redirectUri = sessionStorage.getItem('oidc_redirect_uri')

  sessionStorage.removeItem('oidc_code_verifier')
  sessionStorage.removeItem('oidc_redirect_uri')

  if (!code || !state || !codeVerifier || !redirectUri) {
    error.value = 'Incomplete OIDC callback parameters. Please try again.'
    return
  }

  try {
    const resp = await api.post<LoginResponse>('/auth/oidc/callback', {
      code,
      state,
      code_verifier: codeVerifier,
      redirect_uri: redirectUri,
    })

    const result = await auth.handleOidcResponse(resp)
    if (result === 'totp') {
      await router.push('/login')
    } else {
      await router.push('/dashboard')
    }
  } catch (e) {
    error.value = useApiError(e)
  }
})
</script>

<template>
  <div class="page page-center">
    <div class="container container-tight py-4">
      <div class="text-center mb-4">
        <IconWorld class="text-primary" :size="48" />
        <h1 class="h1 mt-3">FloriDNS</h1>
      </div>
      <div class="card card-md">
        <div class="card-body text-center py-5">
          <template v-if="!error">
            <div class="spinner-border text-primary mb-3" />
            <p class="text-muted">Completing sign-in…</p>
          </template>
          <template v-else>
            <p class="text-danger mb-3">{{ error }}</p>
            <a href="/login" class="btn btn-secondary">Back to login</a>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

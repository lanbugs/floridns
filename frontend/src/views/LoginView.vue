<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { IconWorld, IconShieldCheck, IconFingerprint } from '@tabler/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { api, useApiError } from '@/composables/useApi'
import { usePasskey } from '@/composables/usePasskey'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const toast = useToast()
const { beginPasskeyLogin } = usePasskey()

const step = ref<'credentials' | 'totp'>('credentials')
const username = ref('')
const password = ref('')
const totpCode = ref('')
const loading = ref(false)
const passkeyLoading = ref(false)
const oidcEnabled = ref(false)
const oidcLoading = ref(false)

onMounted(async () => {
  // Show TOTP step directly if returning from OIDC with totp_required
  if (auth.totpToken) {
    step.value = 'totp'
  }
  try {
    const info = await api.get<{ enabled: boolean }>('/auth/oidc/info')
    oidcEnabled.value = info.enabled
  } catch {
    // OIDC not available — ignore
  }
})

async function submitCredentials() {
  loading.value = true
  try {
    const result = await auth.login(username.value, password.value)
    if (result === 'totp') {
      step.value = 'totp'
    } else {
      redirectAfterLogin()
    }
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    loading.value = false
  }
}

async function submitTotp() {
  loading.value = true
  try {
    await auth.verifyTotp(totpCode.value)
    redirectAfterLogin()
  } catch (e) {
    toast.error(useApiError(e))
    totpCode.value = ''
  } finally {
    loading.value = false
  }
}

function redirectAfterLogin() {
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
  router.push(redirect)
}

function backToCredentials() {
  step.value = 'credentials'
  totpCode.value = ''
}

async function loginWithPasskey() {
  passkeyLoading.value = true
  try {
    const resp = await beginPasskeyLogin()
    await auth.loginWithPasskey(resp)
    redirectAfterLogin()
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    passkeyLoading.value = false
  }
}

async function loginWithOidc() {
  oidcLoading.value = true
  try {
    const { auth_url, code_verifier } = await api.get<{ auth_url: string; code_verifier: string }>(
      '/auth/oidc/authorize',
    )
    const redirectUri = window.location.origin + '/auth/callback'
    sessionStorage.setItem('oidc_code_verifier', code_verifier)
    sessionStorage.setItem('oidc_redirect_uri', redirectUri)
    window.location.href = auth_url
  } catch (e) {
    toast.error(useApiError(e))
    oidcLoading.value = false
  }
}
</script>

<template>
  <div class="page page-center">
    <div class="container container-tight py-4">
      <div class="text-center mb-4">
        <div class="mb-3">
          <IconWorld class="text-primary" :size="48" />
        </div>
        <h1 class="h1">FloriDNS</h1>
        <p class="text-muted">PowerDNS Web Frontend</p>
      </div>

      <div class="card card-md">
        <div class="card-body">
          <!-- Step 1: credentials -->
          <template v-if="step === 'credentials'">
            <h2 class="card-title text-center mb-4">Sign in</h2>
            <form @submit.prevent="submitCredentials">
              <div class="mb-3">
                <label class="form-label">Username</label>
                <input
                  v-model="username"
                  type="text"
                  required
                  autocomplete="username"
                  class="form-control"
                  placeholder="admin"
                />
              </div>
              <div class="mb-3">
                <label class="form-label">Password</label>
                <input
                  v-model="password"
                  type="password"
                  required
                  autocomplete="current-password"
                  class="form-control"
                  placeholder="••••••••"
                />
              </div>
              <div class="form-footer">
                <button
                  type="submit"
                  class="btn btn-primary w-100 d-inline-flex align-items-center justify-content-center gap-1"
                  :disabled="loading"
                >
                  <span v-if="loading" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                  Sign in
                </button>
              </div>
            </form>
            <div class="hr-text my-3">or</div>
            <button
              class="btn btn-outline-secondary w-100 d-inline-flex align-items-center justify-content-center gap-1"
              :disabled="passkeyLoading"
              @click="loginWithPasskey"
            >
              <span v-if="passkeyLoading" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
              <IconFingerprint v-else :size="16" />
              Sign in with Passkey
            </button>
            <template v-if="oidcEnabled">
              <div class="hr-text my-3">or</div>
              <button
                class="btn btn-outline-secondary w-100 d-inline-flex align-items-center justify-content-center gap-1"
                :disabled="oidcLoading"
                @click="loginWithOidc"
              >
                <span v-if="oidcLoading" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                Login with SSO
              </button>
            </template>
          </template>

          <!-- Step 2: TOTP -->
          <template v-else>
            <div class="text-center mb-3">
              <IconShieldCheck class="text-primary" :size="40" />
            </div>
            <h2 class="card-title text-center mb-1">Two-factor authentication</h2>
            <p class="text-muted text-center mb-4">Enter the 6-digit code from your authenticator app.</p>
            <form @submit.prevent="submitTotp">
              <div class="mb-3">
                <label class="form-label">Authentication code</label>
                <input
                  v-model="totpCode"
                  type="text"
                  inputmode="numeric"
                  pattern="[0-9]{6}"
                  maxlength="6"
                  required
                  autocomplete="one-time-code"
                  class="form-control text-center font-monospace fs-3"
                  placeholder="000000"
                  autofocus
                />
              </div>
              <div class="form-footer d-flex gap-2">
                <button type="button" class="btn btn-secondary w-50" @click="backToCredentials">
                  Back
                </button>
                <button
                  type="submit"
                  class="btn btn-primary w-50 d-inline-flex align-items-center justify-content-center gap-1"
                  :disabled="loading || totpCode.length !== 6"
                >
                  <span v-if="loading" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                  Verify
                </button>
              </div>
            </form>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

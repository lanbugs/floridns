<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import QRCode from 'qrcode'
import { IconShieldCheck, IconShieldOff, IconShieldLock } from '@tabler/icons-vue'
import { api, useApiError } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const toast = useToast()

const loading = ref(false)

// Setup state
const setupMode = ref(false)
const setupSecret = ref('')
const setupUri = ref('')
const setupCode = ref('')
const enabling = ref(false)
const canvasRef = ref<HTMLCanvasElement | null>(null)

// Disable state
const disableMode = ref(false)
const disableCode = ref('')
const disabling = ref(false)

async function startSetup() {
  loading.value = true
  try {
    const data = await api.get<{ secret: string; uri: string }>('/users/me/totp/setup')
    setupSecret.value = data.secret
    setupUri.value = data.uri
    setupMode.value = true
    await nextTick()
    if (canvasRef.value) {
      await QRCode.toCanvas(canvasRef.value, data.uri, { width: 220, margin: 2 })
    }
  } catch (e) {
    toast.error(useApiError(e))
  } finally {
    loading.value = false
  }
}

function cancelSetup() {
  setupMode.value = false
  setupSecret.value = ''
  setupUri.value = ''
  setupCode.value = ''
}

async function enableTotp() {
  enabling.value = true
  try {
    await api.post('/users/me/totp/enable', { secret: setupSecret.value, code: setupCode.value })
    await auth.fetchMe()
    cancelSetup()
    toast.success('Two-factor authentication enabled')
  } catch (e) {
    toast.error(useApiError(e))
    setupCode.value = ''
  } finally {
    enabling.value = false
  }
}

function startDisable() {
  disableMode.value = true
}

function cancelDisable() {
  disableMode.value = false
  disableCode.value = ''
}

async function disableTotp() {
  disabling.value = true
  try {
    await api.post('/users/me/totp/disable', { code: disableCode.value })
    await auth.fetchMe()
    cancelDisable()
    toast.success('Two-factor authentication disabled')
  } catch (e) {
    toast.error(useApiError(e))
    disableCode.value = ''
  } finally {
    disabling.value = false
  }
}

function copySecret() {
  navigator.clipboard.writeText(setupSecret.value)
}

onMounted(async () => {
  await auth.fetchMe()
})
</script>

<template>
  <div>
    <div class="page-header d-print-none">
      <div class="container-xl">
        <div class="row g-2 align-items-center">
          <div class="col">
            <div class="page-pretitle">Account</div>
            <h2 class="page-title">Security</h2>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">
        <div class="row justify-content-center">
          <div class="col-lg-6">

            <!-- Forced TOTP banner -->
            <div v-if="auth.user?.totp_required && !auth.user?.totp_enabled" class="alert alert-warning mb-3">
              <div class="d-flex align-items-center gap-2">
                <IconShieldLock :size="20" />
                <strong>Two-factor authentication is required.</strong>
              </div>
              <div class="mt-1 text-muted">
                Your administrator requires all accounts to use 2FA. Please set it up below before continuing.
              </div>
            </div>

            <!-- Current status card -->
            <div class="card mb-3">
              <div class="card-header">
                <h3 class="card-title">Two-factor authentication (TOTP)</h3>
              </div>
              <div class="card-body">
                <div class="d-flex align-items-center gap-3 mb-3">
                  <span
                    class="avatar"
                    :style="auth.user?.totp_enabled
                      ? 'background-color: var(--tblr-green); color: #fff;'
                      : 'background-color: var(--tblr-secondary); color: #fff;'"
                  >
                    <IconShieldCheck v-if="auth.user?.totp_enabled" :size="22" />
                    <IconShieldOff v-else :size="22" />
                  </span>
                  <div>
                    <div class="fw-semibold">
                      {{ auth.user?.totp_enabled ? 'Enabled' : 'Not enabled' }}
                    </div>
                    <div class="text-muted small">
                      {{ auth.user?.totp_enabled
                        ? 'Your account is protected with a time-based one-time password.'
                        : 'Add an extra layer of security to your account.' }}
                    </div>
                  </div>
                </div>

                <!-- Enable flow -->
                <template v-if="!auth.user?.totp_enabled">
                  <button
                    v-if="!setupMode"
                    class="btn btn-primary d-inline-flex align-items-center gap-1"
                    :disabled="loading"
                    @click="startSetup"
                  >
                    <span v-if="loading" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                    Set up 2FA
                  </button>

                  <div v-else>
                    <hr class="my-3" />
                    <p class="text-muted mb-3">
                      Scan this QR code with your authenticator app (Google Authenticator, Aegis, Bitwarden, etc.),
                      then enter the 6-digit code to confirm.
                    </p>
                    <div class="text-center mb-3">
                      <canvas ref="canvasRef" style="border-radius: 8px;" />
                    </div>
                    <div class="mb-3">
                      <label class="form-label">Manual entry key</label>
                      <div class="input-group">
                        <input :value="setupSecret" readonly class="form-control font-monospace" />
                        <button
                          class="btn btn-outline-secondary"
                          type="button"
                          @click="copySecret"
                        >
                          Copy
                        </button>
                      </div>
                    </div>
                    <div class="mb-3">
                      <label class="form-label">Verification code</label>
                      <input
                        v-model="setupCode"
                        type="text"
                        inputmode="numeric"
                        pattern="[0-9]{6}"
                        maxlength="6"
                        class="form-control font-monospace"
                        placeholder="000000"
                        autocomplete="one-time-code"
                      />
                    </div>
                    <div class="d-flex gap-2">
                      <button class="btn btn-secondary" @click="cancelSetup">Cancel</button>
                      <button
                        class="btn btn-primary d-inline-flex align-items-center gap-1"
                        :disabled="enabling || setupCode.length !== 6"
                        @click="enableTotp"
                      >
                        <span v-if="enabling" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                        Enable 2FA
                      </button>
                    </div>
                  </div>
                </template>

                <!-- Disable flow -->
                <template v-else>
                  <button
                    v-if="!disableMode"
                    class="btn btn-outline-danger d-inline-flex align-items-center gap-1"
                    @click="startDisable"
                  >
                    Disable 2FA
                  </button>

                  <div v-else>
                    <hr class="my-3" />
                    <p class="text-muted mb-3">
                      Enter your current authenticator code to confirm disabling two-factor authentication.
                    </p>
                    <div class="mb-3">
                      <label class="form-label">Current code</label>
                      <input
                        v-model="disableCode"
                        type="text"
                        inputmode="numeric"
                        pattern="[0-9]{6}"
                        maxlength="6"
                        class="form-control font-monospace"
                        placeholder="000000"
                        autocomplete="one-time-code"
                      />
                    </div>
                    <div class="d-flex gap-2">
                      <button class="btn btn-secondary" @click="cancelDisable">Cancel</button>
                      <button
                        class="btn btn-danger d-inline-flex align-items-center gap-1"
                        :disabled="disabling || disableCode.length !== 6"
                        @click="disableTotp"
                      >
                        <span v-if="disabling" class="spinner-border spinner-border-sm" style="width:0.9em;height:0.9em;" />
                        Disable 2FA
                      </button>
                    </div>
                  </div>
                </template>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  </div>
</template>

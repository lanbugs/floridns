<script setup lang="ts">
import { useNotificationStore } from '@/stores/notifications'

const store = useNotificationStore()

const alertClass: Record<string, string> = {
  success: 'alert-success',
  error: 'alert-danger',
  warning: 'alert-warning',
  info: 'alert-info',
}
</script>

<template>
  <div
    class="toast-container position-fixed bottom-0 end-0 p-3"
    style="z-index: 1090;"
  >
    <TransitionGroup
      enter-active-class="transition-all duration-300"
      leave-active-class="transition-all duration-200"
      enter-from-class="opacity-0 translate-y-2"
      leave-to-class="opacity-0"
    >
      <div
        v-for="n in store.notifications"
        :key="n.id"
        class="alert mb-2 d-flex align-items-center justify-content-between shadow"
        :class="alertClass[n.type]"
        role="alert"
      >
        <span>{{ n.message }}</span>
        <button type="button" class="btn-close ms-3" @click="store.remove(n.id)" />
      </div>
    </TransitionGroup>
  </div>
</template>

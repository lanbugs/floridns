import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Notification } from '@/types'

export const useNotificationStore = defineStore('notifications', () => {
  const notifications = ref<Notification[]>([])

  function add(notification: Omit<Notification, 'id'>): void {
    const id = crypto.randomUUID()
    notifications.value.push({ ...notification, id })
    const timeout = notification.timeout ?? 4000
    if (timeout > 0) {
      setTimeout(() => remove(id), timeout)
    }
  }

  function remove(id: string): void {
    notifications.value = notifications.value.filter((n) => n.id !== id)
  }

  function success(message: string): void {
    add({ type: 'success', message })
  }

  function error(message: string): void {
    add({ type: 'error', message, timeout: 6000 })
  }

  function warning(message: string): void {
    add({ type: 'warning', message })
  }

  function info(message: string): void {
    add({ type: 'info', message })
  }

  return { notifications, add, remove, success, error, warning, info }
})

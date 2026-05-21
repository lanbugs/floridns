import { useNotificationStore } from '@/stores/notifications'

export function useToast() {
  const store = useNotificationStore()
  return {
    success: store.success.bind(store),
    error: store.error.bind(store),
    warning: store.warning.bind(store),
    info: store.info.bind(store),
  }
}

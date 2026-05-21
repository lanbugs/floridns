import '@tabler/core/dist/css/tabler.min.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)

// Initialize theme before mount so there's no flash
import('@/stores/theme').then(({ useThemeStore }) => useThemeStore())

app.mount('#app')

<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppSidebar from './AppSidebar.vue'
import AppHeader from './AppHeader.vue'
import AppFooter from './AppFooter.vue'
import AppToastContainer from '@/components/ui/AppToastContainer.vue'
</script>

<template>
  <div class="page">
    <AppSidebar />
    <AppHeader />
    <div class="page-wrapper">
      <RouterView />
      <AppFooter />
    </div>
  </div>
  <AppToastContainer />
</template>

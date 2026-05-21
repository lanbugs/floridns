<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
    size?: 'sm' | 'md' | 'lg'
    loading?: boolean
    disabled?: boolean
    type?: 'button' | 'submit' | 'reset'
  }>(),
  { variant: 'primary', size: 'md', type: 'button' },
)
</script>

<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :class="[
      'btn d-inline-flex align-items-center gap-1',
      variant === 'secondary' ? 'btn-secondary' :
      variant === 'ghost'     ? 'btn-ghost-secondary' :
      variant === 'danger'    ? 'btn-danger' : 'btn-primary',
      size === 'sm' ? 'btn-sm' : size === 'lg' ? 'btn-lg' : '',
    ]"
  >
    <span
      v-if="loading"
      class="spinner-border spinner-border-sm"
      style="width:0.9em;height:0.9em;"
    />
    <slot />
  </button>
</template>

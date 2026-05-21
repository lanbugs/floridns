<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'blue' | 'green' | 'yellow' | 'red' | 'gray'
  }>(),
  { variant: 'gray' },
)
</script>

<template>
  <span
    :class="[
      'badge',
      variant === 'blue'   ? 'bg-blue text-blue-fg' :
      variant === 'green'  ? 'bg-green text-green-fg' :
      variant === 'yellow' ? 'bg-yellow text-yellow-fg' :
      variant === 'red'    ? 'bg-red text-red-fg' :
      'bg-secondary text-secondary-fg',
    ]"
  >
    <slot />
  </span>
</template>

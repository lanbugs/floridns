<script setup lang="ts">
defineProps<{
  title: string
  modelValue: boolean
  size?: 'sm' | 'md' | 'lg' | 'xl'
}>()

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
function close() {
  emit('update:modelValue', false)
}
</script>

<template>
  <Teleport to="body">
    <template v-if="modelValue">
      <div
        class="modal modal-blur fade show"
        style="display: block;"
        tabindex="-1"
        role="dialog"
        @click.self="close"
      >
        <div
          class="modal-dialog modal-dialog-centered modal-dialog-scrollable"
          :class="[
            size === 'xl' ? 'modal-xl' :
            size === 'lg' ? 'modal-lg' :
            size === 'sm' ? 'modal-sm' : '',
          ]"
        >
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">{{ title }}</h5>
              <button type="button" class="btn-close" @click="close" />
            </div>
            <div class="modal-body">
              <slot />
            </div>
            <div v-if="$slots.footer" class="modal-footer">
              <slot name="footer" />
            </div>
          </div>
        </div>
      </div>
      <div class="modal-backdrop fade show" @click="close" />
    </template>
  </Teleport>
</template>

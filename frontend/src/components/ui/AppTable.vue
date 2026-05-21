<script setup lang="ts" generic="T">
defineProps<{
  columns: { key: string; label: string; class?: string }[]
  rows: T[]
  loading?: boolean
  emptyMessage?: string
}>()
</script>

<template>
  <div class="card">
    <div class="table-responsive">
      <table class="table table-vcenter card-table">
        <thead>
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              :class="col.class"
            >
              {{ col.label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td :colspan="columns.length" class="text-center py-4">
              <div class="spinner-border text-primary" />
            </td>
          </tr>
          <tr v-else-if="rows.length === 0">
            <td :colspan="columns.length" class="text-center text-muted py-4">
              {{ emptyMessage ?? 'No entries found.' }}
            </td>
          </tr>
          <slot v-else />
        </tbody>
      </table>
    </div>
  </div>
</template>

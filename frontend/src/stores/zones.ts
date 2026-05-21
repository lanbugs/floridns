import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Zone, ZoneDetail, PaginatedResponse } from '@/types'
import { api } from '@/composables/useApi'

export const useZonesStore = defineStore('zones', () => {
  const zones = ref<Zone[]>([])
  const total = ref(0)
  const loading = ref(false)
  const currentZone = ref<ZoneDetail | null>(null)

  async function fetchZones(params?: {
    page?: number
    page_size?: number
    search?: string
    kind?: string
  }): Promise<void> {
    loading.value = true
    try {
      const query = new URLSearchParams()
      if (params?.page) query.set('page', String(params.page))
      if (params?.page_size) query.set('page_size', String(params.page_size))
      if (params?.search) query.set('search', params.search)
      if (params?.kind) query.set('kind', params.kind)

      const result = await api.get<PaginatedResponse<Zone>>(
        `/zones${query.toString() ? '?' + query.toString() : ''}`,
      )
      zones.value = result.items
      total.value = result.total
    } finally {
      loading.value = false
    }
  }

  async function fetchZone(zoneId: string): Promise<void> {
    loading.value = true
    try {
      currentZone.value = await api.get<ZoneDetail>(`/zones/${zoneId}`)
    } finally {
      loading.value = false
    }
  }

  async function createZone(data: {
    name: string
    kind: string
    nameservers: string[]
    masters: string[]
    account_id?: string | null
    template_id?: string | null
    comment?: string
  }): Promise<Zone> {
    return api.post<Zone>('/zones', data)
  }

  async function deleteZone(zoneId: string): Promise<void> {
    await api.delete(`/zones/${zoneId}`)
    zones.value = zones.value.filter((z) => z.id !== zoneId)
    total.value--
  }

  return {
    zones,
    total,
    loading,
    currentZone,
    fetchZones,
    fetchZone,
    createZone,
    deleteZone,
  }
})

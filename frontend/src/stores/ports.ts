/**
 * 端口视图状态管理。
 *
 * 同步:
 * - 当前激活的自定义区间 (activeRangeId)
 * - URL 查询参数 ?range=<id>
 * - PortAnalyzer 的分页游标
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchPorts, fetchCustomRanges } from '@/api'

export interface CustomRange {
  id: string
  name: string
  start_port: number
  end_port: number
  color: string
}

export const usePortsStore = defineStore('ports', () => {
  const route = useRoute()
  const router = useRouter()

  // 数据
  const portCards = ref([])
  const stats = ref({})
  const loading = ref(false)

  // 自定义区间
  const customRanges = ref<CustomRange[]>([])
  const activeRangeId = ref<string | null>(null)

  // 分页
  const nextCursor = ref<string | null>(null)
  const hasMore = ref(false)

  // 筛选
  const protocolFilter = ref('')
  const searchQuery = ref('')

  const currentRange = computed(() =>
    activeRangeId.value
      ? customRanges.value.find(r => r.id === activeRangeId.value)
      : null
  )

  async function loadRanges() {
    const res = await fetchCustomRanges()
    if (res.success) {
      customRanges.value = res.data
    }
  }

  async function loadData(append = false) {
    if (!append) {
      portCards.value = []
      nextCursor.value = null
    }

    loading.value = true
    try {
      const params: any = {
        start_port: activeRangeId.value
          ? undefined
          : 1,
        end_port: activeRangeId.value ? undefined : 65535,
        protocol: protocolFilter.value || undefined,
        search: searchQuery.value || undefined,
      }
      if (activeRangeId.value) {
        params.range_id = activeRangeId.value
      }
      if (nextCursor.value) {
        params.cursor = nextCursor.value
      }

      const res = await fetchPorts(params)
      if (res.success) {
        const d = res.data
        if (append) {
          portCards.value.push(...d.port_cards)
        } else {
          portCards.value = d.port_cards
        }
        stats.value = d
        nextCursor.value = d.next_cursor
        hasMore.value = d.has_more
      }
    } catch {
      // 静默
    } finally {
      loading.value = false
    }
  }

  function setActiveRange(id: string | null) {
    activeRangeId.value = id
    // 同步到 URL
    const q = { ...route.query }
    if (id) {
      q.range = id
    } else {
      delete q.range
    }
    router.replace({ query: q })
    loadData()
  }

  // 初始化从 URL 恢复
  function initFromRoute() {
    const rangeId = route.query.range as string | undefined
    if (rangeId) {
      activeRangeId.value = rangeId
    }
  }

  return {
    portCards,
    stats,
    loading,
    customRanges,
    activeRangeId,
    currentRange,
    nextCursor,
    hasMore,
    protocolFilter,
    searchQuery,
    loadRanges,
    loadData,
    setActiveRange,
    initFromRoute,
  }
})

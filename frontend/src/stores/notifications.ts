/**
 * 通知状态管理。
 * 前端从 /api/notifications 拉取，支持标记已读、清除。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchNotifications, markAllRead, clearRead } from '@/api'

export interface NotificationItem {
  id: string
  type: string
  level: 'info' | 'warning' | 'error'
  title: string
  message: string
  timestamp: number
  read: boolean
}

export const useNotificationStore = defineStore('notifications', () => {
  const items = ref<NotificationItem[]>([])
  const loading = ref(false)

  const unreadCount = computed(() => items.value.filter(n => !n.read).length)

  async function load() {
    loading.value = true
    try {
      const res = await fetchNotifications()
      if (res.success) {
        items.value = res.data.notifications || []
      }
    } catch (e) {
      // 静默失败 — 通知非关键
    } finally {
      loading.value = false
    }
  }

  async function markAllReadAction() {
    const res = await markAllRead()
    if (res.success) {
      items.value.forEach(n => (n.read = true))
    }
  }

  async function clearReadAction() {
    const res = await clearRead()
    if (res.success) {
      items.value = items.value.filter(n => !n.read)
    }
  }

  return {
    items,
    loading,
    unreadCount,
    load,
    markAllRead: markAllReadAction,
    clearRead: clearReadAction,
  }
})

/**
 * 通知状态管理。
 * 前端从 /api/notifications 拉取，支持标记已读、清除已读。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  fetchNotifications,
  markAllNotificationsRead,
  clearReadNotifications,
  type NotificationItem,
} from '@/api'

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
    } catch {
      // 静默失败 — 通知非关键
    } finally {
      loading.value = false
    }
  }

  function markRead(id: string) {
    const n = items.value.find(x => x.id === id)
    if (n) n.read = true
  }

  async function markAllReadAction() {
    const res = await markAllNotificationsRead()
    if (res.success) {
      items.value.forEach(n => (n.read = true))
    }
  }

  async function clearReadAction() {
    const res = await clearReadNotifications()
    if (res.success) {
      items.value = items.value.filter(n => !n.read)
    }
  }

  return {
    items,
    loading,
    unreadCount,
    load,
    markRead,
    markAllRead: markAllReadAction,
    clearRead: clearReadAction,
  }
})

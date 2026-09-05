<template>
  <div class="notifications-view">
    <div class="notifications-header">
      <h2>通知</h2>
      <div class="notifications-actions">
        <button
          v-if="items.length > 0 && hasUnread"
          class="btn"
          @click="markAllRead"
        >
          <Check class="w-4 h-4" /> 全部已读
        </button>
        <button
          v-if="items.filter(n => n.read).length > 0"
          class="btn btn--danger"
          @click="clearRead"
          title="清除已读"
        >
          <Trash2 class="w-4 h-4" /> 清除已读
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading-state">
      <RefreshCw class="spinning w-5 h-5" />
      <span>加载通知...</span>
    </div>

    <div v-else-if="items.length === 0" class="empty-state">
      <BellOff class="w-16 h-16" />
      <p class="empty-text">暂无通知</p>
    </div>

    <div v-else class="notifications-list">
      <div
        v-for="n in items"
        :key="n.id"
        class="notification-item"
        :class="{ unread: !n.read }"
        @click="openNotification(n)"
      >
        <div
          class="notification-indicator"
          :style="{ backgroundColor: levelColor(n.level) }"
        />
        <div class="notification-content">
          <div class="notification-title">
            <span class="notification-type-badge" :class="n.level">
              {{ typeLabel(n.type) }}
            </span>
            {{ n.title }}
          </div>
          <p class="notification-message">{{ n.message }}</p>
          <div class="notification-meta">
            <Clock class="w-3 h-3" />
            {{ formatTime(n.timestamp) }}
          </div>
        </div>

        <button
          v-if="!n.read"
          class="mark-read-btn"
          @click.stop="markRead(n.id)"
          title="标记为已读"
        >
          <Eye class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  BellOff, Check, Trash2,
  Clock, RefreshCw, Eye,
} from '@/icons'
import { useNotificationStore } from '@/stores/notifications'

const router = useRouter()
const store = useNotificationStore()

const items = computed(() => store.items.value)
const loading = computed(() => store.loading.value)
const hasUnread = computed(() => store.unreadCount.value > 0)

function levelColor(level: string) {
  const map: Record<string, string> = {
    info: 'var(--blue)',
    warning: 'var(--amber)',
    error: 'var(--red)',
  }
  return map[level] || 'var(--text-muted)'
}

function typeLabel(type: string) {
  const map: Record<string, string> = {
    port_open: '端口开启',
    port_close: '端口关闭',
    port_conflict: '冲突',
    container_start: '容器启动',
    container_stop: '容器停止',
  }
  return map[type] || type
}

function formatTime(ts: number): string {
  const d = new Date(ts)
  const now = Date.now()
  const diff = now - ts

  if (diff < 60000) return `${Math.floor(diff / 1000)}秒前`
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function openNotification(n: any) {
  if (!n.read) store.markRead(n.id)
  if (n.action) {
    router.push(n.action)
  }
}

function markRead(id: string) {
  store.markRead(id)
}

function markAllRead() {
  store.markAllRead()
}

function clearRead() {
  store.clearRead()
}

onMounted(() => store.load())
</script>

<style scoped>
.notifications-view {
  padding: 1.5rem;
  max-width: 800px;
  margin: 0 auto;
}

.notifications-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.notifications-actions {
  display: flex;
  gap: 0.5rem;
}

.notifications-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.notification-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.notification-item:hover {
  background: var(--bg-hover);
}

.notification-item.unread {
  background: var(--brand-soft);
  border-left: 3px solid var(--brand);
}

.notification-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 0.1rem;
}

.notification-content {
  flex: 1;
  min-width: 0;
}

.notification-title {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.2rem;
}

.notification-type-badge {
  font-size: 0.6rem;
  padding: 0.1rem 0.35rem;
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  color: var(--text-secondary);
  white-space: nowrap;
}

.notification-type-badge.info { color: var(--blue); }
.notification-type-badge.warning { color: var(--amber); }
.notification-type-badge.error { color: var(--red); }

.notification-message {
  font-size: 0.75rem;
  color: var(--text-secondary);
  line-height: 1.4;
  margin-bottom: 0.25rem;
  word-break: break-word;
}

.notification-meta {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.68rem;
  color: var(--text-muted);
}

.mark-read-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.2rem;
  color: var(--text-secondary);
  opacity: 0.5;
}

.mark-read-btn:hover {
  opacity: 1;
  color: var(--brand);
}

.loading-state {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 2rem;
  color: var(--text-secondary);
}

.empty-state {
  text-align: center;
  padding: 2.5rem;
  color: var(--text-muted);
}

.empty-text {
  margin-top: 0.75rem;
  font-size: 0.85rem;
}
</style>

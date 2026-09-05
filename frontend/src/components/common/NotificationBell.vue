<template>
  <div class="notification-bell" ref="container">
    <button
      class="bell-button"
      @click.stop="togglePanel"
      :title="`${unreadCount} 条未读通知`"
    >
      <Bell class="w-4 h-4" :class="{ filled: hasUnread }" />
      <span
        v-if="unreadCount > 0"
        class="bell-badge"
      >{{ unreadCount }}</span>
    </button>

    <!-- 下拉面板 -->
    <transition name="fade">
      <div
        v-if="panelOpen"
        class="notification-panel"
      >
        <div class="panel-header">
          <h4 class="panel-title">通知</h4>
          <button
            v-if="notifications.length > 0"
            class="mark-all-read"
            @click="markAllRead"
            title="全部标记为已读"
          >
            <Check class="w-3.5 h-3.5" /> 全部已读
          </button>
        </div>

        <div class="panel-body">
          <div v-if="notifications.length === 0" class="panel-empty">
            <BellOff class="w-10 h-10 text-muted" />
            <p class="empty-text">暂无通知</p>
          </div>

          <div
            v-for="n in notifications"
            :key="n.id"
            class="notification-item"
            :class="{ unread: !n.read }"
            @click="openNotification(n)"
          >
            <div class="notification-indicator" :style="{ backgroundColor: n.typeColor }" />
            <div class="notification-content">
              <div class="notification-title">{{ n.title }}</div>
              <div class="notification-time">{{ formatTime(n.timestamp) }}</div>
            </div>
            <button
              v-if="!n.read"
              class="mark-single-read"
              @click.stop="markRead(n.id)"
              title="标记为已读"
            >
              <div class="w-2 h-2 bg-blue-400 rounded-full" />
            </button>
          </div>
        </div>
        <div v-if="notifications.length > 0" class="panel-footer">
          <button
            class="view-all-btn"
            @click="viewAll"
          >
            查看全部
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { Bell, BellOff, Check } from '@/icons'
import { useNotificationStore } from '@/stores/notifications'

const useNotificationsStore = useNotificationStore

const container = ref<HTMLElement | null>(null)
const panelOpen = ref(false)

const notifications = useNotificationsStore()

const hasUnread = computed(() => notifications.unreadCount > 0)
const unreadCount = computed(() => notifications.unreadCount)

function togglePanel() {
  panelOpen.value = !panelOpen.value
  if (panelOpen.value) {
    notifications.markAllRead()
  }
}

function markAllRead() {
  notifications.markAllRead()
}

function markRead(id: string) {
  notifications.markRead(id)
}

function openNotification(n: any) {
  if (!n.read) notifications.markRead(n.id)
  if (n.action) {
    // 跳转到相关页面
    const router = useRouter()
    router.push(n.action)
  }
  panelOpen.value = false
}

function viewAll() {
  const router = useRouter()
  router.push('/notifications')
  panelOpen.value = false
}

function formatTime(ts: number) {
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

// 点击外部关闭
function onDocumentClick(e: MouseEvent) {
  if (container.value && !container.value.contains(e.target as Node)) {
    panelOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
})
</script>

<style scoped>
.notification-bell {
  position: relative;
  display: inline-block;
}

.bell-button {
  position: relative;
  background: none;
  border: none;
  border-radius: var(--radius-md);
  padding: 0.4rem;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.bell-button:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.bell-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  background: var(--red);
  color: #fff;
  border-radius: 999px;
  font-size: 0.6rem;
  font-weight: 700;
  padding: 1px 4px;
  min-width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.bell-button .filled {
  fill: var(--brand);
  color: var(--brand);
}

.notification-panel {
  position: absolute;
  top: 110%;
  right: 0;
  width: 320px;
  max-height: 480px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  z-index: 100;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border);
}

.panel-title {
  font-size: 0.9rem;
  font-weight: 600;
  margin: 0;
}

.mark-all-read {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 0.75rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.25rem;
  transition: color var(--transition-fast);
}

.mark-all-read:hover {
  color: var(--brand);
}

.panel-body {
  flex: 1;
  overflow-y: auto;
}

.panel-empty {
  text-align: center;
  padding: 1.5rem 1rem;
  color: var(--text-muted);
}

.notification-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.6rem 1rem;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.notification-item:hover {
  background: var(--bg-hover);
}

.notification-item.unread {
  background: var(--brand-soft);
}

.notification-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.notification-content {
  flex: 1;
  min-width: 0;
}

.notification-title {
  font-size: 0.8rem;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.notification-time {
  font-size: 0.65rem;
  color: var(--text-secondary);
}

.mark-single-read {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.2rem;
}

.panel-footer {
  padding: 0.5rem 1rem;
  border-top: 1px solid var(--border);
  text-align: center;
}

.view-all-btn {
  background: none;
  border: none;
  color: var(--brand);
  font-size: 0.8rem;
  cursor: pointer;
  transition: color var(--transition-fast);
}

.view-all-btn:hover {
  color: var(--brand-hover);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s var(--ease-out);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

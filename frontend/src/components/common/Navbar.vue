<template>
  <header class="navbar">
    <div class="navbar-left">
      <button
        v-if="showMenuButton"
        class="navbar-btn"
        @click="$emit('toggle-sidebar')"
        title="切换导航"
      >
        <Menu class="w-4 h-4" />
      </button>

      <h2 class="navbar-title">{{ title }}</h2>
    </div>

    <div class="navbar-right">
      <div class="navbar-search">
        <Search class="w-3.5 h-3.5 search-icon" />
        <input
          v-model="searchInput"
          type="text"
          class="search-input"
          :placeholder="searchPlaceholder"
          @input="onSearch"
        />
        <Keyboard class="w-3.5 h-3.5 shortcut-hint" />
      </div>

      <NotificationBell />

      <button
        class="navbar-btn"
        @click="$emit('refresh')"
        :title="`刷新 (${shortcutRefresh})`"
      >
        <RefreshCw
          class="w-4 h-4"
          :class="{ spinning: refreshing }"
        />
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Menu, Search, Keyboard, RefreshCw } from '@/icons'
import NotificationBell from './NotificationBell.vue'

const props = withDefaults(defineProps<{
  title?: string
  searchPlaceholder?: string
  showMenuButton?: boolean
  shortcutRefresh?: string
}>(), {
  title: 'PortView',
  searchPlaceholder: '搜索端口 / 服务...',
  showMenuButton: false,
  shortcutRefresh: 'Ctrl+R',
})

const searchInput = ref('')
const refreshing = ref(false)

watch(searchInput, (v) => {
  // 防抖
  clearTimeout(window.__portSearchTimer)
  window.__portSearchTimer = setTimeout(() => {
    // eslint-disable-next-line no-undef
    ;(window as any).__portSearchCallback?.(v)
  }, 300)
})

function onSearch() {
  // 父组件通过 provide/inject 或事件监听
  ;(window as any).__portSearchCallback?.(searchInput.value)
}
</script>

<style scoped>
.navbar {
  height: var(--header-height, 56px);
  background: var(--bg-base);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0 1rem;
  position: sticky;
  top: 0;
  z-index: 10;
}

.navbar-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.navbar-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  white-space: nowrap;
}

.navbar-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.navbar-btn {
  background: none;
  border: none;
  border-radius: var(--radius-md);
  padding: 0.4rem;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.navbar-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.navbar-search {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 0.4rem;
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  padding: 0.3rem 0.6rem 0.3rem 1.8rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-elevated);
  color: var(--text-primary);
  font-size: 0.8rem;
  width: 200px;
  transition: width var(--transition-fast);
}

.search-input:focus {
  outline: none;
  border-color: var(--brand);
  width: 280px;
  box-shadow: 0 0 0 2px var(--brand-soft);
}

.shortcut-hint {
  position: absolute;
  right: 0.4rem;
  color: var(--text-muted);
  font-size: 0.7rem;
}

.spinner {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>

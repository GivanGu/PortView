<template>
  <RouterView v-slot="{ Component }">
    <!-- 登录页全屏渲染 -->
    <template v-if="$route.name === 'Login'">
      <component :is="Component" />
    </template>
    <template v-else>
      <div class="app-layout">
        <!-- 侧边栏 -->
        <nav class="sidebar" :class="{ collapsed: sidebarCollapsed }">
          <div class="sidebar-header">
            <h1 class="sidebar-title">⚡ PortView</h1>
            <button
              class="sidebar-collapse-btn"
              @click="sidebarCollapsed = !sidebarCollapsed"
              :title="sidebarCollapsed ? '展开' : '折叠'"
            >
              <ChevronLeft v-if="!sidebarCollapsed" class="w-4 h-4" />
              <ChevronRight v-else class="w-4 h-4" />
            </button>
          </div>

          <div class="sidebar-nav">
            <RouterLink
              v-for="item in mainNavItems"
              :key="item.path"
              :to="item.path"
              class="sidebar-link"
              :class="{ active: $route.path === item.path }"
              :title="item.title"
            >
              <component :is="item.icon" class="sidebar-icon" />
              <span v-if="!sidebarCollapsed" class="sidebar-text">{{ item.label }}</span>
            </RouterLink>

            <!-- 自定义区间分组 -->
            <div class="sidebar-section">
              <div
                v-if="!sidebarCollapsed"
                class="sidebar-section-title"
              >
                🎯 自定义区间
                <RouterLink
                  to="/config"
                  class="sidebar-section-action"
                  title="管理区间"
                >
                  <Settings class="w-3.5 h-3.5" />
                </RouterLink>
              </div>

              <div v-for="range in customRanges" :key="range.id">
                <button
                  class="sidebar-link range-link"
                  :class="{ active: activeRangeId === range.id }"
                  @click="setActiveRange(range.id)"
                  :title="`${range.name} (${range.start_port}-${range.end_port})`"
                >
                  <span
                    class="range-dot"
                    :style="{ backgroundColor: range.color }"
                  />
                  <span
                    v-if="!sidebarCollapsed"
                    class="sidebar-text"
                    :title="range.name"
                  >{{ range.name }}</span
                  >
                  <span v-if="sidebarCollapsed" class="dot-only" />
                </button>
              </div>

              <RouterLink
                v-if="customRanges.length < 9 && !sidebarCollapsed"
                :to="{ path: '/config', query: { tab: 'ranges' } }"
                class="sidebar-link add-range-link"
              >
                <Plus class="w-4 h-4" />
                <span class="sidebar-text">添加区间</span>
              </RouterLink>
            </div>
          </div>

          <div class="sidebar-footer">
            <button
              class="sidebar-link"
              @click="logout"
              title="登出"
            >
              <LogOut class="w-4 h-4 sidebar-icon" />
              <span v-if="!sidebarCollapsed" class="sidebar-text">登出</span>
            </button>

            <button
              class="sidebar-link"
              @click="toggleTheme"
              :title="isDark ? '浅色模式' : '深色模式'"
            >
              <component
                :is="isDark ? Sun : Moon"
                class="w-4 h-4 sidebar-icon"
              />
              <span v-if="!sidebarCollapsed" class="sidebar-text">
                {{ isDark ? '浅色' : '深色' }}
              </span>
            </button>
          </div>
        </nav>

        <!-- 主内容 -->
        <div class="main-wrapper">
          <Navbar
            :title="pageTitle"
            :show-menu-button="isMobile"
            @toggle-sidebar="sidebarCollapsed = !sidebarCollapsed"
            @refresh="refreshCurrentView"
          />
          <main class="main-content">
            <component :is="Component" />
          </main>
        </div>
      </div>
    </template>
  </RouterView>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  Network,
  EyeOff,
  Settings,
  Plus,
  LogOut,
  Sun,
  Moon,
} from '@/icons'
import Navbar from '@/components/common/Navbar.vue'

import { useAuthStore } from '@/stores/auth'
import { usePortsStore } from '@/stores/ports'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const ports = usePortsStore()

const sidebarCollapsed = ref(false)
const isDark = ref(true)

const mainNavItems = [
  { path: '/overview', label: '概览', icon: LayoutDashboard, title: '概览' },
  { path: '/ports', label: '端口监控', icon: Network, title: '端口监控' },
  { path: '/hidden', label: '隐藏端口', icon: EyeOff, title: '隐藏端口' },
]

const pageTitle = computed(() => {
  const map: Record<string, string> = {
    overview: '端口概览',
    ports: '端口监控',
    hidden: '隐藏端口',
    config: '设置',
    notifications: '通知',
  }
  return map[route.path.slice(1)] || 'PortView'
})

const customRanges = computed(() => ports.customRanges)
const activeRangeId = computed({
  get: () => ports.activeRangeId,
  set: (v: string | null) => ports.setActiveRange(v),
})

const isMobile = computed(() => window.matchMedia('(max-width: 768px)').matches)

async function loadRanges() {
  await ports.loadRanges()
  ports.initFromRoute()
}

function setActiveRange(id: string | null) {
  ports.setActiveRange(id)
  router.replace('/ports')
}

function toggleTheme() {
  isDark.value = !isDark.value
  const html = document.documentElement
  html.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  localStorage.setItem('portview.theme', isDark.value ? 'dark' : 'light')
}

function logout() {
  auth.logout()
  router.replace('/login')
}

function refreshCurrentView() {
  // 触发当前视图刷新
  ports.loadData()
}

// 键盘快捷键
function onKeyDown(e: KeyboardEvent) {
  const target = e.target as HTMLElement
  const isInput = target?.tagName === 'INPUT' || target?.tagName === 'TEXTAREA'
  if (isInput) return

  switch (e.key) {
    case '/':
      e.preventDefault()
      // 搜索聚焦
      const searchInput = document.querySelector('.search-input') as HTMLInputElement
      searchInput?.focus()
      break
    case 'j':
      if (e.shiftKey) {
        e.preventDefault()
        // 向下滚动一页
        const container = document.querySelector('.main-content') as HTMLElement
        container?.scrollBy({ top: 200, behavior: 'smooth' })
      }
      break
    case 'k':
      if (e.shiftKey) {
        e.preventDefault()
        const container = document.querySelector('.main-content') as HTMLElement
        container?.scrollBy({ top: -200, behavior: 'smooth' })
      }
      break
    case 'g':
      if (e.shiftKey) {
        e.preventDefault()
        const container = document.querySelector('.main-content') as HTMLElement
        container?.scrollTo({ top: 0, behavior: 'smooth' })
      }
      break
    case 'G':
      e.preventDefault()
      const container = document.querySelector('.main-content') as HTMLElement
      container?.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
      break
    case 'Escape':
      // 切换到概览
      if (route.path !== '/overview') {
        router.replace('/overview')
      }
      break
  }
}

// 监听 `/` 弹出快捷键提示
function showShortcutsHint() {
  // 简单实现：创建临时提示
  const hint = document.createElement('div')
  hint.className = 'shortcuts-hint'
  hint.innerHTML = `
    <div class="hint-content">
      <kbd>/</kbd> 搜索  ·  <kbd>JK</kbd> 上下滚动  ·  <kbd>Esc</kbd> 回到首页  ·  <kbd>?</kbd> 帮助
    </div>
  `
  document.body.appendChild(hint)
  setTimeout(() => hint.remove(), 3000)
}

function onKeyDownGlobal(e: KeyboardEvent) {
  // 全局 `?` 显示快捷键
  if (e.key === '?' && !(e.target as HTMLElement)?.tagName.match(/INPUT|TEXTAREA|SELECT/)) {
    e.preventDefault()
    showShortcutsHint()
  }
  onKeyDown(e)
}

onMounted(() => {
  loadRanges()
  const savedTheme = localStorage.getItem('portview.theme')
  isDark.value = savedTheme !== 'light'
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  window.addEventListener('keydown', onKeyDownGlobal, true)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDownGlobal, true)
})
</script>

<style>
:root {
  --sidebar-width: 240px;
  --sidebar-width-collapsed: 60px;
  --header-height: 56px;
}

.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.main-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-content {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-base);
}

/* 侧边栏 */
.sidebar {
  width: var(--sidebar-width);
  background: var(--bg-base);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  transition: width var(--transition-normal);
  overflow: hidden;
}

.sidebar.collapsed {
  width: var(--sidebar-width-collapsed);
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem;
  border-bottom: 1px solid var(--border);
}

.sidebar-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.sidebar-collapse-btn {
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  padding: 0.25rem;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.sidebar-collapse-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.sidebar-link {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.55rem 0.9rem;
  margin: 0 0.5rem;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-decoration: none;
  transition: all var(--transition-fast);
  cursor: pointer;
  border: none;
  background: none;
  font-size: 0.85rem;
}

.sidebar-link:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.sidebar-link.active {
  background: var(--brand-soft);
  color: var(--brand);
}

.sidebar-icon {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
}

.sidebar-text {
  white-space: nowrap;
  overflow: hidden;
}

.sidebar-section {
  margin-top: 1rem;
}

.sidebar-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.4rem 0.9rem;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.sidebar-section-action {
  opacity: 0.5;
  transition: opacity var(--transition-fast);
}

.sidebar-section-action:hover {
  opacity: 1;
}

.range-link {
  padding-left: 1.2rem !important;
}

.range-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-only {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
}

.add-range-link {
  color: var(--green);
  padding-left: 1.2rem !important;
}

.sidebar-footer {
  padding: 0.5rem 0;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

/* 快捷键提示 */
.shortcuts-hint {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 0.6rem 0.9rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
  box-shadow: var(--shadow-lg);
  z-index: 9999;
}

.shortcuts-hint kbd {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.1rem 0.35rem;
  font-size: 0.7rem;
  color: var(--text-primary);
}
</style>

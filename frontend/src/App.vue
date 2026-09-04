<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { healthCheck } from '@/api'
import OverviewView from '@/components/OverviewView.vue'
import PortsView from '@/components/PortsView.vue'
import HiddenPortsView from '@/components/HiddenPortsView.vue'

type Tab = 'overview' | 'ports' | 'hidden'
type Theme = 'dark' | 'light'

const THEME_KEY = 'portview.theme'

const activeTab = ref<Tab>('overview')
const theme = ref<Theme>('dark')
const version = ref('')
const loading = ref(true)

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem(THEME_KEY)
    if (saved === 'light' || saved === 'dark') return saved
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

function applyTheme(t: Theme) {
  document.documentElement.setAttribute('data-theme', t)
  try {
    localStorage.setItem(THEME_KEY, t)
  } catch {
    /* 忽略隐私模式等写入失败 */
  }
}

function toggleTheme() {
  const next: Theme = theme.value === 'dark' ? 'light' : 'dark'
  theme.value = next
  applyTheme(next)
}

onMounted(async () => {
  theme.value = initialTheme()
  applyTheme(theme.value)
  try {
    const health = await healthCheck()
    version.value = health.version
  } catch {
    version.value = 'unknown'
  }
  loading.value = false
})

function switchTab(tab: Tab) {
  activeTab.value = tab
}
</script>

<template>
  <div class="app-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-logo">
        <div class="logo-icon">⚡</div>
        <span>PortView</span>
      </div>

      <nav class="sidebar-nav">
        <button
          class="nav-item"
          :class="{ active: activeTab === 'overview' }"
          @click="switchTab('overview')"
        >
          <span class="nav-icon">📊</span>
          <span>概览</span>
        </button>
        <button
          class="nav-item"
          :class="{ active: activeTab === 'ports' }"
          @click="switchTab('ports')"
        >
          <span class="nav-icon">📡</span>
          <span>端口监控</span>
        </button>
        <button
          class="nav-item"
          :class="{ active: activeTab === 'hidden' }"
          @click="switchTab('hidden')"
        >
          <span class="nav-icon">🙈</span>
          <span>隐藏端口</span>
        </button>
      </nav>

      <div class="sidebar-footer">
        <button
          class="theme-toggle"
          :title="theme === 'dark' ? '切换到亮色' : '切换到暗色'"
          @click="toggleTheme"
        >
          <span class="nav-icon">{{ theme === 'dark' ? '🌙' : '☀️' }}</span>
          <span>{{ theme === 'dark' ? '暗色模式' : '亮色模式' }}</span>
        </button>
        <div class="footer-line">PortView v{{ version }}</div>
        <div class="footer-line">端口监控与可视化</div>
      </div>
    </aside>

    <!-- 主内容 -->
    <main class="main-content">
      <OverviewView v-if="activeTab === 'overview'" />
      <PortsView v-else-if="activeTab === 'ports'" />
      <HiddenPortsView v-else />
    </main>
  </div>
</template>

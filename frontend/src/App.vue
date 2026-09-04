<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  LayoutDashboard,
  Network,
  StickyNote,
  EyeOff,
  Settings,
  Sun,
  Moon,
  Search,
  Languages,
  Activity,
} from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { setLocale } from '@/i18n'
import { fetchPorts, healthCheck } from '@/api'
import type { PortAnalysis } from '@/api'
import OverviewView from '@/components/OverviewView.vue'
import PortsView from '@/components/PortsView.vue'
import HiddenPortsView from '@/components/HiddenPortsView.vue'

type Tab = 'overview' | 'ports' | 'notes' | 'hidden' | 'settings'
type Theme = 'dark' | 'light'
type Lang = 'zh' | 'en'

const { t, locale } = useI18n()

const THEME_KEY = 'portview.theme'

const activeTab = ref<Tab>('overview')
const theme = ref<Theme>('dark')
const version = ref('')
const loading = ref(true)

// 状态栏实时指标
const stats = ref<{ used: number; available: number; containers: number }>({
  used: 0,
  available: 0,
  containers: 0,
})

const navItems = computed(() => [
  { id: 'overview' as Tab, icon: LayoutDashboard, label: t('nav.overview') },
  { id: 'ports' as Tab, icon: Network, label: t('nav.ports') },
  { id: 'notes' as Tab, icon: StickyNote, label: t('nav.notes') },
  { id: 'hidden' as Tab, icon: EyeOff, label: t('nav.hidden') },
  { id: 'settings' as Tab, icon: Settings, label: t('nav.settings') },
])

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
    /* ignore */
  }
}

function toggleTheme() {
  const next: Theme = theme.value === 'dark' ? 'light' : 'dark'
  theme.value = next
  applyTheme(next)
}

function toggleLang() {
  const next: Lang = locale.value === 'zh' ? 'en' : 'zh'
  locale.value = next
  setLocale(next)
}

const occupancyPct = computed(() => {
  const { used, available } = stats.value
  const total = used + available
  if (total <= 0) return 0
  return Math.round((used / total) * 100)
})

async function loadStats() {
  try {
    const res = await fetchPorts()
    const data = res.data as PortAnalysis
    if (res.success && data) {
      stats.value = {
        used: data.total_used ?? 0,
        available: data.total_available ?? 0,
        containers: data.docker_containers ?? 0,
      }
    }
  } catch {
    /* 后端不可用时保持空指标 */
  }
}

function switchTab(tab: Tab) {
  activeTab.value = tab
  if (tab === 'overview' || tab === 'ports') {
    loadStats()
  }
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
  loadStats()
})
</script>

<template>
  <div class="app-shell">
    <!-- 顶栏：logo + 搜索 + 主题/语言 -->
    <header class="topbar">
      <div class="topbar-brand">
        <div class="brand-mark"><Activity :size="18" /></div>
        <span class="brand-name">{{ t('app.name') }}</span>
      </div>

      <div class="topbar-search" role="search">
        <Search class="search-icon" :size="16" />
        <input type="text" :placeholder="t('topbar.searchPlaceholder')" aria-label="search" />
        <kbd class="kbd">{{ t('topbar.searchKbd') }}</kbd>
      </div>

      <div class="topbar-actions">
        <button class="icon-btn" :title="t('topbar.themeToggle')" @click="toggleTheme">
          <Sun v-if="theme === 'dark'" :size="18" />
          <Moon v-else :size="18" />
        </button>
        <button class="icon-btn" :title="t('topbar.langToggle')" @click="toggleLang">
          <Languages :size="18" />
          <span class="lang-code">{{ locale === 'zh' ? '中' : 'EN' }}</span>
        </button>
      </div>
    </header>

    <div class="app-body">
      <!-- 图标导航轨 -->
      <aside class="rail">
        <nav class="rail-nav">
          <button
            v-for="item in navItems"
            :key="item.id"
            class="rail-item"
            :class="{ active: activeTab === item.id }"
            :title="item.label"
            @click="switchTab(item.id)"
          >
            <component :is="item.icon" :size="22" />
            <span class="rail-label">{{ item.label }}</span>
          </button>
        </nav>
      </aside>

      <!-- 主内容 -->
      <main class="main-content">
        <OverviewView v-if="activeTab === 'overview'" />
        <PortsView v-else-if="activeTab === 'ports'" />
        <HiddenPortsView v-else-if="activeTab === 'hidden'" />

        <section v-else class="placeholder-view">
          <div class="placeholder-card">
            <component
              :is="activeTab === 'notes' ? StickyNote : Settings"
              :size="44"
              class="placeholder-icon"
            />
            <h2>{{ t('placeholder.comingSoon') }}</h2>
            <p class="placeholder-sub">{{ t('nav.' + activeTab) }}</p>
            <span class="badge">{{ t('placeholder.comingSoonDesc') }}</span>
          </div>
        </section>
      </main>
    </div>

    <!-- 状态栏 -->
    <footer class="statusbar">
      <div class="status-item">
        <span class="status-dot" />
        <span>PortView v{{ version }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">{{ t('statusbar.refreshManual') }}</span>
      </div>
      <div class="status-item status-right">
        <span class="status-occ" :title="t('statusbar.occupancy')">
          {{ t('statusbar.occupancy') }} <b>{{ occupancyPct }}%</b>
        </span>
        <span class="status-sep">·</span>
        <span>{{ t('statusbar.containers') }} <b>{{ stats.containers }}</b></span>
      </div>
    </footer>
  </div>
</template>

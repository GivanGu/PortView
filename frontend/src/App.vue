<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue'
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
  Palette,
  ShieldAlert,
  RefreshCw,
} from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { setLocale } from '@/i18n'
import { fetchPorts, healthCheck, getPrefs } from '@/api'
import type { PortAnalysis } from '@/api'
import OverviewView from '@/components/OverviewView.vue'
import PortsView from '@/components/PortsView.vue'
import NotesView from '@/components/NotesView.vue'
import HiddenPortsView from '@/components/HiddenPortsView.vue'
import SettingsView from '@/components/SettingsView.vue'
import LoginView from '@/components/LoginView.vue'
import PasswordPrompt from '@/components/PasswordPrompt.vue'
import useAuth from '@/store/auth'
import usePrefs from '@/store/prefs'

type Tab = 'overview' | 'ports' | 'notes' | 'hidden' | 'settings'
type Theme = 'dark' | 'light'
type Lang = 'zh' | 'en'

const { t, locale } = useI18n()

// v1.2：登录门
const { state: auth, refresh: refreshAuth } = useAuth()
const authChecked = ref(false)
const needsLogin = computed(() => auth.value.auth_required && !auth.value.logged_in)

// v1.4.3：首次启动密码提示（无密码 + 未点过「暂不设置」时弹一次）
const PW_DISMISS_KEY = 'portview.pwPromptDismissed'
const showPwPrompt = ref(false)

function pwDismissed(): boolean {
  try {
    return localStorage.getItem(PW_DISMISS_KEY) === '1'
  } catch {
    return false
  }
}

function onPwSaved() {
  showPwPrompt.value = false
}

function onPwDismissed() {
  try {
    localStorage.setItem(PW_DISMISS_KEY, '1')
  } catch {
    /* ignore */
  }
  showPwPrompt.value = false
}

const THEME_KEY = 'portview.theme'
const ACCENT_KEY = 'portview.accent'

const ACCENTS = [
  { id: 'indigo', color: '#6366f1' },
  { id: 'blue',   color: '#2563eb' },
  { id: 'teal',   color: '#0d9488' },
  { id: 'rose',   color: '#e11d48' },
  { id: 'amber',  color: '#d97706' },
  { id: 'violet', color: '#8b5cf6' },
] as const

type AccentId = (typeof ACCENTS)[number]['id']

const activeTab = ref<Tab>('overview')
const theme = ref<Theme>('dark')
const accent = ref<AccentId>('indigo')
const version = ref('')
const loading = ref(true)
const showAccentPicker = ref(false)

// 状态栏实时指标
const stats = ref<{ used: number; available: number; containers: number }>({
  used: 0,
  available: 0,
  containers: 0,
})

const { refreshInterval, setRefreshInterval, triggerRefresh } = usePrefs()

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

function applyAccent(a: AccentId) {
  document.documentElement.setAttribute('data-accent', a)
  try {
    localStorage.setItem(ACCENT_KEY, a)
  } catch {
    /* ignore */
  }
}

function initialAccent(): AccentId {
  try {
    const saved = localStorage.getItem(ACCENT_KEY)
    if (saved && ACCENTS.some(x => x.id === saved)) return saved as AccentId
  } catch {
    /* ignore */
  }
  return 'indigo'
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

function pickAccent(a: AccentId) {
  accent.value = a
  applyAccent(a)
  showAccentPicker.value = false
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

// 状态栏指标自动刷新（与设置里的「刷新间隔」保持一致；0=手动）
let statsTimer: ReturnType<typeof setInterval> | null = null

function applyStatsTimer() {
  if (statsTimer) {
    clearInterval(statsTimer)
    statsTimer = null
  }
  if (refreshInterval.value > 0) {
    statsTimer = setInterval(() => {
      if (!document.hidden) loadStats()
    }, refreshInterval.value * 1000)
  }
}

// 刷新间隔在设置页修改后实时生效（无需刷新页面）
watch(refreshInterval, () => {
  applyStatsTimer()
})

// v1.4.5：标签页「懒挂载 + 保活」。首次点到的 tab 才 mount（v-if），
// 之后切换只切换显隐（v-show），不再卸载/重挂 → 概览等视图切走再切回不重新拉数据。
const visited = reactive<Record<Tab, boolean>>({
  overview: true,
  ports: false,
  notes: false,
  hidden: false,
  settings: false,
})

function switchTab(tab: Tab) {
  visited[tab] = true
  activeTab.value = tab
}

// v1.4.4：顶栏全局刷新按钮。手动模式下点一下即刷新状态栏指标 + 通知各视图重新拉数据。
function handleGlobalRefresh() {
  loadStats()
  triggerRefresh()
}

function onDocClick(e: MouseEvent) {
  if (showAccentPicker.value && !(e.target as HTMLElement).closest('.accent-picker-wrap')) {
    showAccentPicker.value = false
  }
}

onMounted(async () => {
  document.addEventListener('click', onDocClick)
  theme.value = initialTheme()
  applyTheme(theme.value)
  accent.value = initialAccent()
  applyAccent(accent.value)
  // v1.2：先查登录态
  await refreshAuth()
  authChecked.value = true
  // v1.4.3：首次启动密码提示（无密码 + 未点过「暂不设置」）
  if (!auth.value.has_password && !pwDismissed()) {
    showPwPrompt.value = true
  }
  try {
    const health = await healthCheck()
    version.value = health.version
  } catch {
    version.value = 'unknown'
  }
  try {
    const prefs = await getPrefs()
    if (prefs.success) setRefreshInterval(prefs.data.refresh_interval ?? 0)
  } catch { /* ignore */ }
  applyStatsTimer()
  loading.value = false
  loadStats()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  if (statsTimer) clearInterval(statsTimer)
})
</script>

<template>
  <LoginView v-if="needsLogin" />
  <div v-else class="app-shell">
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
        <button class="icon-btn" :title="t('common.refresh')" @click="handleGlobalRefresh">
          <RefreshCw :size="18" />
        </button>

        <button class="icon-btn" :title="t('topbar.themeToggle')" @click="toggleTheme">
          <Sun v-if="theme === 'dark'" :size="18" />
          <Moon v-else :size="18" />
        </button>

        <!-- 强调色选色器 -->
        <div class="accent-picker-wrap">
          <button
            class="icon-btn accent-trigger"
            :title="t('accent.title')"
            @click="showAccentPicker = !showAccentPicker"
          >
            <Palette :size="18" />
          </button>
          <div
            v-if="showAccentPicker"
            class="accent-picker"
            role="listbox"
            :aria-label="t('accent.title')"
          >
            <button
              v-for="a in ACCENTS"
              :key="a.id"
              class="accent-swatch"
              :class="{ active: accent === a.id }"
              :style="{ background: a.color }"
              :title="a.id"
              :aria-label="a.id"
              :aria-selected="accent === a.id"
              @click="pickAccent(a.id)"
            />
          </div>
        </div>

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
        <OverviewView v-if="visited.overview" v-show="activeTab === 'overview'" />
        <PortsView v-if="visited.ports" v-show="activeTab === 'ports'" />
        <NotesView v-if="visited.notes" v-show="activeTab === 'notes'" />
        <HiddenPortsView v-if="visited.hidden" v-show="activeTab === 'hidden'" />
        <SettingsView v-if="visited.settings" v-show="activeTab === 'settings'" />
      </main>
    </div>

    <!-- 状态栏 -->
    <footer class="statusbar">
      <div class="status-item">
        <span class="status-dot" />
        <span>PortView v{{ version }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">
          {{ refreshInterval > 0 ? t('statusbar.refreshAuto', { s: refreshInterval }) : t('statusbar.refreshManual') }}
        </span>
      </div>
      <div class="status-item status-right">
        <button
          v-if="!auth.has_password"
          class="pw-chip"
          :title="t('app.noPasswordTitle')"
          @click="showPwPrompt = true"
        >
          <ShieldAlert :size="13" />
          {{ t('app.noPassword') }}
        </button>
        <span class="status-occ" :title="t('statusbar.occupancy')">
          {{ t('statusbar.occupancy') }} <b>{{ occupancyPct }}%</b>
        </span>
        <span class="status-sep">·</span>
        <span>{{ t('statusbar.containers') }} <b>{{ stats.containers }}</b></span>
      </div>
    </footer>

  </div>

  <!-- v1.4.4：首次启动密码提示。放在 app-shell 外，避免 needsLogin 切换时
       随 app-shell 一起卸载/重挂，导致旧实例的 saved 事件无法关闭新实例（登录循环）。 -->
  <PasswordPrompt
    v-if="showPwPrompt"
    @saved="onPwSaved"
    @dismissed="onPwDismissed"
  />
</template>

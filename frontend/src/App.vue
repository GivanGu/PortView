<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import {
  LayoutDashboard,
  Network,
  Star,
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
  PanelLeftClose,
  PanelLeftOpen,
  X,
  Eye,
  ChevronLeft,
  ChevronRight,
} from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { setLocale } from '@/i18n'
import { fetchPorts, healthCheck, getPrefs, backgroundUrl, hasBackground } from '@/api'
import type { PortAnalysis } from '@/api'
import OverviewView from '@/components/OverviewView.vue'
import PortsView from '@/components/PortsView.vue'
import FavoritesView from '@/components/FavoritesView.vue'
import HiddenPortsView from '@/components/HiddenPortsView.vue'
import SettingsView from '@/components/SettingsView.vue'
import LoginView from '@/components/LoginView.vue'
import PasswordPrompt from '@/components/PasswordPrompt.vue'
import BackgroundLayer from '@/components/BackgroundLayer.vue'
import SearchFocusOverlay from '@/components/SearchFocusOverlay.vue'
import useAuth from '@/store/auth'
import usePrefs from '@/store/prefs'
import { useSearch, type Tab } from '@/store/search'
import { useFavStatus } from '@/store/favStatus'

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
const LOGO_SCRIM_KEY = 'portview.logoScrim'
const LOGO_MODE_KEY = 'portview.logoDisplayMode'
// v1.6.6：默认主页（启动时打开的标签页）。localStorage 镜像防首屏闪烁，
// 服务端 prefs 为权威源（onMounted 同步回来）。改设置下次启动生效。
const DEFAULT_TAB_KEY = 'portview.defaultTab'
const DEFAULT_TABS = ['overview', 'favorites'] as const
type DefaultTab = (typeof DEFAULT_TABS)[number]

const ACCENTS = [
  { id: 'indigo', color: '#6366f1' },
  { id: 'blue',   color: '#2563eb' },
  { id: 'teal',   color: '#0d9488' },
  { id: 'rose',   color: '#e11d48' },
  { id: 'amber',  color: '#d97706' },
  { id: 'violet', color: '#8b5cf6' },
] as const

type AccentId = (typeof ACCENTS)[number]['id']

function initialDefaultTab(): DefaultTab {
  try {
    const saved = localStorage.getItem(DEFAULT_TAB_KEY)
    if (saved && DEFAULT_TABS.includes(saved as DefaultTab)) return saved as DefaultTab
  } catch {
    /* ignore */
  }
  return 'favorites'
}

// v1.6.6：默认首页由设置决定（默认收藏页，保持 v1.6.5 现状）
const activeTab = ref<Tab>(initialDefaultTab())
const theme = ref<Theme>('dark')
const accent = ref<AccentId>('indigo')
const version = ref('')
const channel = ref('stable')
const versionLabel = computed(() =>
  channel.value === 'dev' ? `dev-${version.value}` : `v${version.value}`,
)
const loading = ref(true)
const showAccentPicker = ref(false)

// v1.4.8：版本检测
const latestVersion = ref('')
const latestReleaseUrl = ref('')
const hasUpdate = computed(() => {
  if (!version.value || !latestVersion.value) return false
  if (version.value === 'unknown') return false
  const cur = version.value.replace(/^v/, '').split('.').map(Number)
  const lat = latestVersion.value.replace(/^v/, '').split('.').map(Number)
  for (let i = 0; i < 3; i++) {
    const c = cur[i]
    const l = lat[i]
    if (isNaN(c) || isNaN(l)) return false
    if (l > c) return true
    if (l < c) return false
  }
  return false
})

async function checkLatestVersion() {
  try {
    const res = await fetch('https://api.github.com/repos/GivanGu/PortView/releases/latest')
    if (res.ok) {
      const data = await res.json()
      latestVersion.value = (data.tag_name || '').replace(/^v/, '')
      latestReleaseUrl.value = data.html_url || ''
    }
  } catch { /* 离线时静默 */ }
}

function openGitHub() {
  window.open('https://github.com/GivanGu/PortView', '_blank')
}

function openLatestRelease() {
  window.open(latestReleaseUrl.value || 'https://github.com/GivanGu/PortView/releases', '_blank')
}

// 状态栏实时指标
const stats = ref<{ used: number; available: number; containers: number }>({
  used: 0,
  available: 0,
  containers: 0,
})

const { refreshInterval, setRefreshInterval, triggerRefresh, logoScrim, setLogoScrim, logoDisplayMode, setLogoDisplayMode, setFavorites, markFavoritesLoaded, backgroundSet, backgroundVersion, backgroundScope, backgroundBlur, setBackgroundSet, setBackgroundScope, setBackgroundBlur } = usePrefs()

const navItems = computed(() => [
  { id: 'overview' as Tab, icon: LayoutDashboard, label: t('nav.overview') },
  { id: 'favorites' as Tab, icon: Star, label: t('nav.favorites') },
  { id: 'ports' as Tab, icon: Network, label: t('nav.ports') },
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

// v1.5.2：卡片 Logo 遮罩档位。落到 <html data-logo-scrim> 属性，
// style.css 依据它给 .port-card-scrim 套对应渐变/毛玻璃/无遮罩样式。
const LOGO_SCRIMS = ['none', 'left', 'overlay', 'glass'] as const

function applyLogoScrim(s: string) {
  document.documentElement.setAttribute('data-logo-scrim', s)
  try {
    localStorage.setItem(LOGO_SCRIM_KEY, s)
  } catch {
    /* ignore */
  }
}

function initialLogoScrim(): string {
  try {
    const saved = localStorage.getItem(LOGO_SCRIM_KEY)
    if (saved && LOGO_SCRIMS.includes(saved as (typeof LOGO_SCRIMS)[number])) return saved
  } catch {
    /* ignore */
  }
  return 'left'
}

// v1.5.11：卡片 Logo 展示模式（background / box）。仅落到 localStorage，
// 模板直接读 store 值做条件渲染，无需 <html> 属性。
const LOGO_MODES = ['background', 'box'] as const

function applyLogoMode(m: string) {
  try {
    localStorage.setItem(LOGO_MODE_KEY, m)
  } catch {
    /* ignore */
  }
}

function initialLogoMode(): 'background' | 'box' {
  try {
    const saved = localStorage.getItem(LOGO_MODE_KEY)
    if (saved && LOGO_MODES.includes(saved as (typeof LOGO_MODES)[number])) return saved as 'background' | 'box'
  } catch {
    /* ignore */
  }
  return 'background'
}

// v1.5.5：侧栏收缩/展开。localStorage 持久化，与主题/强调色同一惯例
const RAIL_KEY = 'portview.railCollapsed'
const railCollapsed = ref(false)

function initialRailCollapsed(): boolean {
  try {
    return localStorage.getItem(RAIL_KEY) === '1'
  } catch {
    return false
  }
}

function toggleRail() {
  railCollapsed.value = !railCollapsed.value
  try {
    localStorage.setItem(RAIL_KEY, railCollapsed.value ? '1' : '0')
  } catch {
    /* ignore */
  }
}

// v1.6.6：侧栏自动隐藏。开启后 rail 默认收起不占空间，悬停左缘标签滑出、移出 300ms 滑回；
// 点标签钉住/取消钉住（触摸设备无 hover，点按即唤出）。localStorage 持久化，与收起/展开同惯例。
const RAIL_AUTO_KEY = 'portview.railAutoHide'
const railAutoHide = ref(false)
const railPinned = ref(false)
const railHoverOpen = ref(false)
let railCloseTimer: ReturnType<typeof setTimeout> | null = null

function initialRailAutoHide(): boolean {
  try {
    return localStorage.getItem(RAIL_AUTO_KEY) === '1'
  } catch {
    return false
  }
}

function toggleRailAutoHide() {
  railAutoHide.value = !railAutoHide.value
  railPinned.value = false
  railHoverOpen.value = false
  try {
    localStorage.setItem(RAIL_AUTO_KEY, railAutoHide.value ? '1' : '0')
  } catch {
    /* ignore */
  }
}

function cancelRailClose() {
  if (railCloseTimer) {
    clearTimeout(railCloseTimer)
    railCloseTimer = null
  }
}

function openRailHover() {
  if (!railAutoHide.value) return
  cancelRailClose()
  railHoverOpen.value = true
}

function scheduleRailClose() {
  if (!railAutoHide.value) return
  cancelRailClose()
  railCloseTimer = setTimeout(() => {
    railHoverOpen.value = false
    railCloseTimer = null
  }, 300)
}

function toggleRailPin() {
  railPinned.value = !railPinned.value
  if (!railPinned.value) railHoverOpen.value = false
}

const railVisible = computed(() => !railAutoHide.value || railPinned.value || railHoverOpen.value)

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

// v1.5.2：Logo 遮罩档位切换后实时落到 <html> 属性，卡片遮罩即时变化
watch(logoScrim, (v) => {
  applyLogoScrim(v)
})

// v1.5.11：Logo 展示模式切换后实时落到 localStorage（模板读 store 即时重渲染）
watch(logoDisplayMode, (v) => {
  applyLogoMode(v)
})

// v1.6.6：全应用背景。scope=all 且有图时，挂 fixed 背景层 + <html data-fav-bg="all">
// 驱动 style.css 把顶栏/侧栏/状态栏/页头转半透明（卡片保持不透明保证可读）。
const showAllBg = computed(() => backgroundSet.value && backgroundScope.value === 'all')
watch(
  showAllBg,
  (v) => {
    if (v) document.documentElement.setAttribute('data-fav-bg', 'all')
    else document.documentElement.removeAttribute('data-fav-bg')
  },
  { immediate: true },
)

// v1.4.5：标签页「懒挂载 + 保活」。首次点到的 tab 才 mount（v-if），
// 之后切换只切换显隐（v-show），不再卸载/重挂 → 概览等视图切走再切回不重新拉数据。
const _defaultTab = activeTab.value
const visited = reactive<Record<Tab, boolean>>({
  overview: _defaultTab === 'overview',
  favorites: _defaultTab === 'favorites',
  ports: false,
  hidden: false,
  settings: false,
})

function switchTab(tab: Tab) {
  visited[tab] = true
  activeTab.value = tab
  // 先更新 store 的激活页，再清空搜索词：
  // 各视图的搜索 watch 以 store.activeTab 为守卫，顺序反了会让旧页面多跑一次空查询
  setActiveTab(tab)
  // 切页清空搜索词：每个页面从全新列表开始，避免跨页带词造成误判
  clearSearch()
}

// ── v1.6.6：顶栏全局搜索 ──
// 各页面不再有自己的搜索框，统一由顶栏输入框驱动（store.query）。
// 有列表过滤能力的页面（端口/收藏）watch query 做过滤；
// 无过滤能力的页面（概览/设置/隐藏端口）用 useSearchFocus 播放聚焦动画。
const {
  query: searchQuery,
  setQuery: setSearchQuery,
  clear: clearSearch,
  setActiveTab,
  shakeNonce: searchShakeNonce,
} = useSearch()
const searchInputRef = ref<HTMLInputElement | null>(null)
const searchShaking = ref(false)

// 收藏页状态栏计数器（FavoritesView 写入，离开收藏页 active=false）
const { status: favStatus } = useFavStatus()

const searchPlaceholder = computed(() => {
  switch (activeTab.value) {
    case 'overview':
      return t('topbar.searchOverview')
    case 'favorites':
      return t('favorites.searchPlaceholder')
    case 'ports':
      return t('ports.searchPlaceholder')
    case 'hidden':
      return t('hidden.searchPlaceholder')
    default:
      return t('topbar.searchSettings')
  }
})

function onSearchInput(e: Event) {
  setSearchQuery((e.target as HTMLInputElement).value)
}

function focusSearch() {
  searchInputRef.value?.focus()
  searchInputRef.value?.select()
}

// ⌘K / Ctrl+K 聚焦搜索框（顶栏 kbd 提示对应的行为）
function onSearchKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    focusSearch()
  }
}

function onSearchInputKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    clearSearch()
  }
}

// 当前页无匹配 → 顶栏抖动一次
watch(searchShakeNonce, () => {
  searchShaking.value = false
  nextTick(() => {
    searchShaking.value = true
    setTimeout(() => {
      searchShaking.value = false
    }, 400)
  })
})

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

// v1.4.8：跨组件导航事件（如 PortsView 点「打开服务」未设置地址时跳设置页）
function onNavigate(e: Event) {
  const detail = (e as CustomEvent).detail ?? {}
  const tab = detail.tab as Tab | undefined
  const anchor = detail.anchor as string | undefined
  if (!tab) return
  switchTab(tab)
  if (anchor) {
    // 等视图渲染（v-if 挂载）后再滚动到目标锚点，带重试机制
    const target = anchor
    let attempts = 0
    const maxAttempts = 5
    function tryScroll() {
      const el = document.getElementById(target)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      } else if (attempts < maxAttempts) {
        attempts++
        setTimeout(tryScroll, 80)
      }
    }
    nextTick(tryScroll)
  }
}

onMounted(async () => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('portview:navigate', onNavigate)
  document.addEventListener('keydown', onSearchKeydown)
  // 初始页签可能不是 overview（默认主页设置），同步 store 守卫
  setActiveTab(activeTab.value)
  theme.value = initialTheme()
  applyTheme(theme.value)
  accent.value = initialAccent()
  applyAccent(accent.value)
  applyLogoScrim(initialLogoScrim())
  setLogoDisplayMode(initialLogoMode())
  railCollapsed.value = initialRailCollapsed()
  railAutoHide.value = initialRailAutoHide()
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
    channel.value = health.channel ?? 'stable'
  } catch {
    version.value = 'unknown'
  }
  try {
    const prefs = await getPrefs()
    if (prefs.success) {
      setRefreshInterval(prefs.data.refresh_interval ?? 0)
      if (prefs.data.logo_scrim) setLogoScrim(prefs.data.logo_scrim)
      if (prefs.data.logo_display_mode) setLogoDisplayMode(prefs.data.logo_display_mode)
      if (prefs.data.favorites) setFavorites(prefs.data.favorites)
      // v1.6.7：服务端数据已就绪（含「无收藏」的空态），放行收藏页归一逻辑
      markFavoritesLoaded()
      // v1.6.6：默认主页（服务端权威，同步到 localStorage，下次启动生效）
      if (prefs.data.default_tab) {
        try {
          localStorage.setItem(DEFAULT_TAB_KEY, prefs.data.default_tab)
        } catch { /* ignore */ }
      }
      // v1.6.6：背景图作用域 + 模糊度
      if (prefs.data.background_scope) setBackgroundScope(prefs.data.background_scope)
      if (prefs.data.background_blur != null) setBackgroundBlur(prefs.data.background_blur)
    }
  } catch { /* ignore */ }
  // v1.6.6：探测背景图是否已设置（驱动全应用背景层显隐）
  void hasBackground().then((set) => setBackgroundSet(set))
  applyStatsTimer()
  loading.value = false
  loadStats()
  // v1.4.8：版本检测（不阻塞加载）
  void checkLatestVersion()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('portview:navigate', onNavigate)
  document.removeEventListener('keydown', onSearchKeydown)
  if (statsTimer) clearInterval(statsTimer)
})
</script>

<template>
  <LoginView v-if="needsLogin" />
  <div v-else class="app-shell">
    <!-- v1.6.6：全应用毛玻璃背景（scope=all 且有图时） -->
    <BackgroundLayer v-if="showAllBg" fixed :src="backgroundUrl(backgroundVersion)" :blur="backgroundBlur" />
    <!-- 顶栏：logo + 搜索 + 主题/语言 -->
    <header class="topbar">
      <div class="topbar-brand">
        <div class="brand-mark"><Activity :size="18" /></div>
        <span class="brand-name">{{ t('app.name') }}</span>
      </div>

      <div class="topbar-search" :class="{ 'search-shaking': searchShaking }" role="search">
        <Search class="search-icon" :size="16" />
        <input
          ref="searchInputRef"
          type="text"
          :value="searchQuery"
          :placeholder="searchPlaceholder"
          aria-label="search"
          @input="onSearchInput"
          @keydown="onSearchInputKeydown"
        />
        <button v-if="searchQuery" class="search-clear" :title="t('topbar.searchClear')" @click="clearSearch">
          <X :size="14" />
        </button>
        <kbd v-else class="kbd">{{ t('topbar.searchKbd') }}</kbd>
      </div>

      <div class="topbar-actions">
        <button class="icon-btn" :title="t('topbar.github')" @click="openGitHub">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/>
          </svg>
        </button>

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
      <aside
        class="rail"
        :class="{ collapsed: railCollapsed, 'auto-hidden': railAutoHide && !railVisible }"
        @mouseenter="openRailHover"
        @mouseleave="scheduleRailClose"
      >
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
        <button
          class="rail-toggle rail-auto-toggle"
          :title="railAutoHide ? t('nav.autoHideOff') : t('nav.autoHide')"
          :aria-label="railAutoHide ? t('nav.autoHideOff') : t('nav.autoHide')"
          @click="toggleRailAutoHide"
        >
          <EyeOff v-if="railAutoHide" :size="18" />
          <Eye v-else :size="18" />
        </button>
        <button
          class="rail-toggle"
          :title="railCollapsed ? t('nav.expand') : t('nav.collapse')"
          :aria-label="railCollapsed ? t('nav.expand') : t('nav.collapse')"
          @click="toggleRail"
        >
          <PanelLeftOpen v-if="railCollapsed" :size="20" />
          <PanelLeftClose v-else :size="20" />
        </button>
      </aside>

      <!-- 自动隐藏模式：左缘半圆标签（悬停滑出 / 点按钉住） -->
      <button
        v-if="railAutoHide"
        class="rail-tab"
        :class="{ open: railVisible }"
        :title="railVisible ? t('nav.hideRail') : t('nav.expand')"
        :aria-label="railVisible ? t('nav.hideRail') : t('nav.expand')"
        @click="toggleRailPin"
        @mouseenter="openRailHover"
        @mouseleave="scheduleRailClose"
      >
        <ChevronLeft v-if="railVisible" :size="14" />
        <ChevronRight v-else :size="14" />
      </button>
      <!-- 自动隐藏模式：rail 隐藏时的左缘窄悬停区 -->
      <div v-if="railAutoHide && !railVisible" class="rail-edge-zone" @mouseenter="openRailHover"></div>

      <!-- 主内容 -->
      <main class="main-content">
        <OverviewView v-if="visited.overview" v-show="activeTab === 'overview'" />
        <FavoritesView v-if="visited.favorites" v-show="activeTab === 'favorites'" />
        <PortsView v-if="visited.ports" v-show="activeTab === 'ports'" />
        <HiddenPortsView v-if="visited.hidden" v-show="activeTab === 'hidden'" />
        <SettingsView v-if="visited.settings" v-show="activeTab === 'settings'" />
      </main>
    </div>

    <!-- 状态栏 -->
    <footer class="statusbar">
      <div class="status-item">
        <span class="status-dot" />
        <span>PortView {{ versionLabel }}</span>
        <button
          v-if="hasUpdate"
          class="update-badge"
          :title="t('topbar.updateAvailable', { v: latestVersion })"
          @click="openLatestRelease"
        >
          {{ t('topbar.updateAvailable', { v: latestVersion }) }}
        </button>
      </div>
      <div class="status-item">
        <span class="status-label">
          {{ refreshInterval > 0 ? t('statusbar.refreshAuto', { s: refreshInterval }) : t('statusbar.refreshManual') }}
        </span>
      </div>
      <div class="status-item status-right">
        <!-- 收藏页计数器：分组名 · 总数 · 离线 · 在线（仅收藏页前台时显示） -->
        <span v-if="favStatus.active" class="fav-status">
          <span class="fav-status-group">{{ favStatus.group }}</span>
          <span class="status-sep">·</span>
          <span :title="t('statusbar.total')">{{ t('statusbar.total') }} <b>{{ favStatus.total }}</b></span>
          <span class="status-sep">·</span>
          <span :title="t('statusbar.offline')">{{ t('statusbar.offline') }} <b>{{ favStatus.offline }}</b></span>
          <span class="status-sep">·</span>
          <span :title="t('statusbar.online')">{{ t('statusbar.online') }} <b>{{ favStatus.online }}</b></span>
        </span>
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

    <!-- v1.6.6：非搜索页关键词聚焦动画层 -->
    <SearchFocusOverlay />
  </div>

  <!-- v1.4.4：首次启动密码提示。放在 app-shell 外，避免 needsLogin 切换时
       随 app-shell 一起卸载/重挂，导致旧实例的 saved 事件无法关闭新实例（登录循环）。 -->
  <PasswordPrompt
    v-if="showPwPrompt"
    @saved="onPwSaved"
    @dismissed="onPwDismissed"
  />
</template>

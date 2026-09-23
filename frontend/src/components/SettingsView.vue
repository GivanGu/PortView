<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { setLocale } from '@/i18n'
import { getPrefs, patchPrefs, resetPrefs, getAccessAddress, setAccessAddress, setBackground, deleteBackground, backgroundUrl, type UserPrefs } from '@/api'
import useAuth from '@/store/auth'
import usePrefs from '@/store/prefs'
import { useSearchFocus } from '@/composables/useSearchFocus'
import { Settings, Sun, Moon, Languages, RotateCcw, Palette, Check, ShieldCheck, Timer, AlertTriangle, Globe, LayoutGrid, Home, Image as ImageIcon } from 'lucide-vue-next'

const { t, locale } = useI18n()

// v1.6.6：顶栏全局搜索 → 本页无过滤能力，命中卡片播放聚焦动画
const rootRef = ref<HTMLElement | null>(null)
useSearchFocus(rootRef, 'settings')

// v1.2：登录/安全
const auth = useAuth()
const newPassword = ref('')
const confirmPassword = ref('')
const passwordBusy = ref(false)

async function handleSetPassword() {
  if (!newPassword.value || newPassword.value.length < 4) {
    showToast(t('settings.pwMinLength'))
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    showToast(t('settings.pwMismatch'))
    return
  }
  const ok = confirm(t('settings.pwConfirmMsg', { len: newPassword.value.length }))
  if (!ok) return
  passwordBusy.value = true
  try {
    await auth.doSetPassword(newPassword.value)
    // doSetPassword 会撤销当前会话（设密码/自动开启保护均触发），
    // 需用新密码重新登录，否则刷新页面后会话失效、被踢回登录页。
    await auth.doLogin(newPassword.value)
    newPassword.value = ''
    confirmPassword.value = ''
    showToast(t('settings.pwUpdated'))
    setTimeout(() => window.location.reload(), 1200)
  } catch {
    showToast(t('settings.pwSetFailed'))
  } finally {
    passwordBusy.value = false
  }
}

async function handleToggleAuth() {
  const next = !auth.state.value.auth_required
  // 开启登录保护前必须先设置密码，否则开启后无人能登录
  if (next && !auth.state.value.has_password) {
    showToast(t('settings.pwSetFirst'))
    return
  }
  try {
    await auth.doToggle(next)
    showToast(next ? t('settings.authOn') : t('settings.authOff'))
  } catch {
    showToast(next ? t('settings.authOnFailed') : t('settings.authOffFailed'))
  }
}

async function handleLogout() {
  await auth.doLogout()
  window.location.reload()
}

// App.vue 已经把这些放在 localStorage 里；SettingsView 只是编辑器。
// 我们把当前值通过 DOM 属性 (data-theme / data-accent) 读出来作为"初始"，
// 再合并后端 prefs 作为"服务端权威源"，取后端优先（无则退回本地）。
const ACCENTS = [
  { id: 'indigo', color: '#6366f1', label: 'accent.indigo' },
  { id: 'blue',   color: '#2563eb', label: 'accent.blue' },
  { id: 'teal',   color: '#0d9488', label: 'accent.teal' },
  { id: 'rose',   color: '#e11d48', label: 'accent.rose' },
  { id: 'amber',  color: '#d97706', label: 'accent.amber' },
  { id: 'violet', color: '#8b5cf6', label: 'accent.violet' },
]

function currentTheme(): 'dark' | 'light' {
  return (document.documentElement.dataset.theme as 'dark' | 'light') || 'dark'
}
function currentAccent(): string {
  return document.documentElement.dataset.accent || 'indigo'
}

const theme = ref<'dark' | 'light'>(currentTheme())
const accent = ref<string>(currentAccent())
const lang = ref<'zh' | 'en'>(locale.value as 'zh' | 'en')
const { refreshInterval, setRefreshInterval, logoScrim, setLogoScrim, logoDisplayMode, setLogoDisplayMode, backgroundSet, backgroundVersion, backgroundScope, backgroundBlur, setBackgroundSet, setBackgroundScope, setBackgroundBlur } = usePrefs()
const savingPref = ref(false)
const toast = ref('')
const toastVisible = ref(false)

// v1.6.6：默认主页（本地镜像防闪烁，服务端权威，下次启动生效）
const DEFAULT_TAB_KEY = 'portview.defaultTab'
const DEFAULT_TABS = ['overview', 'favorites'] as const
type DefaultTab = (typeof DEFAULT_TABS)[number]

function initialDefaultTab(): DefaultTab {
  try {
    const saved = localStorage.getItem(DEFAULT_TAB_KEY)
    if (saved && DEFAULT_TABS.includes(saved as DefaultTab)) return saved as DefaultTab
  } catch { /* ignore */ }
  return 'favorites'
}
const defaultTab = ref<DefaultTab>(initialDefaultTab())

function onHomeChange(v: DefaultTab) {
  defaultTab.value = v
  try {
    localStorage.setItem(DEFAULT_TAB_KEY, v)
  } catch { /* ignore */ }
  void persistPartial({ default_tab: v })
}

// v1.6.6：背景图（≤4MiB，前端预检）
const BG_MAX = 4 * 1024 * 1024
async function onBgFilePicked(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (file.size > BG_MAX) {
    showToast(t('settings.bgTooLarge'))
    return
  }
  try {
    const { mime, b64 } = await readImageFile(file)
    const resp = await setBackground(mime, b64)
    if (resp.success) {
      setBackgroundSet(true)
      showToast(t('settings.bgSaved'))
    } else {
      showToast(t('settings.bgSaveFailed'))
    }
  } catch {
    showToast(t('settings.bgSaveFailed'))
  }
}

async function handleRemoveBg() {
  try {
    await deleteBackground()
    setBackgroundSet(false)
    showToast(t('settings.bgRemoved'))
  } catch {
    showToast(t('settings.bgSaveFailed'))
  }
}

function onBgScopeChange(v: 'favorites' | 'all') {
  setBackgroundScope(v)
  void persistPartial({ background_scope: v })
}

// 背景模糊度：拖动实时预览（input），松手才落库（change），避免每像素一次 PATCH
function onBgBlurInput(e: Event) {
  setBackgroundBlur(Number((e.target as HTMLInputElement).value))
}
function onBgBlurChange(e: Event) {
  void persistPartial({ background_blur: Number((e.target as HTMLInputElement).value) })
}

function readImageFile(file: File): Promise<{ mime: string; b64: string }> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => {
      const dataUrl = String(r.result)
      resolve({ mime: file.type, b64: dataUrl.split(',')[1] || '' })
    }
    r.onerror = () => reject(r.error)
    r.readAsDataURL(file)
  })
}

function showToast(msg: string) {
  toast.value = msg
  toastVisible.value = true
  setTimeout(() => (toastVisible.value = false), 2200)
}

// --- Actions ---
function applyTheme(next: 'dark' | 'light') {
  theme.value = next
  document.documentElement.setAttribute('data-theme', next)
  try {
    localStorage.setItem('portview.theme', next)
  } catch { /* ignore */ }
}

function applyAccent(id: string) {
  accent.value = id
  document.documentElement.setAttribute('data-accent', id)
  try {
    localStorage.setItem('portview.accent', id)
  } catch { /* ignore */ }
}

function applyLang(next: 'zh' | 'en') {
  lang.value = next
  locale.value = next
  setLocale(next)
}

async function persistPartial(patch: Parameters<typeof patchPrefs>[0]) {
  savingPref.value = true
  try {
    const resp = await patchPrefs(patch)
    if (!resp.success) {
      showToast(`${t('settings.saveFailed')}: ${resp.error ?? 'unknown'}`)
    }
    return resp.success
  } catch (e) {
    console.warn('persistPref failed (offline ok):', e)
    showToast(t('settings.offlineSaved'))
    return true
  } finally {
    savingPref.value = false
  }
}

function onThemeChange(v: 'dark' | 'light') {
  applyTheme(v)
  void persistPartial({ theme: v })
}
function onAccentChange(id: string) {
  applyAccent(id)
  void persistPartial({ accent: id })
}
function onLangChange(v: 'zh' | 'en') {
  applyLang(v)
  void persistPartial({ lang: v })
}

function onRefreshIntervalChange(v: number) {
  setRefreshInterval(v)
  void persistPartial({ refresh_interval: v })
}

// v1.5.2：卡片 Logo 背景的可读性遮罩档位
function onLogoScrimChange(v: 'none' | 'left' | 'overlay' | 'glass') {
  setLogoScrim(v)
  void persistPartial({ logo_scrim: v })
}

// v1.5.11：卡片 Logo 展示模式（background / box）
function onLogoDisplayModeChange(v: 'background' | 'box') {
  setLogoDisplayMode(v)
  void persistPartial({ logo_display_mode: v })
}

// ── 访问地址 ──
const accessAddress = ref('')
const accessAddrBusy = ref(false)

async function loadAccessAddress() {
  try {
    const resp = await getAccessAddress()
    if (resp.success) accessAddress.value = resp.data?.address || ''
  } catch { /* ignore */ }
}

async function handleSaveAccessAddress() {
  accessAddrBusy.value = true
  try {
    const resp = await setAccessAddress(accessAddress.value.trim())
    if (resp.success) {
      // 后端只保留主机部分（剥离协议前缀），回传规范化地址后回填输入框
      if (resp.data?.address) accessAddress.value = resp.data.address
      showToast(t('settings.accessAddrSaved'))
    } else {
      showToast(t('settings.saveFailed'))
    }
  } catch {
    showToast(t('settings.saveFailed'))
  } finally {
    accessAddrBusy.value = false
  }
}

async function handleReset() {
  if (!confirm(t('settings.resetConfirm'))) return
  savingPref.value = true
  try {
    await resetPrefs()
  } finally {
    savingPref.value = false
  }
  // 重置回默认值并落到本地
  applyTheme('dark')
  applyAccent('indigo')
  applyLang('zh')
  setRefreshInterval(0)
  setLogoScrim('left')
  setLogoDisplayMode('background')
  // v1.6.6：默认主页 + 背景作用域 + 清除背景图
  defaultTab.value = 'favorites'
  try {
    localStorage.setItem(DEFAULT_TAB_KEY, 'favorites')
  } catch { /* ignore */ }
  setBackgroundScope('favorites')
  setBackgroundBlur(10)
  try {
    await deleteBackground()
    setBackgroundSet(false)
  } catch { /* ignore */ }
  showToast(t('settings.resetDone'))
}

// --- 初始化：如果后端可用，以后端为准 ---
onMounted(async () => {
  try {
    const resp = await getPrefs()
    if (resp.success && resp.data) {
      const p: UserPrefs = resp.data
      if (p.theme) applyTheme(p.theme)
      if (p.accent && ACCENTS.some(a => a.id === p.accent)) applyAccent(p.accent)
      if (p.lang) applyLang(p.lang)
      setRefreshInterval(p.refresh_interval ?? 0)
      if (p.logo_scrim) setLogoScrim(p.logo_scrim)
      if (p.logo_display_mode) setLogoDisplayMode(p.logo_display_mode)
      // v1.6.6：默认主页（服务端权威）
      if (p.default_tab) defaultTab.value = p.default_tab
      if (p.background_scope) setBackgroundScope(p.background_scope)
      if (p.background_blur != null) setBackgroundBlur(p.background_blur)
    }
  } catch {
    /* 后端不可用，本地偏好仍然生效 */
  }
  void loadAccessAddress()
})

const savingText = computed(() => (savingPref.value ? t('settings.saving') : ''))
</script>

<template>
  <div ref="rootRef">
    <div class="main-header">
      <h1>{{ t('settings.title') }}</h1>
      <div class="header-actions">
        <button class="btn" :disabled="savingPref" @click="handleReset">
          <RotateCcw :size="14" class="btn-icon" />
          {{ t('settings.reset') }}
        </button>
      </div>
    </div>

    <div class="main-body">
      <p class="view-desc">{{ t('settings.subtitle') }}</p>

      <div class="settings-grid">
        <!-- v1.2：Login / Security -->
        <section class="settings-card" data-sfocus>
          <header class="settings-card-title">
            <ShieldCheck :size="16" class="card-ico" />
            <span>{{ t('settings.security') }}</span>
          </header>
          <p class="auth-hint">
            <template v-if="auth.state.value.auth_required">
              {{ t('settings.authEnabled') }} —
              <button class="btn-link" @click="handleLogout">{{ t('settings.authLogout') }}</button>
              ·
              <button class="btn-link" @click="handleToggleAuth">{{ t('settings.authClose') }}</button>
            </template>
            <template v-else>
              {{ t('settings.authDisabled') }} —
              <button
                class="btn-link"
                :disabled="!auth.state.value.has_password"
                :title="auth.state.value.has_password ? '' : t('settings.authSetPasswordFirst')"
                @click="handleToggleAuth"
              >
                {{ t('settings.authOpen') }}
              </button>
            </template>
          </p>
          <label class="auth-label">
            {{ t('settings.pwLabel') }}
            <input
              v-model="newPassword"
              class="auth-input"
              type="password"
              :placeholder="t('settings.pwPlaceholder')"
              autocomplete="new-password"
            />
          </label>
          <label class="auth-label">
            {{ t('settings.pwConfirmLabel') }}
            <input
              v-model="confirmPassword"
              class="auth-input"
              type="password"
              :placeholder="t('settings.pwConfirmPlaceholder')"
              autocomplete="new-password"
            />
          </label>
          <p class="auth-warning">
            <AlertTriangle :size="13" class="auth-warning-ico" />
            {{ t('settings.pwWarning') }}
          </p>
          <div class="auth-actions">
            <button
              class="btn btn-small"
              :disabled="passwordBusy || newPassword.length < 4 || newPassword !== confirmPassword"
              @click="handleSetPassword"
            >
              <ShieldCheck :size="13" />
              {{ t('settings.pwSave') }}
            </button>
            <span class="muted auth-status">
              {{ auth.state.value.has_password ? t('settings.pwHasPassword') : t('settings.pwNoPassword') }}
            </span>
          </div>
          <p v-if="auth.state.value.auth_required && !auth.state.value.has_password" class="auth-warning">
            <AlertTriangle :size="13" />
            {{ t('settings.authNoPwWarning') }}
          </p>
        </section>

        <!-- Theme -->
        <section class="settings-card" data-sfocus>
          <header class="settings-card-title">
            <Sun :size="16" class="card-ico" />
            <span>{{ t('settings.theme') }}</span>
          </header>
          <div class="radio-2col">
            <label class="radio-pill" :class="{ active: theme === 'dark' }">
              <input
                type="radio"
                name="pv-theme"
                :value="'dark'"
                :checked="theme === 'dark'"
                @change="() => onThemeChange('dark')"
              />
              <Moon :size="16" />
              <span>{{ t('settings.themeDark') }}</span>
            </label>
            <label class="radio-pill" :class="{ active: theme === 'light' }">
              <input
                type="radio"
                name="pv-theme"
                :value="'light'"
                :checked="theme === 'light'"
                @change="() => onThemeChange('light')"
              />
              <Sun :size="16" />
              <span>{{ t('settings.themeLight') }}</span>
            </label>
          </div>
        </section>

        <!-- v1.6.6：默认主页 -->
        <section class="settings-card" data-sfocus>
          <header class="settings-card-title">
            <Home :size="16" class="card-ico" />
            <span>{{ t('settings.home') }}</span>
          </header>
          <p class="settings-hint">{{ t('settings.homeHint') }}</p>
          <div class="radio-2col">
            <label class="radio-pill" :class="{ active: defaultTab === 'overview' }">
              <input
                type="radio"
                name="pv-home"
                value="overview"
                :checked="defaultTab === 'overview'"
                @change="onHomeChange('overview')"
              />
              <span>{{ t('settings.homeOverview') }}</span>
            </label>
            <label class="radio-pill" :class="{ active: defaultTab === 'favorites' }">
              <input
                type="radio"
                name="pv-home"
                value="favorites"
                :checked="defaultTab === 'favorites'"
                @change="onHomeChange('favorites')"
              />
              <span>{{ t('settings.homeFavorites') }}</span>
            </label>
          </div>
        </section>

        <!-- v1.6.6：背景图 -->
        <section class="settings-card" data-sfocus>
          <header class="settings-card-title">
            <ImageIcon :size="16" class="card-ico" />
            <span>{{ t('settings.background') }}</span>
          </header>
          <p class="settings-hint">{{ t('settings.backgroundHint') }}</p>
          <div v-if="backgroundSet" class="bg-row">
            <img :src="backgroundUrl(backgroundVersion)" class="bg-preview" alt="" />
            <div class="bg-actions">
              <label class="btn btn-small">
                {{ t('settings.bgChange') }}
                <input type="file" accept="image/*" class="hidden-input" @change="onBgFilePicked" />
              </label>
              <button class="btn btn-small btn-danger" @click="handleRemoveBg">
                {{ t('settings.bgRemove') }}
              </button>
            </div>
          </div>
          <label v-else class="btn btn-small">
            {{ t('settings.bgUpload') }}
            <input type="file" accept="image/*" class="hidden-input" @change="onBgFilePicked" />
          </label>
          <div class="settings-sub">
            <div class="settings-sub-title">{{ t('settings.bgScope') }}</div>
            <div class="radio-2col">
              <label class="radio-pill" :class="{ active: backgroundScope === 'favorites', disabled: !backgroundSet }">
                <input
                  type="radio"
                  name="pv-bg-scope"
                  value="favorites"
                  :checked="backgroundScope === 'favorites'"
                  :disabled="!backgroundSet"
                  @change="onBgScopeChange('favorites')"
                />
                <span>{{ t('settings.bgScopeFavorites') }}</span>
              </label>
              <label class="radio-pill" :class="{ active: backgroundScope === 'all', disabled: !backgroundSet }">
                <input
                  type="radio"
                  name="pv-bg-scope"
                  value="all"
                  :checked="backgroundScope === 'all'"
                  :disabled="!backgroundSet"
                  @change="onBgScopeChange('all')"
                />
                <span>{{ t('settings.bgScopeAll') }}</span>
              </label>
            </div>
          </div>
          <div class="settings-sub">
            <div class="settings-sub-title">
              {{ t('settings.bgBlur') }}
              <span class="bg-blur-val">{{ backgroundBlur }}</span>
            </div>
            <input
              type="range"
              class="bg-blur-slider"
              min="0"
              max="30"
              step="1"
              :value="backgroundBlur"
              :disabled="!backgroundSet"
              @input="onBgBlurInput"
              @change="onBgBlurChange"
            />
          </div>
        </section>

        <!-- Accent -->
        <section class="settings-card" data-sfocus>
          <header class="settings-card-title">
            <Palette :size="16" class="card-ico" />
            <span>{{ t('settings.accent') }}</span>
          </header>
          <div class="accent-grid">
            <button
              v-for="a in ACCENTS"
              :key="a.id"
              class="accent-chip"
              :class="{ active: accent === a.id }"
              :title="t(a.label)"
              @click="onAccentChange(a.id)"
            >
              <span class="dot" :style="{ background: a.color }"></span>
              <span class="lbl">{{ t(a.label) }}</span>
              <Check v-if="accent === a.id" :size="13" class="ck" />
            </button>
          </div>
        </section>

        <!-- Language -->
        <section class="settings-card" data-sfocus>
          <header class="settings-card-title">
            <Languages :size="16" class="card-ico" />
            <span>{{ t('settings.language') }}</span>
          </header>
          <div class="radio-2col">
            <label class="radio-pill" :class="{ active: lang === 'zh' }">
              <input
                type="radio"
                name="pv-lang"
                :value="'zh'"
                :checked="lang === 'zh'"
                @change="() => onLangChange('zh')"
              />
              <span>{{ t('settings.langZh') }}</span>
            </label>
            <label class="radio-pill" :class="{ active: lang === 'en' }">
              <input
                type="radio"
                name="pv-lang"
                :value="'en'"
                :checked="lang === 'en'"
                @change="() => onLangChange('en')"
              />
              <span>{{ t('settings.langEn') }}</span>
            </label>
          </div>
        </section>

        <!-- Refresh Interval -->
        <section class="settings-card" data-sfocus>
          <header class="settings-card-title">
            <Timer :size="16" class="card-ico" />
            <span>{{ t('settings.refreshInterval') }}</span>
          </header>
          <p class="settings-hint">{{ t('settings.refreshIntervalHint') }}</p>
          <div class="radio-2col">
            <label class="radio-pill" :class="{ active: refreshInterval === 0 }">
              <input
                type="radio"
                name="pv-refresh"
                :value="0"
                :checked="refreshInterval === 0"
                @change="() => onRefreshIntervalChange(0)"
              />
              <span>{{ t('settings.refreshManual') }}</span>
            </label>
            <label class="radio-pill" :class="{ active: refreshInterval === 10 }">
              <input
                type="radio"
                name="pv-refresh"
                :value="10"
                :checked="refreshInterval === 10"
                @change="() => onRefreshIntervalChange(10)"
              />
              <span>{{ t('settings.refresh10') }}</span>
            </label>
            <label class="radio-pill" :class="{ active: refreshInterval === 15 }">
              <input
                type="radio"
                name="pv-refresh"
                :value="15"
                :checked="refreshInterval === 15"
                @change="() => onRefreshIntervalChange(15)"
              />
              <span>{{ t('settings.refresh15') }}</span>
            </label>
            <label class="radio-pill" :class="{ active: refreshInterval === 30 }">
              <input
                type="radio"
                name="pv-refresh"
                :value="30"
                :checked="refreshInterval === 30"
                @change="() => onRefreshIntervalChange(30)"
              />
              <span>{{ t('settings.refresh30') }}</span>
            </label>
          </div>
        </section>

        <!-- v1.5.15：Logo 展示（展示模式 + 遮罩 合并为一张卡片，遮罩为条件子区块） -->
        <section class="settings-card" data-sfocus>
          <header class="settings-card-title">
            <LayoutGrid :size="16" class="card-ico" />
            <span>{{ t('settings.logoDisplay') }}</span>
          </header>

          <!-- 子区块 1：展示模式 -->
          <div class="settings-sub">
            <div class="settings-sub-title">{{ t('settings.logoDisplayModeLabel') }}</div>
            <p class="settings-hint">{{ t('settings.logoDisplayModeHint') }}</p>
            <div class="radio-2col">
              <label class="radio-pill" :class="{ active: logoDisplayMode === 'background' }">
                <input
                  type="radio"
                  name="pv-logo-mode"
                  :value="'background'"
                  :checked="logoDisplayMode === 'background'"
                  @change="() => onLogoDisplayModeChange('background')"
                />
                <span>{{ t('settings.logoModeBackground') }}</span>
              </label>
              <label class="radio-pill" :class="{ active: logoDisplayMode === 'box' }">
                <input
                  type="radio"
                  name="pv-logo-mode"
                  :value="'box'"
                  :checked="logoDisplayMode === 'box'"
                  @change="() => onLogoDisplayModeChange('box')"
                />
                <span>{{ t('settings.logoModeBox') }}</span>
              </label>
            </div>
          </div>

          <!-- 子区块 2：遮罩（仅背景展示模式生效，方框模式整块隐藏） -->
          <div v-if="logoDisplayMode === 'background'" class="settings-sub">
            <div class="settings-sub-title">{{ t('settings.logoScrimLabel') }}</div>
            <p class="settings-hint">{{ t('settings.logoScrimHint') }}</p>
            <div class="radio-2col">
              <label class="radio-pill" :class="{ active: logoScrim === 'left' }">
                <input
                  type="radio"
                  name="pv-logo-scrim"
                  :value="'left'"
                  :checked="logoScrim === 'left'"
                  @change="() => onLogoScrimChange('left')"
                />
                <span>{{ t('settings.scrimLeft') }}</span>
              </label>
              <label class="radio-pill" :class="{ active: logoScrim === 'overlay' }">
                <input
                  type="radio"
                  name="pv-logo-scrim"
                  :value="'overlay'"
                  :checked="logoScrim === 'overlay'"
                  @change="() => onLogoScrimChange('overlay')"
                />
                <span>{{ t('settings.scrimOverlay') }}</span>
              </label>
              <label class="radio-pill" :class="{ active: logoScrim === 'glass' }">
                <input
                  type="radio"
                  name="pv-logo-scrim"
                  :value="'glass'"
                  :checked="logoScrim === 'glass'"
                  @change="() => onLogoScrimChange('glass')"
                />
                <span>{{ t('settings.scrimGlass') }}</span>
              </label>
              <label class="radio-pill" :class="{ active: logoScrim === 'none' }">
                <input
                  type="radio"
                  name="pv-logo-scrim"
                  :value="'none'"
                  :checked="logoScrim === 'none'"
                  @change="() => onLogoScrimChange('none')"
                />
                <span>{{ t('settings.scrimNone') }}</span>
              </label>
            </div>
          </div>
        </section>

        <!-- Access Address -->
        <section class="settings-card" id="settings-access-address" data-sfocus>
          <header class="settings-card-title">
            <Globe :size="16" class="card-ico" />
            <span>{{ t('settings.accessAddress') }}</span>
          </header>
          <p class="settings-hint">{{ t('settings.accessAddressHint') }}</p>
          <div class="access-addr-row">
            <input
              v-model="accessAddress"
              class="form-input"
              type="text"
              :placeholder="t('settings.accessAddressPlaceholder')"
              @keyup.enter="handleSaveAccessAddress"
            />
            <button
              class="btn btn-small btn-primary"
              :disabled="accessAddrBusy"
              @click="handleSaveAccessAddress"
            >
              {{ t('common.save') }}
            </button>
          </div>
        </section>

        <!-- About -->
        <section class="settings-card" data-sfocus>
          <header class="settings-card-title">
            <Settings :size="16" class="card-ico" />
            <span>{{ t('settings.about') }}</span>
          </header>
          <p class="settings-about-text">
            PortView · {{ t('app.tagline') }}<br />
            <span class="muted">
              {{ t('settings.storageHint') }}
            </span>
          </p>
        </section>
      </div>

      <div v-if="toastVisible" class="save-toast" :title="savingText">
        {{ toast }}
      </div>
    </div>
  </div>
</template>

<style scoped>
/* v1.6.6：背景图卡片 */
.bg-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bg-preview {
  width: 72px;
  height: 48px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid var(--border);
  flex-shrink: 0;
}

.bg-actions {
  display: flex;
  gap: 8px;
}

/* 模糊度滑动条：拖动实时预览，数值随标题右侧显示 */
.bg-blur-val {
  margin-left: 8px;
  font-size: 12px;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.bg-blur-slider {
  width: 100%;
  height: 4px;
  margin-top: 10px;
  appearance: none;
  -webkit-appearance: none;
  border-radius: 2px;
  background: var(--border);
  outline: none;
  cursor: pointer;
  accent-color: var(--accent);
}

.bg-blur-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid var(--bg-primary);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
  cursor: pointer;
  transition: transform 0.12s;
}

.bg-blur-slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
}

.bg-blur-slider::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid var(--bg-primary);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
  cursor: pointer;
}

.bg-blur-slider:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.hidden-input {
  display: none;
}
</style>

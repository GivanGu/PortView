<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { setLocale } from '@/i18n'
import { getPrefs, patchPrefs, resetPrefs, type UserPrefs } from '@/api'
import useAuth from '@/store/auth'
import usePrefs from '@/store/prefs'
import { Settings, Sun, Moon, Languages, RotateCcw, Palette, Check, ShieldCheck, Timer, AlertTriangle } from 'lucide-vue-next'

const { t, locale } = useI18n()

// v1.2：登录/安全
const auth = useAuth()
const newPassword = ref('')
const confirmPassword = ref('')
const passwordBusy = ref(false)

async function handleSetPassword() {
  if (!newPassword.value || newPassword.value.length < 4) {
    showToast('密码至少 4 位')
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    showToast('两次输入的密码不一致')
    return
  }
  // v1.4.3：设置前确认 + 警示（忘记密码无法恢复）
  // v1.4.5：设密码 = 自动开启登录保护，故设置后需重新登录
  const ok = confirm(
    `新密码（${newPassword.value.length} 位）将保存，并自动开启登录保护。\n设置后需重新登录。\n\n请牢记密码，忘记密码将无法恢复。\n确认保存？`
  )
  if (!ok) return
  passwordBusy.value = true
  try {
    await auth.doSetPassword(newPassword.value)
    newPassword.value = ''
    confirmPassword.value = ''
    showToast('密码已更新，登录保护已开启')
    setTimeout(() => window.location.reload(), 1200)
  } catch {
    showToast('设置失败')
  } finally {
    passwordBusy.value = false
  }
}

async function handleToggleAuth() {
  const next = !auth.state.value.auth_required
  // 开启登录保护前必须先设置密码，否则开启后无人能登录
  if (next && !auth.state.value.has_password) {
    showToast('请先设置密码，再开启登录保护')
    return
  }
  try {
    await auth.doToggle(next)
    showToast(next ? '登录已开启' : '登录已关闭')
  } catch {
    showToast(next ? '开启失败：请先设置密码' : '关闭失败')
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
const { refreshInterval, setRefreshInterval } = usePrefs()
const savingPref = ref(false)
const toast = ref('')
const toastVisible = ref(false)

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
    }
  } catch {
    /* 后端不可用，本地偏好仍然生效 */
  }
})

const savingText = computed(() => (savingPref.value ? t('settings.saving') : ''))
</script>

<template>
  <div>
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
        <section class="settings-card">
          <header class="settings-card-title">
            <ShieldCheck :size="16" class="card-ico" />
            <span>{{ t('settings.security') || '安全与登录' }}</span>
          </header>
          <p class="auth-hint">
            <template v-if="auth.state.value.auth_required">
              登录已开启 —
              <button class="btn-link" @click="handleLogout">退出</button>
              ·
              <button class="btn-link" @click="handleToggleAuth">关闭</button>
            </template>
            <template v-else>
              登录已关闭 —
              <button
                class="btn-link"
                :disabled="!auth.state.value.has_password"
                :title="auth.state.value.has_password ? '' : '请先设置密码'"
                @click="handleToggleAuth"
              >
                开启
              </button>
            </template>
          </p>
          <label class="auth-label">
            设置/修改密码（至少 4 位）
            <input
              v-model="newPassword"
              class="auth-input"
              type="password"
              placeholder="新密码"
              autocomplete="new-password"
            />
          </label>
          <label class="auth-label">
            确认密码
            <input
              v-model="confirmPassword"
              class="auth-input"
              type="password"
              placeholder="再次输入密码"
              autocomplete="new-password"
            />
          </label>
          <p class="auth-warning">
            <AlertTriangle :size="13" class="auth-warning-ico" />
            请牢记密码，忘记密码将无法恢复。
          </p>
          <div class="auth-actions">
            <button
              class="btn btn-small"
              :disabled="passwordBusy || newPassword.length < 4 || newPassword !== confirmPassword"
              @click="handleSetPassword"
            >
              <ShieldCheck :size="13" />
              保存密码
            </button>
            <span class="muted auth-status">
              {{ auth.state.value.has_password ? '已有密码' : '尚未设置' }}
            </span>
          </div>
          <p v-if="auth.state.value.auth_required && !auth.state.value.has_password" class="auth-warning">
            <AlertTriangle :size="13" />
            登录已开启但尚未设置密码，当前任何人都可以访问
          </p>
        </section>

        <!-- Theme -->
        <section class="settings-card">
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

        <!-- Accent -->
        <section class="settings-card">
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
        <section class="settings-card">
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
        <section class="settings-card">
          <header class="settings-card-title">
            <Timer :size="16" class="card-ico" />
            <span>刷新间隔</span>
          </header>
          <p class="settings-hint">端口数据自动刷新频率（设为手动则需手动刷新）</p>
          <div class="radio-2col">
            <label class="radio-pill" :class="{ active: refreshInterval === 0 }">
              <input
                type="radio"
                name="pv-refresh"
                :value="0"
                :checked="refreshInterval === 0"
                @change="() => onRefreshIntervalChange(0)"
              />
              <span>手动</span>
            </label>
            <label class="radio-pill" :class="{ active: refreshInterval === 10 }">
              <input
                type="radio"
                name="pv-refresh"
                :value="10"
                :checked="refreshInterval === 10"
                @change="() => onRefreshIntervalChange(10)"
              />
              <span>10 秒</span>
            </label>
            <label class="radio-pill" :class="{ active: refreshInterval === 15 }">
              <input
                type="radio"
                name="pv-refresh"
                :value="15"
                :checked="refreshInterval === 15"
                @change="() => onRefreshIntervalChange(15)"
              />
              <span>15 秒</span>
            </label>
            <label class="radio-pill" :class="{ active: refreshInterval === 30 }">
              <input
                type="radio"
                name="pv-refresh"
                :value="30"
                :checked="refreshInterval === 30"
                @change="() => onRefreshIntervalChange(30)"
              />
              <span>30 秒</span>
            </label>
          </div>
        </section>

        <!-- About -->
        <section class="settings-card">
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

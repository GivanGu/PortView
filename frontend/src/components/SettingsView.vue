<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { setLocale } from '@/i18n'
import { getPrefs, patchPrefs, resetPrefs, getAccessAddress, setAccessAddress, type UserPrefs } from '@/api'
import useAuth from '@/store/auth'
import usePrefs from '@/store/prefs'
import { Settings, Sun, Moon, Languages, RotateCcw, Palette, Check, ShieldCheck, Timer, AlertTriangle, Globe, Layers } from 'lucide-vue-next'

const { t, locale } = useI18n()

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
const { refreshInterval, setRefreshInterval, logoScrim, setLogoScrim } = usePrefs()
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

// v1.5.2：卡片 Logo 背景的可读性遮罩档位
function onLogoScrimChange(v: 'none' | 'left' | 'overlay' | 'glass') {
  setLogoScrim(v)
  void persistPartial({ logo_scrim: v })
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
  setLogoScrim('left')
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
    }
  } catch {
    /* 后端不可用，本地偏好仍然生效 */
  }
  void loadAccessAddress()
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

        <!-- v1.5.2：Logo 遮罩 -->
        <section class="settings-card">
          <header class="settings-card-title">
            <Layers :size="16" class="card-ico" />
            <span>{{ t('settings.logoScrim') }}</span>
          </header>
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
        </section>

        <!-- Access Address -->
        <section class="settings-card" id="settings-access-address">
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

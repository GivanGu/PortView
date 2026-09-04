<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { setLocale } from '@/i18n'
import { getPrefs, patchPrefs, resetPrefs, type UserPrefs } from '@/api'
import { Settings, Sun, Moon, Languages, RotateCcw, Palette, Check } from 'lucide-vue-next'

const { t, locale } = useI18n()

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

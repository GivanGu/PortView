import { createI18n } from 'vue-i18n'
import zh from './locales/zh.json'
import en from './locales/en.json'

const LANG_KEY = 'portview.lang'

function detectLocale(): 'zh' | 'en' {
  try {
    const saved = localStorage.getItem(LANG_KEY)
    if (saved === 'zh' || saved === 'en') return saved
  } catch {
    /* ignore */
  }
  const nav = typeof navigator !== 'undefined' ? (navigator.language || 'en') : 'en'
  return nav.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

export function setLocale(lang: 'zh' | 'en') {
  try {
    localStorage.setItem(LANG_KEY, lang)
  } catch {
    /* ignore */
  }
}

export const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: 'en',
  messages: {
    zh,
    en,
  },
})

export default i18n

/**
 * 认证状态管理（Pinia）。
 *
 * 单用户模式：首次运行初始化默认密码 `portview123`，
 * 后端 SQLite 存储密码哈希。JWT 存 localStorage。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, fetchMe } from '@/api'

const TOKEN_KEY = 'portview.token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<null | { username: string }>(null)
  const initialized = ref(false)

  const isAuthenticated = computed(() => !!token.value)

  async function init() {
    if (token.value) {
      try {
        const res = await fetchMe()
        if (res.success) {
          user.value = res.data
        } else {
          token.value = null
          localStorage.removeItem(TOKEN_KEY)
        }
      } catch {
        token.value = null
        localStorage.removeItem(TOKEN_KEY)
      }
    }
    initialized.value = true
  }

  async function login(password: string): Promise<boolean> {
    try {
      const res = await apiLogin(password)
      if (res.success && res.data?.token) {
        token.value = res.data.token
        user.value = res.data.user || { username: 'admin' }
        localStorage.setItem(TOKEN_KEY, res.data.token)
        return true
      }
      return false
    } catch {
      return false
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
  }

  return {
    token,
    user,
    isAuthenticated,
    initialized,
    login,
    logout,
    init,
  }
})

// 路由守卫
export function authGuard() {
  const auth = useAuthStore()
  if (!auth.initialized) return null  // 还在初始化，放行等待
  return auth.isAuthenticated ? true : '/login'
}

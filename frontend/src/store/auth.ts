import { ref, readonly, type Ref } from 'vue'
import {
  authMe,
  login as loginApi,
  logout as logoutApi,
  setPassword as setPasswordApi,
  setAuthEnabled as setAuthEnabledApi,
  type AuthMe,
} from '@/api'

const state: Ref<AuthMe> = ref({ auth_required: false, logged_in: true, has_password: false })
const refreshing = ref(false)

async function refresh(force = false): Promise<AuthMe> {
  if (refreshing.value && !force) return state.value
  refreshing.value = true
  try {
    const resp = await authMe()
    state.value = resp.data
  } catch (e) {
    console.warn('auth check failed', e)
  } finally {
    refreshing.value = false
  }
  return state.value
}

async function doLogin(password: string) {
  await loginApi(password)
  await refresh(true)
}

async function doLogout() {
  await logoutApi()
  await refresh(true)
}

async function doSetPassword(pw: string) {
  await setPasswordApi(pw)
  await refresh(true)
}

async function doToggle(enabled: boolean) {
  await setAuthEnabledApi(enabled)
  await refresh(true)
}

/** 返回只读 reactive 视图 + 动作集合。组件用法：
 *  const { state, refresh, doLogin, doLogout, doSetPassword, doToggle } = useAuth()
 */
export function useAuth() {
  return {
    state: readonly(state),
    refreshing: readonly(refreshing),
    refresh,
    doLogin,
    doLogout,
    doSetPassword,
    doToggle,
  }
}

export default useAuth

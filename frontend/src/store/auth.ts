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
  // v1.4.5：设密码 = 自动开启登录保护。
  // 此前「设置密码」与「开启登录保护」是两个独立开关：从设置页设密码只调
  // set_password（后端会撤销会话但不改 auth_required），导致设完密码重开应用
  // 仍不要求登录。现在设密码后若未开启则自动开启。
  // 注意：开启会撤销当前会话，调用方需自行 doLogin 重新建立会话。
  const me = await refresh(true)
  if (!me.auth_required) {
    await setAuthEnabledApi(true)
    await refresh(true)
  }
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

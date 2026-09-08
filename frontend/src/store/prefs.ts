import { ref, readonly, type Ref } from 'vue'

/** 全局偏好共享状态：刷新间隔等跨组件需实时同步的值。
 * App.vue 依据它驱动自动刷新定时器；SettingsView 修改时写入，二者保持同步。
 */
const refreshInterval: Ref<number> = ref(0)

function setRefreshInterval(v: number) {
  refreshInterval.value = v
}

export function usePrefs() {
  return {
    refreshInterval: readonly(refreshInterval),
    setRefreshInterval,
  }
}

export default usePrefs

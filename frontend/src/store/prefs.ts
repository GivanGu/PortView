import { ref, readonly, type Ref } from 'vue'

/** 全局偏好共享状态：刷新间隔等跨组件需实时同步的值。
 * App.vue 依据它驱动自动刷新定时器；SettingsView 修改时写入，二者保持同步。
 */
const refreshInterval: Ref<number> = ref(0)

// v1.4.4：手动刷新信号。顶栏「刷新」按钮自增一次，各视图 watch 它后重新拉数据。
const refreshTick = ref(0)

function setRefreshInterval(v: number) {
  refreshInterval.value = v
}

function triggerRefresh() {
  refreshTick.value++
}

export function usePrefs() {
  return {
    refreshInterval: readonly(refreshInterval),
    setRefreshInterval,
    refreshTick: readonly(refreshTick),
    triggerRefresh,
  }
}

export default usePrefs

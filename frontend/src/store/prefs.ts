import { ref, readonly, type Ref } from 'vue'

/** 全局偏好共享状态：刷新间隔等跨组件需实时同步的值。
 * App.vue 依据它驱动自动刷新定时器；SettingsView 修改时写入，二者保持同步。
 */
const refreshInterval: Ref<number> = ref(0)

// v1.4.4：手动刷新信号。顶栏「刷新」按钮自增一次，各视图 watch 它后重新拉数据。
const refreshTick = ref(0)

// v1.5.2：卡片 Logo 背景的可读性遮罩档位（none / left / overlay / glass）。
// 默认 left（左侧渐变）。PortsView 依据它给 .port-card-scrim 套对应样式。
export type LogoScrim = 'none' | 'left' | 'overlay' | 'glass'
const logoScrim: Ref<LogoScrim> = ref('left')

// v1.5.11：卡片 Logo 展示模式。
// background = Logo 铺满整卡作背景（logoScrim 生效）；box = 64px Logo 框 + 信息列。
// 默认 background。logoScrim 仅在 background 模式下有意义。
export type LogoDisplayMode = 'background' | 'box'
const logoDisplayMode: Ref<LogoDisplayMode> = ref('background')

function setRefreshInterval(v: number) {
  refreshInterval.value = v
}

function triggerRefresh() {
  refreshTick.value++
}

function setLogoScrim(v: LogoScrim) {
  logoScrim.value = v
}

function setLogoDisplayMode(v: LogoDisplayMode) {
  logoDisplayMode.value = v
}

export function usePrefs() {
  return {
    refreshInterval: readonly(refreshInterval),
    setRefreshInterval,
    refreshTick: readonly(refreshTick),
    triggerRefresh,
    logoScrim: readonly(logoScrim),
    setLogoScrim,
    logoDisplayMode: readonly(logoDisplayMode),
    setLogoDisplayMode,
  }
}

export default usePrefs

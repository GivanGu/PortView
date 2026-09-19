import { ref, readonly, type Ref } from 'vue'
import { patchPrefs } from '@/api'

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

// v1.5.5：收藏端口号数组（顺序 = 收藏页展示顺序）。
// 端口页卡片菜单切换收藏时写入；收藏页拖拽排序后整体 PATCH。
const favorites: Ref<number[]> = ref([])

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

// v1.6.4：收藏写入串行化。promise chain 保证连续 PATCH 按发出顺序到达服务端，
// 避免乱序覆盖（拖拽排序「顺序乱」根因）；失败回滚到最后一次成功持久化的值。
let favoritesChain: Promise<void> = Promise.resolve()
let lastSavedFavorites: number[] = []

function setFavorites(v: number[]) {
  favorites.value = v
  lastSavedFavorites = [...v]
}

function saveFavorites(next: number[]): Promise<boolean> {
  favorites.value = next
  const run = favoritesChain.then(async () => {
    try {
      const resp = await patchPrefs({ favorites: next })
      if (resp.success) {
        lastSavedFavorites = next
        return true
      }
    } catch (e) {
      console.error('收藏保存失败:', e)
    }
    // 仅当值仍由本次写入持有时回滚，避免覆盖更新的乐观更新
    if (favorites.value === next) favorites.value = [...lastSavedFavorites]
    return false
  })
  favoritesChain = run.then(() => undefined, () => undefined)
  return run
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
    favorites: readonly(favorites),
    setFavorites,
    saveFavorites,
  }
}

export default usePrefs

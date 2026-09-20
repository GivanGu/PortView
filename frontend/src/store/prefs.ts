import { ref, readonly, type Ref } from 'vue'
import { patchPrefs, type FavEntry, type FavFolder, type GridItem } from '@/api'

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

// v1.6.5：收藏网格（GridItem 数组，顺序 = 展示顺序）。
// port 条目带在线状态；url 条目为外部站点；folder 单层分组。
// 端口页卡片菜单切换收藏时写入；收藏页拖拽 / 增删后整体 PATCH。
const favorites: Ref<GridItem[]> = ref([])

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

// ── 收藏网格辅助（v1.6.5）────────────────────────────────

/** 生成唯一 id（前端本地用，后端不解析）。 */
export function uid(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`
}

/** 外部 URL 条目的 logoKey 派生：`url:<hostname>`（小写）。 */
export function urlLogoKey(url: string): string {
  try {
    const u = new URL(url.startsWith('http') ? url : `https://${url}`)
    return `url:${u.hostname.toLowerCase()}`
  } catch {
    return `url:${encodeURIComponent(url).slice(0, 64)}`
  }
}

/** 旧数据迁移（v1.6.4 及以前）：number[] → port 条目；对象原样保留。
 * 唯一收敛点在 setFavorites：localStorage / 服务端旧值都从这里进。 */
export function normalizeFavorites(raw: unknown): GridItem[] {
  if (!Array.isArray(raw)) return []
  const out: GridItem[] = []
  for (const it of raw) {
    if (typeof it === 'number') {
      out.push({ id: `port-${it}`, kind: 'port', port: it })
    } else if (it && typeof it === 'object' && (it as GridItem).kind === 'folder') {
      const f = it as FavFolder
      const items = (Array.isArray(f.items) ? f.items : []).filter(
        (e): e is FavEntry => !!e && (e.kind === 'port' || e.kind === 'url'),
      )
      out.push({ ...f, items })
    } else if (it && typeof it === 'object' && ((it as FavEntry).kind === 'port' || (it as FavEntry).kind === 'url')) {
      out.push(it as FavEntry)
    }
  }
  return out
}

/** 递归判断某端口是否已收藏（含文件夹内）。 */
export function hasPortFavorite(items: GridItem[], port: number): boolean {
  for (const it of items) {
    if (it.kind === 'folder') {
      if (it.items.some((e) => e.kind === 'port' && e.port === port)) return true
    } else if (it.kind === 'port' && it.port === port) return true
  }
  return false
}

/** 递归移除某端口的全部收藏条目（含文件夹内），返回 [新数组, 是否移除过]。 */
export function removePortFavorite(items: GridItem[], port: number): [GridItem[], boolean] {
  let removed = false
  const out: GridItem[] = []
  for (const it of items) {
    if (it.kind === 'folder') {
      const kept = it.items.filter((e) => !(e.kind === 'port' && e.port === port))
      if (kept.length !== it.items.length) removed = true
      out.push(kept.length === it.items.length ? it : { ...it, items: kept })
    } else if (it.kind === 'port' && it.port === port) {
      removed = true
    } else {
      out.push(it)
    }
  }
  return [out, removed]
}

// v1.6.4：收藏写入串行化。promise chain 保证连续 PATCH 按发出顺序到达服务端，
// 避免乱序覆盖（拖拽排序「顺序乱」根因）；失败回滚到最后一次成功持久化的值。
let favoritesChain: Promise<void> = Promise.resolve()
let lastSavedFavorites: GridItem[] = []

function setFavorites(v: GridItem[]) {
  favorites.value = normalizeFavorites(v)
  lastSavedFavorites = [...favorites.value]
}

function saveFavorites(next: GridItem[]): Promise<boolean> {
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
    // 不加 readonly()：深只读会把嵌套 items 也变只读，网格操作（reorder/move）需要可变类型
    favorites,
    setFavorites,
    saveFavorites,
  }
}

export default usePrefs

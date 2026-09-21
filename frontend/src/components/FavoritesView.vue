<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, watchEffect, type Component } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Star,
  Plus,
  Folder,
  Search,
  X,
  Heart,
  BookOpen,
  Gamepad2,
  Briefcase,
  Code2,
  Clapperboard,
  Music4,
  Coffee,
  Rocket,
  Shield,
  Globe,
  Cpu,
  Database,
  Server,
  Home,
  Zap,
  Palette,
  MessageSquare,
  ShoppingBag,
  Plane,
  Dumbbell,
  Wallet,
  Wifi,
  WifiOff,
} from 'lucide-vue-next'
import Sortable from 'sortablejs'
import {
  fetchPorts,
  fetchHiddenPortDetails,
  fetchLogos,
  fetchDefaultLogos,
  logoUrl,
  defaultLogoUrl,
  backgroundUrl,
  upsertNote,
  uploadLogo,
  fetchFavicon,
  type PortCard,
  type LogoMeta,
  type HiddenPortDetail,
  type NoteProtocol,
  type FavEntry,
  type FavFolder,
  type GridItem,
} from '@/api'
import { appKey, normalizeServiceName } from '@/logo'
import { usePrefs, uid, urlLogoKey, hasPortFavorite } from '@/store/prefs'
import { useSearch } from '@/store/search'
import { useFavStatus } from '@/store/favStatus'
import { useOpenService } from '@/composables/useOpenService'
import AccessAddressPrompt from '@/components/AccessAddressPrompt.vue'
import BackgroundLayer from '@/components/BackgroundLayer.vue'

const { t } = useI18n()
const {
  favorites,
  saveFavorites,
  refreshTick,
  triggerRefresh,
  backgroundSet,
  backgroundVersion,
  backgroundScope,
  backgroundBlur,
} = usePrefs()

// 分组预设图标（lucide，无需上传，右键菜单里挑选）
const FOLDER_ICON_MAP: Record<string, Component> = {
  Folder,
  Star,
  Heart,
  BookOpen,
  Gamepad2,
  Briefcase,
  Code2,
  Clapperboard,
  Music4,
  Coffee,
  Rocket,
  Shield,
  Globe,
  Cpu,
  Database,
  Server,
  Home,
  Zap,
  Palette,
  MessageSquare,
  ShoppingBag,
  Plane,
  Dumbbell,
  Wallet,
}

function folderIcon(f: FavFolder): Component {
  return (f.icon && FOLDER_ICON_MAP[f.icon]) || Folder
}

// 侧栏 hover 名称标签：Teleport 到 body 用 fixed 定位（图标右侧）。
// 不放在 .fav-group-list 内部 —— 该容器 overflow-y:auto 会强制 overflow-x:auto，
// 内部绝对定位的标签会撑出常驻横向滚动条。
const hoverLabel = ref<{ x: number; y: number; text: string } | null>(null)
function onGroupEnter(e: MouseEvent, text: string) {
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  hoverLabel.value = { x: rect.right + 8, y: rect.top + rect.height / 2, text }
}
function onGroupLeave() {
  hoverLabel.value = null
}
const { showAddrPrompt, loadManualSchemes, handleOpenService, onAddrConfigure, onAddrDismissed } = useOpenService()

const loading = ref(false)
const toast = ref('')
const toastVisible = ref(false)
let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(msg: string) {
  toast.value = msg
  toastVisible.value = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toastVisible.value = false), 2200)
}

const cards = ref<Map<number, PortCard>>(new Map())
const logos = ref<Map<string, LogoMeta>>(new Map())
const defaultLogoPorts = ref<Map<number, string>>(new Map())
const defaultLogoNames = ref<Set<string>>(new Set())
// <img> 加载失败的条目 id（回退首字母占位）
const logoFailed = ref<Set<string>>(new Set())

// ── 数据加载 ──
function toCard(h: HiddenPortDetail): PortCard {
  return {
    type: 'used',
    port: h.port,
    source: h.source ?? undefined,
    protocol: h.protocol ?? undefined,
    container: h.container ?? undefined,
    image: h.image ?? undefined,
    is_running: h.is_running,
    service_name: h.service_name ?? undefined,
    remark: h.remark || undefined,
  }
}

async function reloadLogos() {
  try {
    const resp = await fetchLogos()
    if (resp.success) {
      const lm = new Map<string, LogoMeta>()
      for (const meta of resp.data) lm.set(meta.app_key, meta)
      logos.value = lm
    }
  } catch (e) {
    console.error('加载 Logo 列表失败:', e)
  }
}

async function loadData() {
  loading.value = true
  try {
    // 四路相互独立，单路失败不影响其它数据渲染
    const [portsResp, hiddenResp, logosResp, defaultsResp] = await Promise.all([
      fetchPorts().catch(() => null),
      fetchHiddenPortDetails().catch(() => null),
      fetchLogos().catch(() => null),
      fetchDefaultLogos().catch(() => null),
    ])
    const m = new Map<number, PortCard>()
    if (portsResp?.success) {
      for (const c of portsResp.data.port_cards) {
        if (c.type === 'used' && c.port != null) m.set(c.port, c)
      }
    }
    if (hiddenResp?.success) {
      for (const h of hiddenResp.data) {
        if (!m.has(h.port)) m.set(h.port, toCard(h))
      }
    }
    cards.value = m
    if (logosResp?.success) {
      const lm = new Map<string, LogoMeta>()
      for (const meta of logosResp.data) lm.set(meta.app_key, meta)
      logos.value = lm
    }
    if (defaultsResp?.success) {
      const pm = new Map<number, string>()
      for (const [p, k] of Object.entries(defaultsResp.data.ports)) pm.set(Number(p), k)
      defaultLogoPorts.value = pm
      defaultLogoNames.value = new Set(defaultsResp.data.names)
    }
  } catch (e) {
    console.error('加载收藏数据失败:', e)
  } finally {
    loading.value = false
  }
}

// ── 网格模型（v1.6.5）：GridItem[]，port/url 条目 + 单层文件夹 ──
// v1.6.6：文件夹从网格磁贴改为左侧分组栏，网格只展示当前分组的条目。

interface FlatEntry {
  entry: FavEntry
  folder: FavFolder | null
}

// 全部条目（含文件夹内），用于搜索 / 离线筛选
const allEntries = computed<FlatEntry[]>(() => {
  const out: FlatEntry[] = []
  for (const it of favorites.value) {
    if (it.kind === 'folder') {
      for (const e of it.items) out.push({ entry: e, folder: it })
    } else {
      out.push({ entry: it, folder: null })
    }
  }
  return out
})

// 文件夹列表（左侧分组栏）
const folders = computed<FavFolder[]>(() =>
  favorites.value.filter((it): it is FavFolder => it.kind === 'folder'),
)
const entryCount = computed(() => allEntries.value.length)

// 当前选中的视图：null = 「全部」（所有条目），'online'/'offline' = 在线/离线视图，否则为文件夹 id
const selectedGroup = ref<string | null>(null)
const isOnlineView = computed(() => selectedGroup.value === 'online')
const isOfflineView = computed(() => selectedGroup.value === 'offline')
const isFolderView = computed(
  () =>
    selectedGroup.value != null &&
    selectedGroup.value !== 'online' &&
    selectedGroup.value !== 'offline',
)
const currentFolder = computed<FavFolder | null>(() => {
  if (!isFolderView.value) return null
  return folders.value.find((f) => f.id === selectedGroup.value) ?? null
})

function entryName(entry: FavEntry): string {
  if (entry.kind === 'port') {
    const card = entry.port != null ? cards.value.get(entry.port) : undefined
    return card?.remark || card?.service_name || String(entry.port ?? '')
  }
  return entry.title || entry.url || ''
}

function isOfflineEntry(entry: FavEntry): boolean {
  if (entry.kind !== 'port') return false
  const card = entry.port != null ? cards.value.get(entry.port) : undefined
  return card == null || card.is_running === false
}

// ── Logo 解析：port 条目走 用户Logo > 内置默认；url 条目走 上传Logo ──
function defaultLogoKey(card: PortCard): string | null {
  if (card.port != null && defaultLogoPorts.value.has(card.port)) {
    return defaultLogoPorts.value.get(card.port)!
  }
  if (card.service_name) {
    const norm = normalizeServiceName(card.service_name)
    if (defaultLogoNames.value.has(norm)) return norm
  }
  return null
}

function entryLogoSrc(entry: FavEntry): string | undefined {
  if (logoFailed.value.has(entry.id)) return undefined
  if (entry.kind === 'port') {
    const card = entry.port != null ? cards.value.get(entry.port) : undefined
    if (!card) return undefined
    const key = appKey(card)
    if (logos.value.get(key)?.status === 'found') return logoUrl(key)
    const dkey = defaultLogoKey(card)
    if (dkey) return defaultLogoUrl(dkey)
    return undefined
  }
  if (entry.logoKey && logos.value.get(entry.logoKey)?.status === 'found') return logoUrl(entry.logoKey)
  return undefined
}

function onLogoError(entryId: string) {
  const s = new Set(logoFailed.value)
  s.add(entryId)
  logoFailed.value = s
}

// url 条目 favicon 自动抓取（服务端抓取，幂等；本会话每个 key 只尝试一次）
const faviconPending = new Set<string>()
// 后端拒绝（非法 URL 等）或网络错误：未落终态记录，标记后本会话不再重试，避免无限重抓
const faviconFailed = new Set<string>()
function ensureUrlFavicons() {
  for (const { entry } of allEntries.value) {
    if (entry.kind !== 'url' || !entry.url || !entry.logoKey) continue
    const key = entry.logoKey
    const status = logos.value.get(key)?.status
    if (status === 'found' || status === 'not_found' || faviconPending.has(key) || faviconFailed.has(key))
      continue
    faviconPending.add(key)
    fetchFavicon(key, entry.url)
      .then((resp) => {
        if (!resp.success) faviconFailed.add(key)
      })
      .catch(() => {
        faviconFailed.add(key)
      })
      .finally(() => {
        faviconPending.delete(key)
        void reloadLogos()
      })
  }
}

// ── 搜索（过滤时扁平展示，隐藏分组结构）──
// v1.6.6：搜索词来自顶栏全局搜索（store 单例，切页自动清空）
const { query: search, activeTab } = useSearch()
const searching = computed(() => search.value.trim() !== '')

function entryMatches(entry: FavEntry, folder: FavFolder | null, q: string): boolean {
  if (entryName(entry).toLowerCase().includes(q)) return true
  if (entry.kind === 'url' && entry.url?.toLowerCase().includes(q)) return true
  if (folder && folder.name.toLowerCase().includes(q)) return true
  return false
}

// 网格展示的条目：搜索 → 扁平匹配；在线/离线 → 扁平视图；文件夹 → 组内条目；「全部」→ 所有条目
const visible = computed<FavEntry[]>(() => {
  const q = search.value.trim().toLowerCase()
  if (q) {
    const out: FavEntry[] = []
    for (const { entry, folder } of allEntries.value) {
      if (!entryMatches(entry, folder, q)) continue
      out.push(entry)
    }
    return out
  }
  if (isOnlineView.value) return allEntries.value.filter((fe) => !isOfflineEntry(fe.entry)).map((fe) => fe.entry)
  if (isOfflineView.value) return allEntries.value.filter((fe) => isOfflineEntry(fe.entry)).map((fe) => fe.entry)
  if (isFolderView.value) {
    const f = currentFolder.value
    return f ? f.items : []
  }
  return allEntries.value.map((fe) => fe.entry)
})

// 当前视图名称（状态栏计数器用）
const currentGroupName = computed(() => {
  if (isOnlineView.value) return t('favorites.onlineGroup')
  if (isOfflineView.value) return t('favorites.offlineGroup')
  if (isFolderView.value) return currentFolder.value?.name ?? ''
  return t('favorites.allGroup')
})

// ── 状态栏计数器联动（本页写入，App.vue 状态栏读取）──
const { setFavStatus } = useFavStatus()
watchEffect(() => {
  const active = activeTab.value === 'favorites'
  const list = visible.value
  const off = list.filter((e) => isOfflineEntry(e)).length
  setFavStatus({
    active,
    group: active ? currentGroupName.value : '',
    total: active ? list.length : 0,
    offline: active ? off : 0,
    online: active ? list.length - off : 0,
  })
})

// ── 数据归一：根目录不再是合法位置（添加只允许在文件夹内）──
// 加载时静默把根条目迁入第一个文件夹（无文件夹则建「默认分组」收它们）；
// 无任何条目且无文件夹时建空「默认分组」，保证始终至少有一个分组。
function normalizeFavoritesData() {
  const root = favorites.value.filter((it): it is FavEntry => it.kind !== 'folder')
  const first = folders.value[0]
  if (root.length > 0) {
    if (first) {
      saveFavorites(
        favorites.value
          .filter((it) => it.kind === 'folder')
          .map((it) => (it.id === first.id ? { ...it, items: [...it.items, ...root] } : it)),
      )
    } else {
      saveFavorites([
        ...favorites.value.filter((it) => it.kind === 'folder'),
        { id: uid('folder'), kind: 'folder', name: t('favorites.defaultFolder'), icon: 'Folder', items: root },
      ])
    }
    return
  }
  if (folders.value.length === 0) {
    saveFavorites([
      ...favorites.value,
      { id: uid('folder'), kind: 'folder', name: t('favorites.defaultFolder'), icon: 'Folder', items: [] },
    ])
  }
}
watch(favorites, () => normalizeFavoritesData(), { immediate: true })

// ── 变更操作（全部整体 PATCH，走 saveFavorites 串行写入）──
function addEntry(targetFolderId: string | null, entry: FavEntry) {
  if (targetFolderId) {
    saveFavorites(
      favorites.value.map((it) =>
        it.kind === 'folder' && it.id === targetFolderId ? { ...it, items: [...it.items, entry] } : it,
      ),
    )
  } else {
    saveFavorites([...favorites.value, entry])
  }
}

function removeEntry(entryId: string) {
  const next: GridItem[] = []
  for (const it of favorites.value) {
    if (it.kind === 'folder') next.push({ ...it, items: it.items.filter((e) => e.id !== entryId) })
    else if (it.id !== entryId) next.push(it)
  }
  saveFavorites(next)
}

function moveEntry(entryId: string, targetFolderId: string | null) {
  let moved: FavEntry | null = null
  const stripped: GridItem[] = []
  for (const it of favorites.value) {
    if (it.kind === 'folder') {
      const kept: FavEntry[] = []
      for (const e of it.items) {
        if (e.id === entryId) moved = e
        else kept.push(e)
      }
      stripped.push(kept.length === it.items.length ? it : { ...it, items: kept })
    } else if (it.id === entryId) {
      moved = it
    } else {
      stripped.push(it)
    }
  }
  if (!moved) return
  if (targetFolderId) {
    for (let i = 0; i < stripped.length; i++) {
      const it = stripped[i]
      if (it.kind === 'folder' && it.id === targetFolderId) {
        stripped[i] = { ...it, items: [...it.items, moved] }
      }
    }
  } else {
    stripped.push(moved)
  }
  saveFavorites(stripped)
}

function addFolder(name: string, icon: string) {
  saveFavorites([...favorites.value, { id: uid('folder'), kind: 'folder', name, icon, items: [] }])
}

function saveFolderMeta(id: string, name: string, icon: string) {
  saveFavorites(
    favorites.value.map((it) => (it.kind === 'folder' && it.id === id ? { ...it, name, icon } : it)),
  )
}

function deleteFolder(id: string) {
  const folder = favorites.value.find((it) => it.kind === 'folder' && it.id === id)
  if (!folder || folder.kind !== 'folder') return
  const rest = favorites.value.filter((it) => !(it.kind === 'folder' && it.id === id))
  saveFavorites([...rest, ...folder.items])
  // 删除的是当前选中分组 → 回到「全部」
  if (selectedGroup.value === id) selectedGroup.value = null
}

// 重排文件夹（保持根条目位置不动，仅重排文件夹项）
function reorderFolders(oldIndex: number, newIndex: number): GridItem[] {
  const fs = [...folders.value]
  const [m] = fs.splice(oldIndex, 1)
  fs.splice(newIndex, 0, m)
  let i = 0
  return favorites.value.map((it) => (it.kind === 'folder' ? fs[i++] : it))
}

// 重排某文件夹内部条目
function reorderInFolder(oldIndex: number, newIndex: number, folderId: string): GridItem[] {
  return favorites.value.map((it) => {
    if (it.kind !== 'folder' || it.id !== folderId) return it
    const sub = [...it.items]
    const [m] = sub.splice(oldIndex, 1)
    sub.splice(newIndex, 0, m)
    return { ...it, items: sub }
  })
}

// ── 打开 / 点击 ──
function openEntry(entry: FavEntry) {
  if (entry.kind === 'port') {
    const card = entry.port != null ? cards.value.get(entry.port) : undefined
    void handleOpenService(card ?? { type: 'used', port: entry.port })
  } else if (entry.url) {
    window.open(entry.url, '_blank', 'noopener')
  }
}

// ── 右键菜单 ──
type CtxTarget =
  | { kind: 'entry'; entry: FavEntry; folder: FavFolder | null }
  | { kind: 'folder'; folder: FavFolder }
  | { kind: 'root' }
const ctxMenu = ref<{ x: number; y: number; target: CtxTarget } | null>(null)

function clampMenu(e: MouseEvent): { x: number; y: number } {
  const menuWidth = 200
  const menuHeight = 320
  let x = e.clientX
  let y = e.clientY
  if (x + menuWidth > window.innerWidth) x = Math.max(8, window.innerWidth - menuWidth - 8)
  if (y + menuHeight > window.innerHeight) y = Math.max(8, window.innerHeight - menuHeight - 8)
  return { x, y }
}

function findFolderOf(entryId: string): FavFolder | null {
  for (const it of favorites.value) {
    if (it.kind === 'folder' && it.items.some((e) => e.id === entryId)) return it
  }
  return null
}

function openEntryMenuAt(entry: FavEntry, e: MouseEvent) {
  ctxMenu.value = { ...clampMenu(e), target: { kind: 'entry', entry, folder: findFolderOf(entry.id) } }
}
function openFolderMenu(folder: FavFolder, e: MouseEvent) {
  ctxMenu.value = { ...clampMenu(e), target: { kind: 'folder', folder } }
}
function openRootMenu(e: MouseEvent) {
  ctxMenu.value = { ...clampMenu(e), target: { kind: 'root' } }
}
// 网格空白处右键：仅文件夹视图弹出「添加」菜单（根下不允许添加）
function onGridContextMenu(e: MouseEvent) {
  if (!isFolderView.value) return
  e.preventDefault()
  openRootMenu(e)
}
function closeCtxMenu() {
  ctxMenu.value = null
}

// 模板用收窄后的 computed（vue-tsc 不跨 <template v-if> 收窄联合类型）
const ctxEntry = computed(() => {
  const t = ctxMenu.value?.target
  return t && t.kind === 'entry' ? t : null
})
// 扁平视图（全部/在线/离线/搜索）只读：不允许增删，仅文件夹视图内可移除
const ctxCanRemove = computed(() => {
  const t = ctxMenu.value?.target
  return t?.kind === 'entry' && isFolderView.value && !searching.value
})
const ctxFolder = computed(() => {
  const t = ctxMenu.value?.target
  return t && t.kind === 'folder' ? t : null
})

function onScrollCloseMenu() {
  if (ctxMenu.value) closeCtxMenu()
}
function onKeydownCloseMenu(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    if (ctxMenu.value) ctxMenu.value = null
    if (nameModal.value) nameModal.value = null
  }
}
function onResizeCloseMenu() {
  if (ctxMenu.value) closeCtxMenu()
}

function otherFolders(excludeId: string | null): FavFolder[] {
  return folders.value.filter((f) => f.id !== excludeId)
}

function onCtxMoveTo(folderId: string) {
  const target = ctxMenu.value?.target
  if (target?.kind !== 'entry') return
  closeCtxMenu()
  moveEntry(target.entry.id, folderId)
}
function onCtxRemoveEntry() {
  const target = ctxMenu.value?.target
  if (target?.kind !== 'entry') return
  closeCtxMenu()
  removeEntry(target.entry.id)
  showToast(t('ports.removedFavorite'))
}
function onCtxRemoveFolder() {
  const target = ctxMenu.value?.target
  if (target?.kind !== 'folder') return
  closeCtxMenu()
  if (!confirm(t('favorites.deleteFolderConfirm', { name: target.folder.name }))) return
  deleteFolder(target.folder.id)
}

// ── 拖拽排序（sortablejs）＋ 拖入分组（悬停检测）──
const gridEl = ref<HTMLElement | null>(null)
const folderListEl = ref<HTMLElement | null>(null)
let rootSortable: Sortable | null = null
let folderSortable: Sortable | null = null
const dragOverFolderId = ref<string | null>(null)

function destroySortables() {
  rootSortable?.destroy()
  rootSortable = null
  folderSortable?.destroy()
  folderSortable = null
  // 拖拽中卸载组件时 onEnd 不会触发，需在此兜底移除悬停检测监听
  window.removeEventListener('mousemove', onRootDragMove)
}

function onRootDragMove(e: MouseEvent) {
  const el = document.elementFromPoint(e.clientX, e.clientY)
  const tile = el?.closest?.('[data-folder-id]') as HTMLElement | null
  dragOverFolderId.value = tile?.dataset.folderId ?? null
}

// 网格：条目排序 + 拖到左侧分组栏移动（仅文件夹视图；扁平视图禁用拖拽）
function setupRootSortable() {
  rootSortable?.destroy()
  rootSortable = null
  if (loading.value || searching.value || !isFolderView.value || visible.value.length === 0 || !gridEl.value) return
  rootSortable = Sortable.create(gridEl.value, {
    animation: 150,
    group: 'fav-entries', // 独立分组：条目不会跨入侧栏文件夹列表
    filter: '.fav-add-tile', // 「+」磁贴不可拖
    onStart: (evt) => {
      // 拖拽中的节点自身会挡住 elementFromPoint 命中检测，需排除
      ;(evt.item as HTMLElement).style.pointerEvents = 'none'
      window.addEventListener('mousemove', onRootDragMove)
    },
    onEnd: (evt) => {
      ;(evt.item as HTMLElement).style.pointerEvents = ''
      window.removeEventListener('mousemove', onRootDragMove)
      const id = evt.item.dataset.id
      const over = dragOverFolderId.value
      dragOverFolderId.value = null
      if (!id) return
      // 拖到左侧分组栏的某个文件夹 → 移入（「全部」不接受拖放，根目录不再是合法位置）
      if (over) {
        moveEntry(id, over)
        return
      }
      const { oldIndex, newIndex } = evt
      if (oldIndex == null || newIndex == null || oldIndex === newIndex) return
      // 仅文件夹视图启用拖拽 → 重排该文件夹内部
      const gid = selectedGroup.value
      if (gid && gid !== 'online' && gid !== 'offline') {
        saveFavorites(reorderInFolder(oldIndex, newIndex, gid))
      }
    },
  })
}

// 左侧分组栏：文件夹排序
function setupFolderSortable() {
  folderSortable?.destroy()
  folderSortable = null
  if (!folderListEl.value || folders.value.length < 2) return
  folderSortable = Sortable.create(folderListEl.value, {
    animation: 150,
    group: 'fav-folders', // 独立分组：侧栏文件夹不接受网格条目拖入
    handle: '.fav-group-item',
    onEnd: (evt) => {
      const { oldIndex, newIndex } = evt
      if (oldIndex == null || newIndex == null || oldIndex === newIndex) return
      saveFavorites(reorderFolders(oldIndex, newIndex))
    },
  })
}

watch(
  [loading, searching, selectedGroup, () => visible.value.length],
  () => {
    void nextTick(() => setupRootSortable())
  },
)
watch(
  () => folders.value.length,
  () => {
    void nextTick(() => setupFolderSortable())
  },
)

// ── 添加弹窗 ──
const addModal = ref<{ folderId: string | null } | null>(null)
const addTab = ref<'port' | 'url'>('port')
const addPortQuery = ref('')
const addTitle = ref('')
const addUrl = ref('')
const addFile = ref<File | null>(null)
const addFilePreview = ref('')
const addBusy = ref(false)

function openAddModal(folderId: string | null) {
  closeCtxMenu()
  addTab.value = 'port'
  addPortQuery.value = ''
  addTitle.value = ''
  addUrl.value = ''
  if (addFilePreview.value) URL.revokeObjectURL(addFilePreview.value)
  addFile.value = null
  addFilePreview.value = ''
  addModal.value = { folderId }
}

const portCandidates = computed(() => {
  const q = addPortQuery.value.trim().toLowerCase()
  const list = [...cards.value.values()].filter((c) => c.port != null)
  const filtered = q
    ? list.filter((c) => {
        const name = (c.remark || c.service_name || String(c.port)).toLowerCase()
        return name.includes(q) || String(c.port).includes(q)
      })
    : list
  return filtered.sort((a, b) => (a.port ?? 0) - (b.port ?? 0))
})

function addPortEntry(card: PortCard) {
  if (card.port == null || !addModal.value) return
  if (hasPortFavorite(favorites.value, card.port)) return
  addEntry(addModal.value.folderId, { id: uid('port'), kind: 'port', port: card.port })
  addModal.value = null
  showToast(t('ports.addedFavorite'))
}

function readImageFile(file: File): Promise<{ mime: string; b64: string }> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => {
      const dataUrl = String(r.result)
      resolve({ mime: file.type, b64: dataUrl.split(',')[1] || '' })
    }
    r.onerror = () => reject(r.error)
    r.readAsDataURL(file)
  })
}

function onAddFilePicked(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0] ?? null
  addFile.value = file
  if (addFilePreview.value) URL.revokeObjectURL(addFilePreview.value)
  addFilePreview.value = file ? URL.createObjectURL(file) : ''
}

async function saveUrlEntry() {
  const target = addModal.value
  if (!target) return
  const title = addTitle.value.trim()
  let raw = addUrl.value.trim()
  if (!raw) {
    showToast(t('favorites.urlInvalid'))
    return
  }
  if (!/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(raw)) raw = `https://${raw}`
  let normalized: URL
  try {
    normalized = new URL(raw)
  } catch {
    showToast(t('favorites.urlInvalid'))
    return
  }
  // 仅 http(s) 可抓取 favicon；其它 scheme 拒绝，避免后端拒收后前端无限重抓
  if (normalized.protocol !== 'http:' && normalized.protocol !== 'https:') {
    showToast(t('favorites.urlInvalid'))
    return
  }
  const url = normalized.toString()
  const key = urlLogoKey(url)
  const file = addFile.value
  addBusy.value = true
  if (file) {
    if (file.size > 1024 * 1024) {
      showToast(t('favorites.logoTooLarge'))
    } else {
      try {
        const { mime, b64 } = await readImageFile(file)
        const resp = await uploadLogo(key, mime, b64)
        if (!resp.success) showToast(t('favorites.logoUploadFailed'))
      } catch {
        showToast(t('favorites.logoUploadFailed'))
      }
    }
  }
  addEntry(target.folderId, {
    id: uid('url'),
    kind: 'url',
    url,
    title: title || normalized.hostname,
    logoKey: key,
  })
  addBusy.value = false
  addModal.value = null
  showToast(t('favorites.added'))
  // favicon 抓取统一由 ensureUrlFavicons 负责（addEntry 已触发 watch），此处不再重复请求
}

// ── 更换图标（url 条目 / 任意条目的手动 Logo）──
const logoInputRef = ref<HTMLInputElement | null>(null)
const logoTargetId = ref<string | null>(null)

function openChangeLogo(entry: FavEntry) {
  closeCtxMenu()
  logoTargetId.value = entry.id
  logoInputRef.value?.click()
}

async function onLogoFilePicked(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  const entryId = logoTargetId.value
  logoTargetId.value = null
  if (!file || !entryId) return
  if (file.size > 1024 * 1024) {
    showToast(t('favorites.logoTooLarge'))
    return
  }
  const entry = allEntries.value.find((fe) => fe.entry.id === entryId)?.entry
  if (!entry || !entry.logoKey) return
  try {
    const { mime, b64 } = await readImageFile(file)
    const resp = await uploadLogo(entry.logoKey, mime, b64)
    if (resp.success) {
      const s = new Set(logoFailed.value)
      s.delete(entry.id)
      logoFailed.value = s
      await reloadLogos()
      showToast(t('favorites.logoAdded'))
    } else {
      showToast(t('favorites.logoUploadFailed'))
    }
  } catch {
    showToast(t('favorites.logoUploadFailed'))
  }
}

// ── 新建 / 重命名分组弹窗（名称 + 图标一体，v1.6.6 统一入口）──
const nameModal = ref<{ mode: 'new' | 'rename'; folderId?: string } | null>(null)
const nameInput = ref('')
const iconInput = ref('Folder')

function openNewGroup() {
  nameInput.value = ''
  iconInput.value = 'Folder'
  nameModal.value = { mode: 'new' }
}
function openRenameFolder(folder: FavFolder) {
  closeCtxMenu()
  nameInput.value = folder.name
  iconInput.value = folder.icon || 'Folder'
  nameModal.value = { mode: 'rename', folderId: folder.id }
}
function saveNameModal() {
  const name = nameInput.value.trim()
  if (!name || !nameModal.value) return
  if (nameModal.value.mode === 'new') {
    addFolder(name, iconInput.value)
  } else if (nameModal.value.folderId) {
    saveFolderMeta(nameModal.value.folderId, name, iconInput.value)
  }
  nameModal.value = null
}

function pickModalIcon(name: string) {
  iconInput.value = name
}

// ── 名称/备注编辑弹窗（port=备注，与端口页同步；url=显示名称）──
const nameEditModal = ref<{ entry: FavEntry } | null>(null)
const nameEditInput = ref('')

function openNameEdit(entry: FavEntry) {
  closeCtxMenu()
  nameEditInput.value =
    entry.kind === 'port'
      ? ((entry.port != null ? cards.value.get(entry.port)?.remark : undefined) || '')
      : entry.title || ''
  nameEditModal.value = { entry }
}

async function saveNameEdit() {
  const target = nameEditModal.value
  if (!target) return
  const entry = target.entry
  const val = nameEditInput.value.trim()
  if (entry.kind === 'port') {
    if (entry.port == null) return
    const card = cards.value.get(entry.port)
    if (!card) return
    try {
      const protocol = ((card.protocol || '').toLowerCase() || '') as NoteProtocol
      const resp = await upsertNote({
        port: entry.port,
        service_name: card.service_name ?? '',
        protocol,
        remark: val,
      })
      if (resp.success) {
        card.remark = val || undefined
        triggerRefresh()
        nameEditModal.value = null
      } else {
        showToast(t('common.saveFailed'))
      }
    } catch (e) {
      console.error('保存备注失败:', e)
      showToast(t('common.saveFailed'))
    }
  } else {
    renameEntry(entry.id, val)
    nameEditModal.value = null
  }
}

// 重命名 url 条目（改 title，根/文件夹内均可）
function renameEntry(entryId: string, title: string) {
  const next: GridItem[] = []
  for (const it of favorites.value) {
    if (it.kind === 'folder') {
      next.push({
        ...it,
        items: it.items.map((e) => (e.id === entryId && e.kind === 'url' ? { ...e, title } : e)),
      })
    } else if (it.id === entryId && it.kind === 'url') {
      next.push({ ...it, title })
    } else {
      next.push(it)
    }
  }
  saveFavorites(next)
}

// ── 生命周期 ──
watch(refreshTick, () => {
  if (!loading.value) loadData()
})
watch([() => favorites.value, () => logos.value], () => {
  if (!loading.value) ensureUrlFavicons()
})

onMounted(() => {
  void loadData()
  void loadManualSchemes()
  window.addEventListener('scroll', onScrollCloseMenu, true)
  window.addEventListener('keydown', onKeydownCloseMenu)
  window.addEventListener('resize', onResizeCloseMenu)
})
onBeforeUnmount(() => {
  destroySortables()
  if (addFilePreview.value) URL.revokeObjectURL(addFilePreview.value)
  window.removeEventListener('scroll', onScrollCloseMenu, true)
  window.removeEventListener('keydown', onKeydownCloseMenu)
  window.removeEventListener('resize', onResizeCloseMenu)
})
</script>

<template>
  <div class="favorites-view" :class="{ 'has-bg': backgroundSet && backgroundScope === 'favorites' }">
    <BackgroundLayer
      v-if="backgroundSet && backgroundScope === 'favorites'"
      :src="backgroundUrl(backgroundVersion)"
      :blur="backgroundBlur"
    />
    <div class="main-body">
      <div v-if="loading" class="empty-state">
        <div class="empty-text">{{ t('common.loading') }}</div>
      </div>

      <template v-else>
        <div class="fav-layout">
          <!-- 左侧分组栏：WeTab 式窄坞（纯图标 + hover 浮出名称，搜索时隐藏） -->
          <aside v-if="!searching" class="fav-sidebar">
            <div
              class="fav-group-item all"
              :class="{ active: selectedGroup === null }"
              @click="selectedGroup = null"
              @mouseenter="onGroupEnter($event, t('favorites.allGroup'))"
              @mouseleave="onGroupLeave"
            >
              <Star :size="20" class="fav-group-ico" />
            </div>

            <div
              class="fav-group-item"
              :class="{ active: selectedGroup === 'online' }"
              @click="selectedGroup = 'online'"
              @mouseenter="onGroupEnter($event, t('favorites.onlineGroup'))"
              @mouseleave="onGroupLeave"
            >
              <Wifi :size="20" class="fav-group-ico" />
            </div>

            <div
              class="fav-group-item"
              :class="{ active: selectedGroup === 'offline' }"
              @click="selectedGroup = 'offline'"
              @mouseenter="onGroupEnter($event, t('favorites.offlineGroup'))"
              @mouseleave="onGroupLeave"
            >
              <WifiOff :size="20" class="fav-group-ico" />
            </div>

            <div class="fav-divider"></div>

            <div ref="folderListEl" class="fav-group-list" @scroll="onGroupLeave">
              <div
                v-for="f in folders"
                :key="f.id"
                class="fav-group-item"
                :class="{ active: selectedGroup === f.id, 'drag-over': dragOverFolderId === f.id }"
                :data-folder-id="f.id"
                @click="selectedGroup = f.id"
                @contextmenu.prevent.stop="openFolderMenu(f, $event)"
                @mouseenter="onGroupEnter($event, f.name)"
                @mouseleave="onGroupLeave"
              >
                <component :is="folderIcon(f)" :size="20" class="fav-group-ico" />
              </div>
            </div>

            <div class="fav-divider"></div>

            <button
              class="fav-group-item fav-new-btn"
              @click="openNewGroup"
              @mouseenter="onGroupEnter($event, t('favorites.newFolder'))"
              @mouseleave="onGroupLeave"
            >
              <Plus :size="20" class="fav-group-ico" />
            </button>
          </aside>

          <!-- 右侧主区：网格（搜索已上移顶栏全局搜索） -->
          <div class="fav-main">
            <div v-if="entryCount === 0" class="empty-state">
              <div class="empty-icon">
                <Star :size="32" />
              </div>
              <div class="empty-text">{{ t('favorites.empty') }}</div>
              <button
                v-if="folders.length > 0"
                class="btn btn-primary btn-sm"
                @click="openAddModal(folders[0].id)"
              >
                <Plus :size="14" /> {{ t('favorites.add') }}
              </button>
            </div>

            <div v-else-if="visible.length === 0" class="empty-state">
              <div class="empty-text">{{ t('common.noResult') }}</div>
            </div>

            <div
              v-else
              ref="gridEl"
              class="fav-grid"
              :class="{ 'no-drag': !isFolderView || searching }"
              @contextmenu="onGridContextMenu($event)"
            >
              <div
                v-for="entry in visible"
                :key="entry.id"
                class="fav-tile"
                :class="{ offline: isOfflineEntry(entry) }"
                :data-id="entry.id"
                :data-kind="entry.kind"
                :title="t('ports.openService')"
                @contextmenu.prevent.stop="openEntryMenuAt(entry, $event)"
              >
                <span v-if="entry.kind === 'port'" class="port-status-dot" :class="isOfflineEntry(entry) ? 'is-offline' : 'is-online'"></span>
                <div class="fav-tile-logo" @click="openEntry(entry)">
                  <img v-if="entryLogoSrc(entry)" :src="entryLogoSrc(entry)" :alt="entryName(entry)" @error="onLogoError(entry.id)" />
                  <span v-else class="fav-tile-fallback">{{ entryName(entry).charAt(0).toUpperCase() }}</span>
                </div>
                <div class="fav-tile-name">
                  <span class="fav-name-text">{{ entryName(entry) }}</span>
                </div>
              </div>

              <!-- 「+」磁贴：仅文件夹视图显示（根下不允许添加） -->
              <div v-if="isFolderView" class="fav-tile fav-add-tile" :title="t('favorites.add')" @click="openAddModal(selectedGroup)">
                <div class="fav-tile-logo">
                  <Plus :size="26" />
                </div>
                <div class="fav-tile-name">
                  <span class="fav-name-text">{{ t('favorites.add') }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- 添加收藏弹窗 -->
    <Teleport to="body">
      <div v-if="addModal" class="modal-overlay" @click.self="addModal = null">
        <div class="modal">
          <div class="modal-header">
            <h2>
              {{ t('favorites.addTitle') }}
              <span class="meta">
                — {{ addModal.folderId ? currentFolder?.name ?? '' : t('favorites.targetRoot') }}
              </span>
            </h2>
            <button class="modal-close" :title="t('common.close')" @click="addModal = null">
              <X :size="16" />
            </button>
          </div>
          <div class="modal-body">
            <div class="add-tabs">
              <button class="chip" :class="{ active: addTab === 'port' }" @click="addTab = 'port'">
                {{ t('favorites.addFromPort') }}
              </button>
              <button class="chip" :class="{ active: addTab === 'url' }" @click="addTab = 'url'">
                {{ t('favorites.addCustom') }}
              </button>
            </div>

            <div v-if="addTab === 'port'" class="add-port-list">
              <div class="search-box">
                <span class="search-icon"><Search :size="15" /></span>
                <input v-model="addPortQuery" type="text" :placeholder="t('favorites.portSearch')" />
              </div>
              <div v-if="portCandidates.length === 0" class="empty-text">{{ t('favorites.noPorts') }}</div>
              <div
                v-for="card in portCandidates"
                :key="card.port"
                class="add-port-row"
                :class="{ disabled: hasPortFavorite(favorites, card.port!) }"
                :title="hasPortFavorite(favorites, card.port!) ? t('favorites.alreadyFav') : ''"
                @click="addPortEntry(card)"
              >
                <span class="port-status-dot" :class="card.is_running === false ? 'is-offline' : 'is-online'"></span>
                <span class="add-port-name">{{ card.remark || card.service_name || String(card.port) }}</span>
                <span class="add-port-num">:{{ card.port }}</span>
              </div>
            </div>

            <div v-else class="add-url-form">
              <div class="form-group">
                <label class="form-label">{{ t('favorites.nameLabel') }}</label>
                <input v-model="addTitle" class="form-input" type="text" :placeholder="t('favorites.nameLabel')" />
              </div>
              <div class="form-group">
                <label class="form-label">{{ t('favorites.urlLabel') }}</label>
                <input v-model="addUrl" class="form-input" type="text" placeholder="https://example.com" />
              </div>
              <div class="form-group">
                <label class="form-label">{{ t('favorites.logoLabel') }}</label>
                <div class="add-logo-row">
                  <img v-if="addFilePreview" :src="addFilePreview" class="add-logo-preview" alt="" />
                  <label class="btn btn-sm add-logo-btn">
                    {{ t('favorites.pickLogo') }}
                    <input type="file" accept="image/*" class="hidden-input" @change="onAddFilePicked" />
                  </label>
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-sm" @click="addModal = null">{{ t('common.cancel') }}</button>
            <button
              v-if="addTab === 'url'"
              class="btn btn-primary btn-sm"
              :disabled="addBusy"
              @click="saveUrlEntry"
            >
              {{ t('common.save') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 新建 / 重命名分组弹窗（名称 + 图标一体） -->
    <Teleport to="body">
      <div v-if="nameModal" class="modal-overlay" @click.self="nameModal = null">
        <div class="modal modal-sm">
          <div class="modal-header">
            <h2>{{ nameModal?.mode === 'new' ? t('favorites.newFolder') : t('favorites.renameFolder') }}</h2>
            <button class="modal-close" :title="t('common.close')" @click="nameModal = null">
              <X :size="16" />
            </button>
          </div>
          <div class="modal-body">
            <div class="folder-icon-grid">
              <button
                v-for="(Comp, name) in FOLDER_ICON_MAP"
                :key="name"
                class="folder-icon-item"
                :class="{ active: iconInput === name }"
                :title="String(name)"
                @click="pickModalIcon(String(name))"
              >
                <component :is="Comp" :size="18" />
              </button>
            </div>
            <input
              v-model="nameInput"
              class="form-input"
              type="text"
              :placeholder="t('favorites.nameLabel')"
              @keyup.enter="saveNameModal"
            />
          </div>
          <div class="modal-footer">
            <button class="btn btn-sm" @click="nameModal = null">{{ t('common.cancel') }}</button>
            <button class="btn btn-primary btn-sm" :disabled="!nameInput.trim()" @click="saveNameModal">
              {{ t('common.save') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 名称/备注编辑弹窗（port=备注，与端口页同步；url=显示名称） -->
    <Teleport to="body">
      <div v-if="nameEditModal" class="modal-overlay" @click.self="nameEditModal = null">
        <div class="modal modal-sm">
          <div class="modal-header">
            <h2>
              {{ nameEditModal.entry.kind === 'port' ? t('favorites.editRemark') : t('favorites.renameEntry') }}
            </h2>
            <button class="modal-close" :title="t('common.close')" @click="nameEditModal = null">
              <X :size="16" />
            </button>
          </div>
          <div class="modal-body">
            <input
              v-model="nameEditInput"
              class="form-input"
              type="text"
              :placeholder="t('favorites.nameLabel')"
              @keyup.enter="saveNameEdit"
            />
          </div>
          <div class="modal-footer">
            <button class="btn btn-sm" @click="nameEditModal = null">{{ t('common.cancel') }}</button>
            <button class="btn btn-primary btn-sm" @click="saveNameEdit">{{ t('common.save') }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 右键菜单 -->
    <Teleport to="body">
      <template v-if="ctxMenu">
        <div class="settings-menu-overlay" @click="closeCtxMenu"></div>
        <div class="settings-menu" :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }">
          <template v-if="ctxEntry">
            <div class="settings-menu-group">
              <button
                v-for="f in otherFolders(ctxEntry.folder?.id ?? null)"
                :key="f.id"
                class="settings-menu-item"
                @click="onCtxMoveTo(f.id)"
              >
                <span class="settings-menu-ico"><Folder :size="14" /></span>
                <span>{{ t('favorites.moveTo', { name: f.name }) }}</span>
              </button>
              <button
                v-if="ctxEntry.entry.logoKey"
                class="settings-menu-item"
                @click="openChangeLogo(ctxEntry.entry)"
              >
                <span class="settings-menu-ico">◈</span>
                <span>{{ t('favorites.changeLogo') }}</span>
              </button>
              <button class="settings-menu-item" @click="openNameEdit(ctxEntry.entry)">
                <span class="settings-menu-ico">✎</span>
                <span>
                  {{ ctxEntry.entry.kind === 'port' ? t('favorites.editRemark') : t('favorites.renameEntry') }}
                </span>
              </button>
            </div>
            <div v-if="ctxCanRemove" class="settings-menu-group">
              <button class="settings-menu-item danger" @click="onCtxRemoveEntry">
                <span class="settings-menu-ico">★</span>
                <span>{{ t('ports.removeFavorite') }}</span>
              </button>
            </div>
          </template>

          <template v-else-if="ctxFolder">
            <div class="settings-menu-group">
              <button class="settings-menu-item" @click="openRenameFolder(ctxFolder.folder)">
                <span class="settings-menu-ico">✎</span>
                <span>{{ t('favorites.renameFolder') }}</span>
              </button>
            </div>
            <div class="settings-menu-group">
              <button class="settings-menu-item danger" @click="onCtxRemoveFolder">
                <span class="settings-menu-ico">✕</span>
                <span>{{ t('favorites.deleteFolder') }}</span>
              </button>
            </div>
          </template>

          <template v-else>
            <div class="settings-menu-group">
              <button class="settings-menu-item" @click="openAddModal(selectedGroup)">
                <span class="settings-menu-ico">＋</span>
                <span>{{ t('favorites.add') }}</span>
              </button>
            </div>
          </template>
        </div>
      </template>
    </Teleport>

    <!-- 侧栏 hover 名称标签（body 级 fixed，避免撑出侧栏横向滚动条） -->
    <Teleport to="body">
      <div
        v-if="hoverLabel"
        class="fav-hover-label"
        :style="{ left: hoverLabel.x + 'px', top: hoverLabel.y + 'px' }"
      >
        {{ hoverLabel.text }}
      </div>
    </Teleport>

    <!-- 更换图标文件选择（隐藏） -->
    <input ref="logoInputRef" type="file" accept="image/*" class="hidden-input" @change="onLogoFilePicked" />

    <div v-if="toastVisible" class="save-toast">{{ toast }}</div>

    <AccessAddressPrompt v-if="showAddrPrompt" @configure="onAddrConfigure" @dismissed="onAddrDismissed" />
  </div>
</template>

<style scoped>
.favorites-view {
  position: relative;
  /* 填满 .main-content，让绝对定位的背景层铺满整个视图高度 */
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.favorites-view .main-body {
  position: relative;
  z-index: 1;
}

/* 背景作用域 = 收藏页时，表面半透明让毛玻璃透出 */
.favorites-view.has-bg .main-body {
  background: transparent;
}

/* 两栏布局：左侧分组坞 + 右侧主区。
   min-height:100% 撑满 main-body 可视区（滚动容器子元素的百分比高度按可视高解析），
   侧栏 sticky top:50% + translateY(-50%) → 网格短时居中于可视区，长时滚动钉在可视区正中。 */
.fav-layout {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  min-height: 100%;
}

/* WeTab 式窄坞：52px 玻璃面板、纯图标、hover 浮出名称。
   sticky top:50% + translateY(-50%)：始终居中于 main-body 可视区（滚动时钉在正中）。 */
.fav-sidebar {
  position: sticky;
  top: 50%;
  transform: translateY(-50%);
  z-index: 10;
  width: 52px;
  min-width: 52px;
  min-height: 240px;
  /* 长网格时坞高封顶到视口内，保证底部「+」始终可见 */
  max-height: calc(100vh - 180px);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-radius: 16px;
  background: color-mix(in srgb, var(--bg-secondary) var(--fav-bg-glass), transparent);
  border: 1px solid var(--border);
  backdrop-filter: blur(10px);
}

.fav-group-item {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  user-select: none;
}

.fav-group-item:hover {
  background: color-mix(in srgb, var(--text-primary) 10%, transparent);
  color: var(--text-primary);
}

.fav-group-item.active {
  background: color-mix(in srgb, var(--accent) 16%, transparent);
  color: var(--accent);
}

.fav-group-item.drag-over {
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 45%, transparent);
}

.fav-group-ico {
  flex-shrink: 0;
}

/* hover 浮出名称：body 级 fixed 白色胶囊（WeTab 同款），定位在图标右侧 */
.fav-hover-label {
  position: fixed;
  transform: translateY(-50%);
  z-index: 1000;
  max-width: 180px;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.92);
  color: #1a1d27;
  font-size: 12px;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
  pointer-events: none;
}

.fav-divider {
  width: 22px;
  height: 2px;
  border-radius: 1px;
  background: var(--border);
  flex-shrink: 0;
}

.fav-group-list {
  flex: 1;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  overflow-y: auto;
  /* 禁止横向滚动条：垂直滚动条（6px）出现时会挤占内容区，
     若保留 8px 水平 padding 会使 36px 图标溢出 → 横向滚动条。
     图标 flex 居中无需 padding，内容区 52px 扣掉滚动条仍 > 36px。 */
  overflow-x: hidden;
}

.fav-new-btn {
  margin-top: auto;
}

/* 分组弹窗内的图标网格 */
.folder-icon-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 4px;
  margin-bottom: 14px;
}

.folder-icon-item {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 34px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.12s, color 0.12s, border-color 0.12s;
}

.folder-icon-item:hover {
  background: var(--bg-card-hover);
  color: var(--text-primary);
}

.folder-icon-item.active {
  background: color-mix(in srgb, var(--accent) 16%, transparent);
  border-color: var(--accent);
  color: var(--accent);
}

/* 右侧主区 */
.fav-main {
  flex: 1;
  min-width: 0;
}

/* 网格：居中、大图标、间距大气 */
.fav-grid {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 22px;
  padding: 12px 0;
}

.fav-tile {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  width: 92px;
  cursor: grab;
  transition: transform 0.15s;
}

.fav-tile:hover {
  transform: translateY(-2px);
}

.fav-tile:active {
  cursor: grabbing;
}

.fav-tile.offline {
  opacity: 0.55;
}

/* 「+」磁贴：虚线描边，hover 高亮 */
.fav-add-tile {
  cursor: pointer;
}

.fav-add-tile .fav-tile-logo {
  border: 1px dashed var(--border-light);
  background: transparent;
  color: var(--text-muted);
}

.fav-add-tile:hover .fav-tile-logo {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 8%, transparent);
  color: var(--accent);
}

.fav-add-tile .fav-name-text {
  cursor: pointer;
}

/* 扁平视图（全部/在线/离线）禁用拖拽外观 */
.fav-grid.no-drag .fav-tile {
  cursor: default;
}

.fav-tile .port-status-dot {
  position: absolute;
  top: 0;
  right: 14px;
}

.fav-tile-logo {
  width: 64px;
  height: 64px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: rgba(128, 128, 160, 0.12);
  cursor: pointer;
  transition: background 0.15s;
}

.fav-tile-logo:hover {
  background: rgba(128, 128, 160, 0.25);
}

.fav-tile-logo img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.fav-tile-fallback {
  font-size: 26px;
  font-weight: 600;
  color: var(--text-muted);
}

.fav-tile-name {
  width: 100%;
  text-align: center;
}

.fav-name-text {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  /* 背景图上保证可读 */
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.55);
}

/* 浅色主题：白字不可读 → 深色加粗、去投影 */
[data-theme='light'] .fav-name-text {
  color: var(--text-primary);
  text-shadow: none;
}

/* 弹窗内 chip */
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 12px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.chip:hover {
  background: var(--bg-card-hover);
}

.chip.active {
  border-color: var(--accent);
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}

/* 弹窗内元素 */
.modal-sm {
  max-width: 400px;
}

.empty-sm {
  padding: 24px 0;
}

.empty-state .btn {
  margin-top: 16px;
}

.add-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}

.add-port-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 300px;
  overflow-y: auto;
}

.add-port-list .search-box {
  max-width: none;
  margin-bottom: 6px;
}

.add-port-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-card);
  cursor: pointer;
  font-size: 13px;
}

.add-port-row:hover {
  background: var(--bg-card-hover);
}

.add-port-row.disabled {
  opacity: 0.45;
  cursor: default;
}

.add-port-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.add-port-num {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
}

.add-url-form .form-group:last-child {
  margin-bottom: 0;
}

.add-logo-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.add-logo-preview {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  object-fit: contain;
  background: rgba(128, 128, 160, 0.12);
}

.add-logo-btn {
  position: relative;
  overflow: hidden;
}

.hidden-input {
  display: none;
}

/* 窄屏：分组坞退化为顶部横向图标行 */
@media (max-width: 768px) {
  .fav-layout {
    flex-direction: column;
  }

  .fav-sidebar {
    position: static;
    transform: none;
    width: 100%;
    min-width: 0;
    min-height: 0;
    flex-direction: row;
    align-items: center;
    overflow-x: auto;
    padding: 8px;
    gap: 8px;
  }

  .fav-group-list {
    flex-direction: row;
    justify-content: flex-start;
    overflow: visible;
    padding: 0;
  }

  .fav-group-item {
    flex-shrink: 0;
  }

  .fav-divider {
    width: 2px;
    height: 22px;
  }

  .fav-new-btn {
    margin-top: 0;
    margin-left: auto;
  }
}
</style>

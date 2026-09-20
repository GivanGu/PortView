<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Star, Plus, Folder, Search, X } from 'lucide-vue-next'
import Sortable from 'sortablejs'
import {
  fetchPorts,
  fetchHiddenPortDetails,
  fetchLogos,
  fetchDefaultLogos,
  logoUrl,
  defaultLogoUrl,
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
import { useOpenService } from '@/composables/useOpenService'
import AccessAddressPrompt from '@/components/AccessAddressPrompt.vue'

const { t } = useI18n()
const { favorites, saveFavorites, refreshTick, triggerRefresh } = usePrefs()
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

interface FlatEntry {
  entry: FavEntry
  folder: FavFolder | null
}

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

// ── 搜索 / 离线筛选（过滤时扁平展示，隐藏文件夹结构）──
const search = ref('')
const offlineOnly = ref(false)
const filtering = computed(() => search.value.trim() !== '' || offlineOnly.value)

const offlineCount = computed(
  () => allEntries.value.filter((fe) => fe.entry.kind === 'port' && isOfflineEntry(fe.entry)).length,
)

function entryMatches(entry: FavEntry, folder: FavFolder | null, q: string): boolean {
  if (entryName(entry).toLowerCase().includes(q)) return true
  if (entry.kind === 'url' && entry.url?.toLowerCase().includes(q)) return true
  if (folder && folder.name.toLowerCase().includes(q)) return true
  return false
}

const visible = computed<GridItem[]>(() => {
  if (!filtering.value) return favorites.value
  const q = search.value.trim().toLowerCase()
  const out: GridItem[] = []
  for (const { entry, folder } of allEntries.value) {
    if (offlineOnly.value && (entry.kind !== 'port' || !isOfflineEntry(entry))) continue
    if (q && !entryMatches(entry, folder, q)) continue
    out.push(entry)
  }
  return out
})

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

function addFolder(name: string) {
  saveFavorites([...favorites.value, { id: uid('folder'), kind: 'folder', name, items: [] }])
}

function renameFolder(id: string, name: string) {
  saveFavorites(favorites.value.map((it) => (it.kind === 'folder' && it.id === id ? { ...it, name } : it)))
}

function deleteFolder(id: string) {
  const folder = favorites.value.find((it) => it.kind === 'folder' && it.id === id)
  if (!folder || folder.kind !== 'folder') return
  const rest = favorites.value.filter((it) => !(it.kind === 'folder' && it.id === id))
  saveFavorites([...rest, ...folder.items])
}

function reorder(oldIndex: number, newIndex: number, items: GridItem[], folderId?: string): GridItem[] {
  if (folderId) {
    return items.map((it) => {
      if (it.kind !== 'folder' || it.id !== folderId) return it
      const sub = [...it.items]
      const [m] = sub.splice(oldIndex, 1)
      sub.splice(newIndex, 0, m)
      return { ...it, items: sub }
    })
  }
  const order = [...items]
  const [m] = order.splice(oldIndex, 1)
  order.splice(newIndex, 0, m)
  return order
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
function closeCtxMenu() {
  ctxMenu.value = null
}

// 模板用收窄后的 computed（vue-tsc 不跨 <template v-if> 收窄联合类型）
const ctxEntry = computed(() => {
  const t = ctxMenu.value?.target
  return t && t.kind === 'entry' ? t : null
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
    if (folderModalId.value) folderModalId.value = null
    if (addModal.value) addModal.value = null
    if (nameModal.value) nameModal.value = null
  }
}
function onResizeCloseMenu() {
  if (ctxMenu.value) closeCtxMenu()
}

function otherFolders(excludeId: string | null): FavFolder[] {
  return favorites.value.filter((it): it is FavFolder => it.kind === 'folder' && it.id !== excludeId)
}

function onCtxMoveTo(folderId: string) {
  const target = ctxMenu.value?.target
  if (target?.kind !== 'entry') return
  closeCtxMenu()
  moveEntry(target.entry.id, folderId)
}
function onCtxMoveRoot() {
  const target = ctxMenu.value?.target
  if (target?.kind !== 'entry') return
  closeCtxMenu()
  moveEntry(target.entry.id, null)
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
function onCtxRemoveFolderFromModal() {
  const folder = currentFolder.value
  if (!folder) return
  if (!confirm(t('favorites.deleteFolderConfirm', { name: folder.name }))) return
  folderModalId.value = null
  deleteFolder(folder.id)
}

// ── 文件夹弹窗 ──
const folderModalId = ref<string | null>(null)
const currentFolder = computed<FavFolder | null>(() => {
  const it = favorites.value.find((x) => x.kind === 'folder' && x.id === folderModalId.value)
  return it && it.kind === 'folder' ? it : null
})

function openFolderModal(id: string) {
  closeCtxMenu()
  folderModalId.value = id
}

// 文件夹内行内重命名
const folderRename = ref('')
watch(
  () => folderModalId.value,
  (id) => {
    folderRename.value = id ? currentFolder.value?.name ?? '' : ''
  },
)
function saveFolderRename() {
  const name = folderRename.value.trim()
  if (!name || !currentFolder.value) return
  renameFolder(currentFolder.value.id, name)
}

// ── 拖拽排序（sortablejs）＋ 拖入文件夹（悬停检测）──
const gridEl = ref<HTMLElement | null>(null)
const folderGridEl = ref<HTMLElement | null>(null)
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

function setupRootSortable() {
  rootSortable?.destroy()
  rootSortable = null
  if (loading.value || filtering.value || visible.value.length === 0 || !gridEl.value) return
  rootSortable = Sortable.create(gridEl.value, {
    animation: 150,
    onStart: (evt) => {
      // 拖拽中的节点自身会挡住 elementFromPoint 命中检测，需排除
      ;(evt.item as HTMLElement).style.pointerEvents = 'none'
      window.addEventListener('mousemove', onRootDragMove)
    },
    onEnd: (evt) => {
      ;(evt.item as HTMLElement).style.pointerEvents = ''
      window.removeEventListener('mousemove', onRootDragMove)
      const id = evt.item.dataset.id
      const kind = evt.item.dataset.kind
      const folderId = dragOverFolderId.value
      dragOverFolderId.value = null
      if (!id || kind === 'folder') {
        // 文件夹磁贴只参与排序，不参与拖入
        if (kind === 'folder' && evt.oldIndex != null && evt.newIndex != null && evt.oldIndex !== evt.newIndex) {
          saveFavorites(reorder(evt.oldIndex, evt.newIndex, favorites.value))
        }
        return
      }
      if (folderId) {
        moveEntry(id, folderId)
        return
      }
      const { oldIndex, newIndex } = evt
      if (oldIndex == null || newIndex == null || oldIndex === newIndex) return
      saveFavorites(reorder(oldIndex, newIndex, favorites.value))
    },
  })
}

function setupFolderSortable() {
  folderSortable?.destroy()
  folderSortable = null
  const folder = currentFolder.value
  if (!folder || !folderGridEl.value || folder.items.length === 0) return
  folderSortable = Sortable.create(folderGridEl.value, {
    animation: 150,
    onEnd: (evt) => {
      const { oldIndex, newIndex } = evt
      if (oldIndex == null || newIndex == null || oldIndex === newIndex) return
      saveFavorites(reorder(oldIndex, newIndex, favorites.value, folder.id))
    },
  })
}

watch([loading, filtering, () => favorites.value.length], () => {
  void nextTick(() => setupRootSortable())
})
// 条目数变化（空文件夹加首项 / 删末项）也需重建 Sortable
watch([folderModalId, () => currentFolder.value?.items.length ?? 0], () => {
  void nextTick(() => setupFolderSortable())
})

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

// ── 新建 / 重命名文件夹弹窗 ──
const nameModal = ref<{ mode: 'new' | 'rename'; folderId?: string } | null>(null)
const nameInput = ref('')

function openNewFolder() {
  closeCtxMenu()
  nameInput.value = ''
  nameModal.value = { mode: 'new' }
}
function openRenameFolder(folder: FavFolder) {
  closeCtxMenu()
  nameInput.value = folder.name
  nameModal.value = { mode: 'rename', folderId: folder.id }
}
function saveNameModal() {
  const name = nameInput.value.trim()
  if (!name || !nameModal.value) return
  if (nameModal.value.mode === 'new') addFolder(name)
  else if (nameModal.value.folderId) renameFolder(nameModal.value.folderId, name)
  nameModal.value = null
}

// ── 行内备注编辑（port 条目，与端口页备注同步）──
const editingPort = ref<number | null>(null)
const editRemark = ref('')

function startEdit(entry: FavEntry) {
  if (entry.kind !== 'port') return
  editingPort.value = entry.port ?? null
  editRemark.value = (entry.port != null ? cards.value.get(entry.port)?.remark : undefined) || ''
}
function cancelEdit() {
  editingPort.value = null
}
async function saveEdit(entry: FavEntry) {
  if (entry.kind !== 'port' || editingPort.value !== entry.port) return
  editingPort.value = null
  const card = entry.port != null ? cards.value.get(entry.port) : undefined
  if (!card) return
  const remark = editRemark.value.trim()
  try {
    const protocol = ((card.protocol || '').toLowerCase() || '') as NoteProtocol
    const resp = await upsertNote({
      port: entry.port!,
      service_name: card.service_name ?? '',
      protocol,
      remark,
    })
    if (resp.success) {
      card.remark = remark || undefined
      triggerRefresh()
    } else {
      showToast(t('common.saveFailed'))
    }
  } catch (e) {
    console.error('保存备注失败:', e)
    showToast(t('common.saveFailed'))
  }
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
  <div class="favorites-view">
    <div class="main-header">
      <h1>{{ t('favorites.title') }}</h1>
      <div class="header-actions">
        <span class="meta">{{ t('favorites.count', { n: favorites.length }) }}</span>
        <span v-if="offlineCount > 0" class="offline-badge" :title="t('favorites.offlineCount', { n: offlineCount })">
          {{ t('favorites.offlineCount', { n: offlineCount }) }}
        </span>
        <button class="btn btn-primary btn-sm" @click="openAddModal(null)">
          <Plus :size="14" /> {{ t('favorites.add') }}
        </button>
      </div>
    </div>

    <div class="main-body">
      <div v-if="loading" class="empty-state">
        <div class="empty-text">{{ t('common.loading') }}</div>
      </div>

      <template v-else>
        <div class="toolbar">
          <div class="search-box">
            <span class="search-icon"><Search :size="15" /></span>
            <input v-model="search" type="text" :placeholder="t('favorites.searchPlaceholder')" />
          </div>
          <button
            class="chip"
            :class="{ active: offlineOnly }"
            @click="offlineOnly = !offlineOnly"
          >
            {{ t('favorites.offlineOnly') }} ({{ offlineCount }})
          </button>
        </div>

        <div v-if="favorites.length === 0" class="empty-state">
          <div class="empty-icon">
            <Star :size="32" />
          </div>
          <div class="empty-text">{{ t('favorites.empty') }}</div>
        </div>

        <div v-else-if="visible.length === 0" class="empty-state">
          <div class="empty-text">{{ t('common.noResult') }}</div>
        </div>

        <div v-else ref="gridEl" class="fav-grid" @contextmenu.prevent="openRootMenu($event)">
          <template v-for="item in visible" :key="item.id">
            <!-- 文件夹磁贴 -->
            <div
              v-if="item.kind === 'folder'"
              class="fav-tile fav-folder-tile"
              :data-id="item.id"
              data-kind="folder"
              :data-folder-id="item.id"
              :class="{ 'drag-over': dragOverFolderId === item.id }"
              :title="t('favorites.dragToFolder')"
              @click="openFolderModal(item.id)"
              @contextmenu.prevent.stop="openFolderMenu(item, $event)"
            >
              <div class="fav-folder-ico"><Folder :size="28" /></div>
              <div class="fav-tile-name">
                <span class="fav-name-text">{{ item.name }}</span>
              </div>
              <div class="fav-folder-count">{{ t('favorites.folderCount', { n: item.items.length }) }}</div>
            </div>

            <!-- 条目磁贴（port / url） -->
            <div
              v-else
              class="fav-tile"
              :class="{ offline: isOfflineEntry(item) }"
              :data-id="item.id"
              :data-kind="item.kind"
              :title="item.kind === 'port' ? t('favorites.editRemark') : t('ports.openService')"
              @contextmenu.prevent.stop="openEntryMenuAt(item, $event)"
            >
              <span v-if="item.kind === 'port'" class="port-status-dot" :class="isOfflineEntry(item) ? 'is-offline' : 'is-online'"></span>
              <div class="fav-tile-logo" @click="openEntry(item)">
                <img v-if="entryLogoSrc(item)" :src="entryLogoSrc(item)" :alt="entryName(item)" @error="onLogoError(item.id)" />
                <span v-else class="fav-tile-fallback">{{ entryName(item).charAt(0).toUpperCase() }}</span>
              </div>
              <div class="fav-tile-name">
                <input
                  v-if="item.kind === 'port' && editingPort === item.port"
                  v-model="editRemark"
                  class="fav-edit-input"
                  @keyup.enter="saveEdit(item)"
                  @keyup.esc="cancelEdit"
                  @blur="saveEdit(item)"
                />
                <span v-else class="fav-name-text" @click="item.kind === 'port' ? startEdit(item) : openEntry(item)">
                  {{ entryName(item) }}
                </span>
              </div>
            </div>
          </template>
        </div>
      </template>
    </div>

    <!-- 文件夹弹窗 -->
    <Teleport to="body">
      <div v-if="currentFolder" class="modal-overlay" @click.self="folderModalId = null">
        <div class="modal">
          <div class="modal-header">
            <h2>
              <Folder :size="16" class="folder-ico-inline" />
              <input
                v-model="folderRename"
                class="folder-rename-input"
                @keyup.enter="saveFolderRename"
                @blur="saveFolderRename"
              />
            </h2>
            <div class="modal-header-actions">
              <span class="meta">{{ t('favorites.folderCount', { n: currentFolder.items.length }) }}</span>
              <button class="modal-close" :title="t('common.close')" @click="folderModalId = null">
                <X :size="16" />
              </button>
            </div>
          </div>
          <div class="modal-body">
            <div v-if="currentFolder.items.length === 0" class="empty-state empty-sm">
              <div class="empty-text">{{ t('favorites.emptyFolder') }}</div>
            </div>
            <div v-else ref="folderGridEl" class="fav-grid">
              <div
                v-for="entry in currentFolder.items"
                :key="entry.id"
                class="fav-tile"
                :class="{ offline: isOfflineEntry(entry) }"
                :data-id="entry.id"
                :data-kind="entry.kind"
                @contextmenu.prevent="openEntryMenuAt(entry, $event)"
              >
                <span v-if="entry.kind === 'port'" class="port-status-dot" :class="isOfflineEntry(entry) ? 'is-offline' : 'is-online'"></span>
                <div class="fav-tile-logo" @click="openEntry(entry)">
                  <img v-if="entryLogoSrc(entry)" :src="entryLogoSrc(entry)" :alt="entryName(entry)" @error="onLogoError(entry.id)" />
                  <span v-else class="fav-tile-fallback">{{ entryName(entry).charAt(0).toUpperCase() }}</span>
                </div>
                <div class="fav-tile-name">
                  <span class="fav-name-text" @click="openEntry(entry)">
                    {{ entryName(entry) }}
                  </span>
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-danger btn-sm" @click="onCtxRemoveFolderFromModal">
              {{ t('favorites.deleteFolder') }}
            </button>
            <button class="btn btn-primary btn-sm" @click="openAddModal(currentFolder.id)">
              <Plus :size="14" /> {{ t('favorites.addHere') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

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

    <!-- 新建 / 重命名文件夹弹窗 -->
    <Teleport to="body">
      <div v-if="nameModal" class="modal-overlay" @click.self="nameModal = null">
        <div class="modal modal-sm">
          <div class="modal-header">
            <h2>{{ nameModal.mode === 'new' ? t('favorites.newFolder') : t('favorites.renameFolder') }}</h2>
            <button class="modal-close" :title="t('common.close')" @click="nameModal = null">
              <X :size="16" />
            </button>
          </div>
          <div class="modal-body">
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

    <!-- 右键菜单 -->
    <Teleport to="body">
      <template v-if="ctxMenu">
        <div class="settings-menu-overlay" @click="closeCtxMenu"></div>
        <div class="settings-menu" :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }">
          <template v-if="ctxEntry">
            <div class="settings-menu-group">
              <button v-if="ctxEntry.folder" class="settings-menu-item" @click="onCtxMoveRoot">
                <span class="settings-menu-ico">⌂</span>
                <span>{{ t('favorites.moveRoot') }}</span>
              </button>
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
            </div>
            <div class="settings-menu-group">
              <button class="settings-menu-item danger" @click="onCtxRemoveEntry">
                <span class="settings-menu-ico">★</span>
                <span>{{ t('ports.removeFavorite') }}</span>
              </button>
            </div>
          </template>

          <template v-else-if="ctxFolder">
            <div class="settings-menu-group">
              <button class="settings-menu-item" @click="openFolderModal(ctxFolder.folder.id)">
                <span class="settings-menu-ico"><Folder :size="14" /></span>
                <span>{{ t('favorites.openFolder') }}</span>
              </button>
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
              <button class="settings-menu-item" @click="openAddModal(null)">
                <span class="settings-menu-ico">＋</span>
                <span>{{ t('favorites.add') }}</span>
              </button>
              <button class="settings-menu-item" @click="openNewFolder">
                <span class="settings-menu-ico"><Folder :size="14" /></span>
                <span>{{ t('favorites.newFolder') }}</span>
              </button>
            </div>
          </template>
        </div>
      </template>
    </Teleport>

    <!-- 更换图标文件选择（隐藏） -->
    <input ref="logoInputRef" type="file" accept="image/*" class="hidden-input" @change="onLogoFilePicked" />

    <div v-if="toastVisible" class="save-toast">{{ toast }}</div>

    <AccessAddressPrompt v-if="showAddrPrompt" @configure="onAddrConfigure" @dismissed="onAddrDismissed" />
  </div>
</template>

<style scoped>
.fav-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
}

.fav-tile {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 12px 12px;
  border-radius: var(--radius, 10px);
  background: var(--bg-card);
  border: 1px solid var(--border);
  cursor: grab;
  transition: all 0.15s;
}

.fav-tile:hover {
  background: var(--bg-card-hover);
}

.fav-tile:active {
  cursor: grabbing;
}

.fav-tile.offline {
  opacity: 0.55;
}

.fav-tile .port-status-dot {
  position: absolute;
  top: 10px;
  right: 10px;
}

.fav-tile-logo {
  width: 48px;
  height: 48px;
  border-radius: 10px;
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
  font-size: 20px;
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
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: text;
}

.fav-edit-input {
  width: 100%;
  box-sizing: border-box;
  font-size: 13px;
  padding: 2px 6px;
  border-radius: 6px;
  border: 1px solid var(--border-light);
  background: var(--bg-secondary);
  color: var(--text-primary);
  outline: none;
}

/* 文件夹磁贴 */
.fav-folder-tile {
  cursor: pointer;
}

.fav-folder-tile.drag-over {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 35%, transparent);
}

.fav-folder-ico {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--accent) 18%, transparent);
  color: var(--accent);
}

.fav-folder-count {
  font-size: 11px;
  color: var(--text-muted);
}

/* 顶栏离线徽标 */
.offline-badge {
  font-size: 12px;
  color: var(--text-muted);
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--bg-card);
  border: 1px solid var(--border);
}

/* 筛选 chip */
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

.modal-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.folder-ico-inline {
  vertical-align: -2px;
  margin-right: 6px;
  color: var(--accent);
}

.folder-rename-input {
  background: none;
  border: none;
  outline: none;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  width: 220px;
}

.empty-sm {
  padding: 24px 0;
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
</style>

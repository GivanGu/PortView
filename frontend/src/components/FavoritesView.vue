<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Star } from 'lucide-vue-next'
import Sortable from 'sortablejs'
import {
  fetchPorts,
  fetchHiddenPortDetails,
  fetchLogos,
  fetchDefaultLogos,
  logoUrl,
  defaultLogoUrl,
  upsertNote,
  patchPrefs,
  type PortCard,
  type LogoMeta,
  type HiddenPortDetail,
  type NoteProtocol,
} from '@/api'
import { appKey, normalizeServiceName } from '@/logo'
import { usePrefs } from '@/store/prefs'
import { useOpenService } from '@/composables/useOpenService'
import AccessAddressPrompt from '@/components/AccessAddressPrompt.vue'

const { t } = useI18n()
const { favorites, setFavorites, refreshTick, triggerRefresh } = usePrefs()
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

interface FavTile {
  port: number
  card: PortCard | null
}

// 收藏顺序即展示顺序；卡片消失时 card 为 null（置灰保留，不自动移除）
const tiles = computed<FavTile[]>(() =>
  favorites.value.map((port) => ({ port, card: cards.value.get(port) ?? null })),
)

// 隐藏端口详情 → PortCard（收藏页仍显示隐藏端口：显式收藏意图 > 隐藏规则）
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

// ── Logo（与 PortsView 同一套解析规则：用户 Logo > 内置默认 Logo）──
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

function logoSrc(card: PortCard): string | undefined {
  const key = appKey(card)
  if (logos.value.get(key)?.status === 'found') return logoUrl(key)
  const dkey = defaultLogoKey(card)
  if (dkey) return defaultLogoUrl(dkey)
  return undefined
}

// ── 展示 ──
function displayName(tile: FavTile): string {
  if (tile.card) return tile.card.remark || tile.card.service_name || String(tile.port)
  return String(tile.port)
}

function isOffline(tile: FavTile): boolean {
  return tile.card == null || tile.card.is_running === false
}

// ── 行内备注编辑（Enter 保存 / Esc 取消，保存到 port_notes 与端口页自动同步）──
const editingPort = ref<number | null>(null)
const editRemark = ref('')

function startEdit(tile: FavTile) {
  if (!tile.card) return
  editingPort.value = tile.port
  editRemark.value = tile.card.remark || ''
}

function cancelEdit() {
  editingPort.value = null
}

async function saveEdit(tile: FavTile) {
  if (editingPort.value !== tile.port) return
  editingPort.value = null
  const card = tile.card
  if (!card) return
  const remark = editRemark.value.trim()
  try {
    const protocol = ((card.protocol || '').toLowerCase() || '') as NoteProtocol
    const resp = await upsertNote({
      port: tile.port,
      service_name: card.service_name ?? '',
      protocol,
      remark,
    })
    if (resp.success) {
      card.remark = remark || undefined
      // 备注/服务名变更 → 全局刷新，端口页等视图立即同步
      triggerRefresh()
    } else {
      showToast(t('common.saveFailed'))
    }
  } catch (e) {
    console.error('保存备注失败:', e)
    showToast(t('common.saveFailed'))
  }
}

// ── 拖拽排序（sortablejs，onEnd 后写回 prefs）──
const gridEl = ref<HTMLElement | null>(null)
let sortable: Sortable | null = null

function destroySortable() {
  sortable?.destroy()
  sortable = null
}

watch([loading, () => tiles.value.length], async ([l, n]) => {
  if (l || n === 0) {
    destroySortable()
    return
  }
  await nextTick()
  if (!gridEl.value) return
  destroySortable()
  sortable = Sortable.create(gridEl.value, {
    animation: 150,
    onEnd: (evt) => {
      const { oldIndex, newIndex } = evt
      if (oldIndex == null || newIndex == null || oldIndex === newIndex) return
      const order = [...favorites.value]
      const [moved] = order.splice(oldIndex, 1)
      order.splice(newIndex, 0, moved)
      setFavorites(order)
      patchPrefs({ favorites: order })
        .then((resp) => {
          if (!resp.success) showToast(t('common.saveFailed'))
        })
        .catch((e) => {
          console.error('保存收藏顺序失败:', e)
          showToast(t('common.saveFailed'))
        })
    },
  })
})

// 顶栏全局刷新 → 重新拉取端口/隐藏详情/Logo（页签保活，不 watch 会停在首载快照）
watch(refreshTick, () => {
  if (!loading.value) loadData()
})

onMounted(() => {
  loadData()
  loadManualSchemes()
})
onBeforeUnmount(destroySortable)
</script>

<template>
  <div class="favorites-view">
    <div class="main-header">
      <h1>{{ t('favorites.title') }}</h1>
      <div class="header-actions">
        <span class="meta">{{ t('favorites.count', { n: favorites.length }) }}</span>
      </div>
    </div>

    <div class="main-body">
      <div v-if="loading" class="empty-state">
        <div class="empty-text">{{ t('common.loading') }}</div>
      </div>

      <div v-else-if="tiles.length === 0" class="empty-state">
        <div class="empty-icon">
          <Star :size="32" />
        </div>
        <div class="empty-text">{{ t('favorites.empty') }}</div>
      </div>

      <div v-else ref="gridEl" class="fav-grid">
        <div
          v-for="tile in tiles"
          :key="tile.port"
          class="fav-tile"
          :class="{ offline: isOffline(tile) }"
          :title="tile.card ? t('favorites.editRemark') : t('favorites.vanished')"
        >
          <span class="port-status-dot" :class="isOffline(tile) ? 'is-offline' : 'is-online'"></span>
          <div
            class="fav-tile-logo"
            :title="t('ports.openService')"
            @click="handleOpenService(tile.card ?? { type: 'used', port: tile.port })"
          >
            <img v-if="tile.card && logoSrc(tile.card)" :src="logoSrc(tile.card)" :alt="displayName(tile)" />
            <span v-else class="fav-tile-fallback">{{ displayName(tile).charAt(0).toUpperCase() }}</span>
          </div>
          <div class="fav-tile-name">
            <input
              v-if="editingPort === tile.port"
              v-model="editRemark"
              class="fav-edit-input"
              @keyup.enter="saveEdit(tile)"
              @keyup.esc="cancelEdit"
              @blur="saveEdit(tile)"
            />
            <span v-else class="fav-name-text" @click="startEdit(tile)">{{ displayName(tile) }}</span>
          </div>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="toastVisible" class="save-toast">{{ toast }}</div>
    </Teleport>

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
</style>

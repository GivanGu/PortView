<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  listNotes,
  upsertNote,
  deleteNote,
  fetchPorts,
  fetchLogos,
  discoverLogo,
  uploadLogo,
  type NoteRead,
  type NotePayload,
  type PortCard,
  type LogoMeta,
} from '@/api'
import { appKey } from '@/logo'
import { Search, StickyNote, Plus, Pencil, Trash2, X, AlertCircle, ImageOff, ImagePlus } from 'lucide-vue-next'

const { t } = useI18n()

const notes = ref<NoteRead[]>([])
const loading = ref(false)
const saving = ref(false)
const searchQuery = ref('')

// 轻提示（Logo 发现/上传结果反馈）
const toast = ref('')
const toastVisible = ref(false)
let toastTimer: ReturnType<typeof setTimeout>
function showToast(msg: string) {
  toast.value = msg
  toastVisible.value = true
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastVisible.value = false }, 2600)
}

// v1.3：未备注端口 —— 展示所有已用但无 note 记录的端口，
// 方便用户「看到→点开→补备注」的一站式快速流。
const allUsedPorts = ref<PortCard[]>([])

// v1.5.0：无 Logo 端口 —— 展示所有已用但未设置 Logo 的端口，
// 方便用户「看到→快速补 Logo」的一站式快速流。
const logos = ref<Map<string, LogoMeta>>(new Map())
const logoBusy = ref<Set<string>>(new Set())

// 编辑器状态（新建/编辑共用 modal）
const editorOpen = ref(false)
const editingPort = ref<number | null>(null)
const draft = ref<NotePayload>({
  port: 0,
  service_name: '',
  protocol: '',
  remark: '',
})

const isEditing = computed(() => editingPort.value !== null)

// v1.3：未备注端口 = 已用端口中有 port 但 notes 里没它的，且服务名未知
// v1.4.3：同时覆盖后端标记为「未知服务」的端口（service_name === '未知服务'），
// 让「看到未知服务→补备注」成为一条主路径。
const UNKNOWN_SVC = '未知服务'
const unremarked = computed(() => {
  const notedPorts = new Set(notes.value.map(n => n.port))
  return allUsedPorts.value
    .filter(c => c.type === 'used' && c.port != null && !notedPorts.has(c.port) &&
      (!c.service_name || c.service_name === UNKNOWN_SVC))
    .sort((a, b) => (a.port ?? 0) - (b.port ?? 0))
})

const shownUnremarked = computed(() => {
  if (!searchQuery.value) return unremarked.value
  const q = searchQuery.value.toLowerCase()
  return unremarked.value.filter(c =>
    String(c.port ?? '').includes(q) ||
    (c.service_name ?? '').toLowerCase().includes(q) ||
    (c.container ?? '').toLowerCase().includes(q) ||
    (c.remark ?? '').toLowerCase().includes(q)
  )
})

// v1.5.0：无 Logo 端口 = 已用端口中 logo 状态非 'found' 的
const noLogo = computed(() => {
  return allUsedPorts.value
    .filter(c => c.type === 'used' && c.port != null &&
      logos.value.get(appKey(c))?.status !== 'found')
    .sort((a, b) => (a.port ?? 0) - (b.port ?? 0))
})

const shownNoLogo = computed(() => {
  if (!searchQuery.value) return noLogo.value
  const q = searchQuery.value.toLowerCase()
  return noLogo.value.filter(c =>
    String(c.port ?? '').includes(q) ||
    (c.service_name ?? '').toLowerCase().includes(q) ||
    (c.container ?? '').toLowerCase().includes(q) ||
    (c.remark ?? '').toLowerCase().includes(q)
  )
})

async function loadData() {
  loading.value = true
  try {
    const resp = await listNotes(searchQuery.value)
    if (resp.success) notes.value = resp.data
  } catch (e) {
    console.error('load notes failed:', e)
  } finally {
    loading.value = false
  }
}

// v1.3：加载所有已用端口（无搜索/无过滤），供"未备注"分区使用。
// 独立于 notes.searchQuery —— 未备注区的搜索由前端侧 shownUnremarked 处理，
// 避免每次输入都触发后端往返。
async function loadAllPorts() {
  try {
    const resp = await fetchPorts({ start_port: 1, end_port: 65535 })
    if (resp.success) {
      allUsedPorts.value = (resp.data as { port_cards: PortCard[] }).port_cards ?? []
    }
  } catch (e) {
    console.error('load all ports failed:', e)
  }
}

// v1.5.0：加载 Logo 状态，供"无 Logo"分区判断
async function loadLogos() {
  try {
    const resp = await fetchLogos()
    if (resp.success) {
      const m = new Map<string, LogoMeta>()
      for (const meta of resp.data) m.set(meta.app_key, meta)
      logos.value = m
    }
  } catch (e) {
    console.error('load logos failed:', e)
  }
}

function isLogoBusy(card: PortCard): boolean {
  return logoBusy.value.has(appKey(card))
}

async function handleDiscoverLogo(card: PortCard) {
  const key = appKey(card)
  if (!card.port) return
  logoBusy.value = new Set(logoBusy.value).add(key)
  try {
    const resp = await discoverLogo(key, card.port)
    if (resp.success) {
      await loadLogos()
      if (resp.data?.status === 'not_found') {
        showToast(t('notes.logoDiscoverFailed', { service: card.service_name || card.port }))
      } else {
        showToast(t('notes.logoAdded'))
      }
    }
  } catch (e) {
    console.error('Logo discover failed:', e)
    showToast(t('notes.logoDiscoverFailed', { service: card.service_name || card.port }))
  } finally {
    const s = new Set(logoBusy.value)
    s.delete(key)
    logoBusy.value = s
  }
}

async function handleUploadLogo(card: PortCard) {
  const key = appKey(card)
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/png,image/jpeg,image/svg+xml,image/gif,image/webp,image/x-icon,image/vnd.microsoft.icon'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    if (file.size > 1024 * 1024) return
    logoBusy.value = new Set(logoBusy.value).add(key)
    try {
      const reader = new FileReader()
      reader.onload = async () => {
        const base64 = (reader.result as string).split(',')[1]
        await uploadLogo(key, file.type, base64)
        await loadLogos()
        showToast(t('notes.logoAdded'))
      }
      reader.readAsDataURL(file)
    } catch (e) {
      console.error('Logo upload failed:', e)
      showToast(t('notes.logoUploadFailed'))
    } finally {
      const s = new Set(logoBusy.value)
      s.delete(key)
      logoBusy.value = s
    }
  }
  input.click()
}

function openEditByPort(port: number, preset?: string) {
  editingPort.value = port
  const match = allUsedPorts.value.find(c => c.port === port)
  const rawProto = (match?.protocol ?? '').toString().toLowerCase()
  const rawSvc = match?.service_name ?? preset ?? ''
  draft.value = {
    port,
    // 「未知服务」是占位符，打开编辑器时清空，让用户直接填真实服务名
    service_name: rawSvc === UNKNOWN_SVC ? '' : rawSvc,
    protocol: (rawProto === 'tcp' || rawProto === 'udp') ? rawProto : '',
    remark: '',
  }
  editorOpen.value = true
}

let searchTimer: ReturnType<typeof setTimeout>
watch(searchQuery, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadData, 300)
})

function openCreate() {
  editingPort.value = null
  draft.value = { port: 80, service_name: '', protocol: '', remark: '' }
  editorOpen.value = true
}

function openEdit(n: NoteRead) {
  editingPort.value = n.port
  draft.value = {
    port: n.port,
    service_name: n.service_name,
    protocol: n.protocol,
    remark: n.remark,
  }
  editorOpen.value = true
}

function closeEditor() {
  editorOpen.value = false
}

async function handleSave() {
  if (draft.value.port < 0 || draft.value.port > 65535) return
  saving.value = true
  try {
    await upsertNote(draft.value)
    closeEditor()
    await loadData()
  } catch (e) {
    console.error('save note failed:', e)
    alert(t('notes.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function handleDelete(n: NoteRead) {
  if (!confirm(t('notes.deleteConfirm', { port: n.port }))) return
  await deleteNote(n.port)
  await loadData()
}

function fmtTime(ts: number): string {
  if (!ts) return '—'
  const d = new Date(ts * 1000)
  return d.toLocaleString()
}

function exportNotesJson() {
  const data = notes.value.map(n => ({
    port: n.port,
    service_name: n.service_name,
    protocol: n.protocol,
    remark: n.remark,
    updated_at: new Date(n.updated_at * 1000).toISOString(),
  }))
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `portview-notes-${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => {
  loadData()
  loadAllPorts()
  loadLogos()
})

// 保存/删除 note 后，"未备注"分区需要即时反映 ——
// unremarked 是 computed，notes 变化即自动重算，无需额外刷新。
</script>

<template>
  <div>
    <div class="main-header">
      <h1>{{ t('notes.title') }}</h1>
      <div class="header-actions">
        <span class="meta">{{ t('notes.total', { n: notes.length }) }}</span>
        <button class="btn" :disabled="notes.length === 0" @click="exportNotesJson">
          ⬇ JSON
        </button>
        <button class="btn btn-primary" @click="openCreate">
          <Plus :size="14" class="btn-icon" />
          {{ t('notes.add') }}
        </button>
      </div>
    </div>

    <div class="main-body">
      <div class="search-box" v-if="notes.length || searchQuery">
        <span class="search-icon"><Search :size="15" /></span>
        <input
          v-model="searchQuery"
          type="text"
          :placeholder="t('notes.searchPlaceholder')"
        />
      </div>

      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        {{ t('common.loading') }}
      </div>

      <template v-else>
        <!-- v1.3：未备注端口分区 —— 让"看到就补备注"成为一条主路径 -->
        <div v-if="shownUnremarked.length" class="unremarked-panel" style="margin-bottom: 16px;">
          <div class="unremarked-header">
            <AlertCircle :size="15" class="unremarked-icon" />
            <span class="unremarked-title">{{ t('notes.unremarked') }} <span class="unremarked-count">{{ shownUnremarked.length }}</span></span>
          </div>
          <div class="unremarked-list">
            <div
              v-for="c in shownUnremarked"
              :key="'ur-' + c.port"
              class="unremarked-row"
            >
              <span class="unremarked-port">{{ c.port }}</span>
              <span class="unremarked-src" :class="(c.source || '').toLowerCase()">
                {{ c.source === 'docker' ? t('common.sourceDocker') : c.source === 'system' ? t('common.sourceSystem') : (c.source === 'host' ? t('common.sourceHost') : t('common.sourceUnknown')) }}
              </span>
              <span class="unremarked-svc">{{ c.service_name || (c.container || '—') }}</span>
              <span class="unremarked-protocol" v-if="c.protocol">{{ c.protocol.toUpperCase() }}</span>
              <button
                class="btn btn-sm btn-primary"
                @click="openEditByPort(c.port!)"
                :title="t('notes.unremarkedHint')"
              >
                <Plus :size="13" /> {{ t('notes.unremarkedBtn') }}
              </button>
            </div>
          </div>
        </div>

        <!-- v1.5.0：无 Logo 端口分区 —— 让"看到就补 Logo"成为一条主路径 -->
        <div v-if="shownNoLogo.length" class="unremarked-panel" style="margin-bottom: 16px;">
          <div class="unremarked-header">
            <ImageOff :size="15" class="unremarked-icon" />
            <span class="unremarked-title">{{ t('notes.noLogo') }} <span class="unremarked-count">{{ shownNoLogo.length }}</span></span>
          </div>
          <div class="unremarked-list">
            <div
              v-for="c in shownNoLogo"
              :key="'nl-' + c.port"
              class="unremarked-row"
            >
              <span class="unremarked-port">{{ c.port }}</span>
              <span class="unremarked-src" :class="(c.source || '').toLowerCase()">
                {{ c.source === 'docker' ? t('common.sourceDocker') : c.source === 'system' ? t('common.sourceSystem') : (c.source === 'host' ? t('common.sourceHost') : t('common.sourceUnknown')) }}
              </span>
              <span class="unremarked-svc">{{ c.service_name || (c.container || '—') }}</span>
              <span class="unremarked-protocol" v-if="c.protocol">{{ c.protocol.toUpperCase() }}</span>
              <div class="row-actions">
                <button
                  class="btn btn-sm btn-primary"
                  :disabled="isLogoBusy(c)"
                  @click="handleDiscoverLogo(c)"
                  :title="t('notes.noLogoDiscover')"
                >
                  <Search :size="13" class="spinning" v-if="isLogoBusy(c)" />
                  <Search :size="13" v-else />
                  {{ isLogoBusy(c) ? t('notes.logoDiscovering') : t('notes.noLogoDiscoverBtn') }}
                </button>
                <button
                  class="btn btn-sm"
                  :disabled="isLogoBusy(c)"
                  @click="handleUploadLogo(c)"
                  :title="t('notes.noLogoUploadBtn')"
                >
                  <ImagePlus :size="13" /> {{ t('notes.noLogoUploadBtn') }}
                </button>
                <button
                  class="btn btn-sm"
                  @click="openEditByPort(c.port!)"
                  :title="t('notes.noLogoNoteBtn')"
                >
                  <StickyNote :size="13" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="notes.length === 0 && shownUnremarked.length === 0 && shownNoLogo.length === 0" class="empty-state">
          <div class="empty-icon"><StickyNote :size="32" /></div>
          <div class="empty-text">{{ t('notes.empty') }}</div>
          <button class="btn btn-primary" :style="{ marginTop: '12px' }" @click="openCreate">
            <Plus :size="14" class="btn-icon" />
            {{ t('notes.add') }}
          </button>
        </div>

        <div v-if="notes.length" class="notes-list">
          <div v-for="n in notes" :key="n.port" class="note-item">
            <div class="note-main">
              <div class="note-port">{{ n.port }}</div>
              <div class="note-title">
                <span class="note-svc">{{ n.service_name || '—' }}</span>
                <span v-if="n.protocol" class="note-protocol">{{ n.protocol.toUpperCase() }}</span>
              </div>
              <div v-if="n.remark" class="note-remark">{{ n.remark }}</div>
              <div class="note-meta">
                <span>{{ t('notes.updated') }}</span>
                <span>{{ fmtTime(n.updated_at) }}</span>
              </div>
            </div>
            <div class="note-actions">
              <button class="btn btn-sm" :title="t('notes.edit')" @click="openEdit(n)">
                <Pencil :size="14" />
              </button>
              <button
                class="btn btn-sm btn-danger"
                :title="t('common.delete')"
                @click="handleDelete(n)"
              >
                <Trash2 :size="14" />
              </button>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- Editor Modal -->
    <div v-if="editorOpen" class="modal-overlay" @click.self="closeEditor">
      <div class="modal">
        <div class="modal-header">
          <h2>{{ isEditing ? t('notes.editTitle') : t('notes.addTitle') }}</h2>
          <button class="modal-close" @click="closeEditor">
            <X :size="16" />
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">{{ t('notes.portLabel') }}</label>
            <input
              v-model.number="draft.port"
              class="form-input"
              type="number"
              min="0"
              max="65535"
            />
          </div>
          <div class="form-group">
            <label class="form-label">{{ t('notes.serviceLabel') }}</label>
            <input
              v-model="draft.service_name"
              class="form-input"
              type="text"
              :placeholder="t('notes.servicePlaceholder')"
              maxlength="120"
            />
          </div>
          <div class="form-group">
            <label class="form-label">{{ t('notes.protocolLabel') }}</label>
            <select v-model="draft.protocol" class="form-input">
              <option value="">{{ t('notes.protocolBoth') }}</option>
              <option value="tcp">tcp</option>
              <option value="udp">udp</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">{{ t('notes.remarkLabel') }}</label>
            <textarea
              v-model="draft.remark"
              class="form-input"
              rows="4"
              :placeholder="t('notes.remarkPlaceholder')"
              maxlength="1024"
            ></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn" @click="closeEditor">{{ t('common.cancel') }}</button>
          <button class="btn btn-primary" :disabled="saving" @click="handleSave">
            {{ t('common.save') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 轻提示 -->
    <Teleport to="body">
      <div v-if="toastVisible" class="save-toast">{{ toast }}</div>
    </Teleport>
  </div>
</template>

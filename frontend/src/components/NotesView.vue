<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  listNotes,
  upsertNote,
  deleteNote,
  type NoteRead,
  type NotePayload,
} from '@/api'
import { Search, StickyNote, Plus, Pencil, Trash2, X } from 'lucide-vue-next'

const { t } = useI18n()

const notes = ref<NoteRead[]>([])
const loading = ref(false)
const saving = ref(false)
const searchQuery = ref('')

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

onMounted(() => {
  loadData()
})
</script>

<template>
  <div>
    <div class="main-header">
      <h1>{{ t('notes.title') }}</h1>
      <div class="header-actions">
        <span class="meta">{{ t('notes.total', { n: notes.length }) }}</span>
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

      <div v-else-if="notes.length === 0" class="empty-state">
        <div class="empty-icon"><StickyNote :size="32" /></div>
        <div class="empty-text">{{ t('notes.empty') }}</div>
        <button class="btn btn-primary" :style="{ marginTop: '12px' }" @click="openCreate">
          <Plus :size="14" class="btn-icon" />
          {{ t('notes.add') }}
        </button>
      </div>

      <div v-else class="notes-list">
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
  </div>
</template>

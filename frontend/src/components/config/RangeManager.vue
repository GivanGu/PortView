<template>
  <div class="range-manager">
    <!-- 列表模式 -->
    <div v-if="!editingRange" class="range-list">
      <div class="range-list-header">
        <span class="range-list-title">自定义监控区间 ({{ ranges.length }}/9)</span>
        <button
          class="btn btn--primary"
          @click="startAdd()"
          :disabled="ranges.length >= 9"
        >
          <Plus class="w-4 h-4" /> 添加区间
        </button>
      </div>

      <div
        v-if="ranges.length === 0"
        class="range-empty"
      >
        <GitBranch class="w-12 h-12 text-muted" />
        <p class="range-empty-text">暂无自定义区间</p>
      </div>

      <div v-else class="range-grid">
        <div
          v-for="range in ranges"
          :key="range.id"
          class="range-card"
          :style="{ borderColor: range.color }"
        >
          <div class="range-card-header">
            <span class="range-name">{{ range.name }}</span>
            <span
              class="range-badge"
              :style="{ backgroundColor: range.color + '20', color: range.color }"
            >{{ range.start_port }}-{{ range.end_port }}</span>
          </div>

          <div class="range-ports">
            <span>端口范围: {{ range.start_port }} — {{ range.end_port }}</span>
            <span>颜色: {{ range.color }}</span>
          </div>

          <div class="range-actions">
            <button class="btn btn--icon btn--ghost" @click="startEdit(range)" title="编辑">
              <Pencil class="w-3.5 h-3.5" />
            </button>
            <button
              class="btn btn--icon btn--ghost btn--danger"
              @click="confirmDelete(range)"
              title="删除"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 编辑/添加表单 -->
    <RangeForm
      v-if="editingRange"
      :range="editingRange"
      :submitting="submitting"
      @cancel="cancelEdit"
      @save="saveRange"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, defineAsyncComponent } from 'vue'
import { Plus, Pencil, Trash2, GitBranch } from '@/icons'

const RangeForm = defineAsyncComponent(() => import('./RangeForm.vue'))

const props = defineProps<{
  ranges: any[]
}>()

const emit = defineEmits<{
  (e: 'add', range: any): void
  (e: 'edit', id: string, range: any): void
  (e: 'delete', id: string): void
}>()

const editingRange = ref<any>(null)
const submitting = ref(false)

function startAdd() {
  editingRange.value = {
    id: null,
    name: '',
    start_port: 1,
    end_port: 1024,
    color: '#4f46e5',
  }
}

function startEdit(range: any) {
  editingRange.value = { ...range }
}

function cancelEdit() {
  editingRange.value = null
}

function confirmDelete(range: any) {
  if (confirm(`删除区间 "${range.name}"？此操作不可撤销。`)) {
    emit('delete', range.id)
  }
}

async function saveRange(range: any) {
  submitting.value = true
  try {
    if (range.id) {
      emit('edit', range.id, {
        name: range.name,
        start_port: range.start_port,
        end_port: range.end_port,
        color: range.color,
      })
    } else {
      emit('add', {
        name: range.name,
        start_port: range.start_port,
        end_port: range.end_port,
        color: range.color,
      })
    }
    editingRange.value = null
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.range-manager {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.range-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.range-list-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.range-empty {
  text-align: center;
  padding: 2.5rem 0;
  color: var(--text-muted);
}

.range-empty-text {
  margin-top: 0.75rem;
  font-size: 0.85rem;
}

.range-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
}

.range-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-left: 4px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.85rem 1rem;
  transition: border-color var(--transition-fast);
}

.range-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.range-name {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
}

.range-badge {
  font-size: 0.7rem;
  padding: 0.15rem 0.4rem;
  border-radius: var(--radius-sm);
  font-family: monospace;
}

.range-ports {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
}

.range-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.25rem;
}

.btn--danger:hover {
  background: var(--red-soft);
  color: var(--red);
}
</style>

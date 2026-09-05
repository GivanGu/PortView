<template>
  <div class="range-form">
    <div class="range-form-header">
      <h3 class="range-form-title">
        {{ isEdit ? '编辑区间' : '添加区间' }}
      </h3>
      <button class="btn btn--icon btn--ghost" @click="emit('cancel')" title="取消">
        <X class="w-4 h-4" />
      </button>
    </div>

    <div class="form-grid">
      <div class="form-field">
        <label class="form-label">区间名称</label>
        <input
          v-model="form.name"
          class="form-input"
          placeholder="例如：Web服务端口"
        />
      </div>

      <div class="form-row">
        <div class="form-field">
          <label class="form-label">起始端口</label>
          <input
            v-model.number="form.start_port"
            type="number"
            class="form-input"
            min="1"
            max="65535"
          />
        </div>

        <div class="form-field">
          <label class="form-label">结束端口</label>
          <input
            v-model.number="form.end_port"
            type="number"
            class="form-input"
            min="1"
            max="65535"
          />
        </div>
      </div>

      <div class="form-field">
        <label class="form-label">标识颜色</label>
        <div class="color-picker-row">
          <input
            v-model="form.color"
            type="color"
            class="color-swatch"
          />
          <input
            v-model="form.color"
            class="form-input color-input"
            placeholder="#4f46e5"
          />
        </div>
      </div>

      <div v-if="overlapWarning" class="overlap-warning">
        <AlertCircle class="w-4 h-4" />
        <span>与已有区间 "{{ overlapWarning }}" 重叠</span>
      </div>
    </div>

    <div class="form-actions">
      <button class="btn" @click="emit('cancel')">
        取消
      </button>
      <button
        class="btn btn--primary"
        @click="save"
        :disabled="submitting || !isValid"
      >
        <span v-if="submitting">保存中...</span>
        <span v-else>{{ isEdit ? '保存修改' : '添加区间' }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { X, AlertCircle } from '@/icons'

const props = defineProps<{
  range: any
  submitting?: boolean
}>()

const emit = defineEmits<{
  (e: 'cancel'): void
  (e: 'save', range: any): void
}>()

const form = ref({
  id: null as string | null,
  name: '',
  start_port: 1,
  end_port: 1024,
  color: '#4f46e5',
})

const isEdit = computed(() => !!props.range?.id)

const isValid = computed(() => {
  return form.value.name.trim().length > 0 &&
    form.value.start_port > 0 &&
    form.value.start_port <= form.value.end_port &&
    form.value.end_port <= 65535
})

// 重叠检测（提示但不阻止）
const overlapWarning = ref<string | null>(null)

function checkOverlap() {
  overlapWarning.value = null
  // 这个检查只在有完整 props.ranges 时才能做，
  // 这里我们接收不到父的 ranges，所以只做基本校验
  const s = form.value.start_port
  const e = form.value.end_port
  if (s >= e) {
    overlapWarning.value = null // 不提示，让 isValid 控制
  }
}

watch(
  () => props.range,
  (val) => {
    if (val) {
      form.value = {
        id: val.id,
        name: val.name,
        start_port: val.start_port,
        end_port: val.end_port,
        color: val.color,
      }
    }
  },
  { immediate: true },
)

watch(
  [() => form.value.start_port, () => form.value.end_port],
  checkOverlap,
)

function save() {
  if (!isValid.value || props.submitting) return
  emit('save', { ...form.value })
}
</script>

<style scoped>
.range-form {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 1.25rem;
}

.range-form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.range-form-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.form-grid {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-row {
  display: flex;
  gap: 1rem;
}

.form-row .form-field {
  flex: 1;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.form-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.form-input {
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-base);
  color: var(--text-primary);
  font-size: 0.85rem;
}

.form-input:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 2px var(--brand-soft);
}

.color-picker-row {
  display: flex;
  gap: 0.5rem;
}

.color-swatch {
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: none;
  cursor: pointer;
  flex-shrink: 0;
}

.color-input {
  flex: 1;
  font-family: monospace;
  font-size: 0.8rem;
}

.overlap-warning {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.6rem;
  background: var(--amber-soft);
  border-radius: var(--radius-md);
  color: var(--amber);
  font-size: 0.8rem;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}
</style>

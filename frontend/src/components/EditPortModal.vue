<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal" @keydown.esc="emit('close')">
      <div class="modal-header">
        <h3 class="modal-title">编辑端口服务</h3>
        <button class="modal-close" @click="emit('close')">
          <X class="w-4 h-4" />
        </button>
      </div>

      <div class="modal-body">
        <div class="modal-field">
          <label class="modal-label">端口号</label>
          <div class="modal-value">{{ card.port }}</div>
        </div>

        <div class="modal-field">
          <label class="modal-label">协议</label>
          <div class="modal-value">{{ card.protocol }}</div>
        </div>

        <div class="modal-field">
          <label class="modal-label">服务名称</label>
          <input
            v-model="serviceName"
            class="form-input"
            placeholder="请输入服务名称"
          />
        </div>

        <div class="modal-field">
          <label class="modal-label">来源</label>
          <div class="modal-value">{{ sourceLabel(card.source) }}</div>
        </div>

        <div
          v-if="card.container"
          class="modal-field"
        >
          <label class="modal-label">容器</label>
          <div class="modal-value">{{ card.container }}</div>
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn" @click="emit('close')">
          取消
        </button>
        <button
          class="btn btn--primary"
          @click="save"
          :disabled="!serviceName || saving"
        >
          <span v-if="saving">保存中...</span>
          <span v-else>保存</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { X } from '@/icons'

const props = defineProps<{
  card: any
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', card: any, name: string): void
}>()

const serviceName = ref(props.card?.service_name || '')
const saving = ref(false)

function sourceLabel(source: string) {
  const map: Record<string, string> = {
    docker: '容器',
    system: '系统',
    host: '主机',
  }
  return map[source] || '未知'
}

function save() {
  if (!serviceName.value) return
  saving.value = true
  emit('save', props.card, serviceName.value)
  saving.value = false
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 420px;
  margin: 1rem;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border);
}

.modal-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.modal-close {
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  padding: 0.25rem;
  cursor: pointer;
  color: var(--text-secondary);
}

.modal-close:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.modal-body {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.modal-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.modal-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.modal-value {
  font-size: 0.85rem;
  color: var(--text-primary);
  font-family: monospace;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 0.75rem 1.25rem;
  border-top: 1px solid var(--border);
}
</style>

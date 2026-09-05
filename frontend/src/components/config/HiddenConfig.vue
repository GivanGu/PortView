<template>
  <div class="hidden-config">
    <div class="hidden-config-header">
      <div class="hidden-input-group">
        <input
          v-model.number="newPort"
          type="number"
          class="form-input hidden-input"
          placeholder="输入端口号 (1-65535)"
        />
        <button
          class="btn btn--primary"
          @click="addPort"
          :disabled="!isValidPort"
        >
          <EyeOff class="w-4 h-4" /> 隐藏
        </button>
      </div>
    </div>

    <div v-if="hiddenPorts.length === 0" class="hidden-empty">
      <Eye class="w-12 h-12 text-muted" />
      <p class="hidden-empty-text">暂无隐藏的端口</p>
    </div>

    <div v-else class="hidden-list">
      <div
        v-for="port in hiddenPorts"
        :key="port"
        class="hidden-item"
      >
        <span class="hidden-port">{{ port }}</span>
        <button
          class="btn btn--icon btn--ghost"
          @click="$emit('remove', port)"
          title="取消隐藏"
        >
          <Eye class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Eye, EyeOff } from '@/icons'

const props = defineProps<{
  hiddenPorts: number[]
}>()

const emit = defineEmits<{
  (e: 'add', port: number): void
  (e: 'remove', port: number): void
  (e: 'reload'): void
}>()

const newPort = ref<number | null>(null)

const isValidPort = computed(() => {
  return newPort.value !== null && newPort.value !== undefined &&
    newPort.value > 0 && newPort.value <= 65535
})

function addPort() {
  if (isValidPort.value) {
    emit('add', newPort.value as number)
    newPort.value = null
  }
}
</script>

<style scoped>
.hidden-config {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.hidden-config-header {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.hidden-input-group {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.hidden-input {
  width: 140px;
  font-size: 0.8rem;
}

.hidden-empty {
  text-align: center;
  padding: 2rem 0;
  color: var(--text-muted);
}

.hidden-empty-text {
  margin-top: 0.75rem;
  font-size: 0.85rem;
}

.hidden-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.hidden-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.3rem 0.6rem;
  background: var(--bg-elevated);
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
}

.hidden-port {
  font-family: monospace;
  font-size: 0.8rem;
  color: var(--text-primary);
}

.btn--ghost {
  opacity: 0.6;
}

.btn--ghost:hover {
  opacity: 1;
  background: var(--bg-hover);
}
</style>

<template>
  <div class="conflict-list">
    <div
      v-for="port in ports"
      :key="port.port"
      class="conflict-item"
    >
      <div class="conflict-left">
        <span class="conflict-port">{{ port.port }}</span>
        <span class="conflict-protocol">{{ port.protocol }}</span>
        <span class="conflict-service">{{ port.service_name || '未知服务' }}</span>
      </div>

      <div v-if="port.conflict_with" class="conflict-detail">
        <AlertCircle class="w-3 h-3" />
        <span>冲突来源: {{ port.conflict_with }}</span>
      </div>
    </div>

    <div v-if="ports.length === 0" class="no-conflicts">
      <CheckCircle class="w-5 h-5" />
      <span>暂无端口冲突</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { AlertCircle, CheckCircle } from '@/icons'

defineProps<{
  ports: any[]
}>()
</script>

<style scoped>
.conflict-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.conflict-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.6rem 0.85rem;
  background: var(--red-soft);
  border: 1px solid var(--red-soft);
  border-radius: var(--radius-md);
  font-size: 0.8rem;
}

.conflict-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: monospace;
}

.conflict-port {
  font-weight: 700;
  color: var(--text-primary);
}

.conflict-protocol {
  padding: 0.1rem 0.3rem;
  background: var(--bg-elevated);
  border-radius: var(--radius-sm);
  font-size: 0.65rem;
}

.conflict-service {
  color: var(--text-secondary);
}

.conflict-detail {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  color: var(--red);
  font-size: 0.72rem;
}

.no-conflicts {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: var(--green);
  padding: 0.75rem;
}
</style>

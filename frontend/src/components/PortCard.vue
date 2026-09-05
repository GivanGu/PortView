<template>
  <div
    class="port-card"
    :class="[
      `type-${card.type}`,
      { conflict: card.conflict, hidden: card.hidden },
    ]"
  >
    <!-- 端口卡片操作按钮 -->
    <div class="port-actions">
      <button
        v-if="card.type === 'used'"
        class="port-action-btn"
        :title="`编辑服务名`"
        @click="$emit('edit', card)"
      >
        <Pencil class="w-3.5 h-3.5" />
      </button>
      <button
        v-if="card.type === 'used'"
        class="port-action-btn danger"
        :title="`隐藏端口`"
        @click="$emit('hide', card)"
      >
        <EyeOff class="w-3.5 h-3.5" />
      </button>
      <button
        v-if="card.type === 'unknown_range'"
        class="port-action-btn danger"
        :title="`隐藏范围`"
        @click="$emit('hide', card)"
      >
        <EyeOff class="w-3.5 h-3.5" />
      </button>
    </div>

    <!-- 已用端口卡片 -->
    <template v-if="card.type === 'used'">
      <div class="port-card-inner">
        <!-- 端口号 -->
        <div class="port-number-section">
          <span class="port-number">{{ card.port }}</span>
          <span
            class="port-protocol"
            :class="card.protocol?.toLowerCase()"
          >{{ card.protocol }}</span>
        </div>

        <!-- 服务信息 -->
        <div class="port-service-info">
          <div class="service-name">
            {{ card.service_name || '未知服务' }}
          </div>
          <div class="service-detail">
            <span
              class="source-badge"
              :class="card.source"
            >
              <component :is="sourceIcon(card.source)" class="w-3 h-3" />
              {{ sourceLabel(card.source) }}
            </span>

            <span
              v-if="card.container"
              class="container-info"
              :class="{ running: card.is_running, stopped: !card.is_running }"
            >
              <span
                class="status-dot"
                :class="{ running: card.is_running, stopped: !card.is_running }"
              />
              {{ card.container }}
            </span>

            <span v-if="card.image" class="image-info">
              {{ card.image }}
            </span>

            <!-- 冲突标记 -->
            <span
              v-if="card.conflict"
              class="conflict-badge"
            >
              <AlertCircle class="w-3 h-3" /> 冲突
            </span>
          </div>
        </div>
      </div>
    </template>

    <!-- 可用端口范围 -->
    <template v-else-if="card.type === 'gap'">
      <div class="gap-card-inner">
        <div class="gap-info">
          <span class="gap-range">{{ card.start_port }} — {{ card.end_port }}</span>
          <span class="gap-count">{{ card.available_count }} 个可用</span>
        </div>
        <span class="gap-badge">
          <CheckCircle class="w-3.5 h-3.5" /> 可用
        </span>
      </div>
    </template>

    <!-- 未知范围 -->
    <template v-else-if="card.type === 'unknown_range'">
      <div class="unknown-card-inner">
        <div class="unknown-range">
          {{ card.start_port }} — {{ card.end_port }}
        </div>
        <div class="unknown-count">
          {{ card.port_count }} 个未知服务端口
        </div>
        <span class="unknown-badge">
          <HelpCircle class="w-3.5 h-3.5" /> 未知
        </span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  Pencil, EyeOff, AlertCircle, CheckCircle,
  HelpCircle, Server, Package, Laptop,
} from '@/icons'

const props = defineProps<{
  card: any
}>()

type IconType = any

function sourceIcon(source: string): IconType {
  const map: Record<string, IconType> = {
    docker: Package,
    system: Server,
    host: Laptop,
  }
  return map[source] || Server
}

function sourceLabel(source: string): string {
  const map: Record<string, string> = {
    docker: '容器',
    system: '系统',
    host: '主机',
  }
  return map[source] || '未知'
}

defineEmits<{
  (e: 'edit', card: any): void
  (e: 'hide', card: any): void
}>()
</script>

<style scoped>
.port-card {
  margin: 0.25rem;
  padding: 0.6rem 0.75rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  position: relative;
  transition: all var(--transition-fast);
  height: 88px;
}

.port-card:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

/* 冲突染色 */
.port-card.conflict {
  border-left: 3px solid var(--red);
  background: var(--red-soft);
}

.port-actions {
  position: absolute;
  top: 0.4rem;
  right: 0.4rem;
  display: flex;
  gap: 0.15rem;
  opacity: 0.5;
  transition: opacity var(--transition-fast);
}

.port-card:hover .port-actions {
  opacity: 1;
}

.port-action-btn {
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  padding: 0.15rem;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.port-action-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.port-action-btn.danger:hover {
  background: var(--red-soft);
  color: var(--red);
}

/* 已用端口布局 */
.port-card-inner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding-right: 2.5rem;
}

.port-number-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 52px;
}

.port-number {
  font-family: monospace;
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
}

.port-protocol {
  font-size: 0.6rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 0.1rem 0.3rem;
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  color: var(--text-secondary);
}

.port-protocol.tcp { color: var(--amber); }
.port-protocol.udp { color: var(--cyan); }

.port-service-info {
  flex: 1;
  min-width: 0;
}

.service-name {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.service-detail {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
  font-size: 0.72rem;
  color: var(--text-secondary);
  margin-top: 0.15rem;
}

.source-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  padding: 0.1rem 0.35rem;
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  white-space: nowrap;
}

.source-badge.docker { color: var(--cyan); }
.source-badge.system { color: var(--amber); }
.source-badge.host { color: var(--purple); }

.container-info {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-family: monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  display: inline-block;
}

.status-dot.running {
  background: var(--green);
}

.status-dot.stopped {
  background: var(--red);
}

.image-info {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Gap 卡片 */
.gap-card-inner {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.gap-info {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.gap-range {
  font-family: monospace;
  font-size: 0.8rem;
  color: var(--text-primary);
}

.gap-count {
  font-size: 0.7rem;
  color: var(--text-secondary);
}

.gap-badge {
  color: var(--green);
  font-size: 0.7rem;
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
}

/* Unknown 卡片 */
.unknown-card-inner {
  display: flex;
  flex-direction: column;
}

.unknown-range {
  font-family: monospace;
  font-size: 0.85rem;
  color: var(--text-primary);
  margin-bottom: 0.2rem;
}

.unknown-count {
  font-size: 0.7rem;
  color: var(--text-secondary);
}

.unknown-badge {
  color: var(--text-muted);
  font-size: 0.7rem;
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  margin-top: 0.2rem;
  align-self: flex-start;
}

/* 冲突标记 */
.conflict-badge {
  color: var(--red);
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
}
</style>

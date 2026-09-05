<template>
  <div class="export-overlay" @click.self="emit('close')">
    <div class="export-menu">
      <div class="export-header">
        <h4 class="export-title">导出端口数据</h4>
        <button class="export-close" @click="emit('close')">
          <X class="w-3 h-3" />
        </button>
      </div>

      <div class="export-options">
        <button class="export-option" @click="exportAs('csv')">
          <FileSpreadsheet class="w-4 h-4" />
          <div>
            <div class="export-option-title">CSV 文件</div>
            <div class="export-option-desc">Excel / 电子表格</div>
          </div>
        </button>

        <button class="export-option" @click="exportAs('json')">
          <FileJson class="w-4 h-4" />
          <div>
            <div class="export-option-title">JSON</div>
            <div class="export-option-desc">结构化数据</div>
          </div>
        </button>

        <button class="export-option" @click="exportAs('txt')">
          <FileText class="w-4 h-4" />
          <div>
            <div class="export-option-title">TXT 文本</div>
            <div class="export-option-desc">便于复制分享</div>
          </div>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { X, FileSpreadsheet, FileJson, FileText } from '@/icons'

defineEmits<{
  (e: 'close'): void
  (e: 'export', format: 'csv' | 'json' | 'txt'): void
}>()

defineExpose({ exportAs })

function exportAs(format: 'csv' | 'json' | 'txt') {
  // 由父组件监听
}
</script>

<style scoped>
.export-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.export-menu {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 0.5rem;
  min-width: 220px;
  box-shadow: var(--shadow-lg);
}

.export-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border);
}

.export-title {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.export-close {
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  padding: 0.15rem;
  cursor: pointer;
  color: var(--text-secondary);
}

.export-close:hover {
  background: var(--bg-hover);
}

.export-options {
  padding: 0.5rem;
}

.export-option {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  width: 100%;
  padding: 0.5rem 0.6rem;
  border-radius: var(--radius-md);
  text-align: left;
  transition: all var(--transition-fast);
}

.export-option:hover {
  background: var(--bg-hover);
}

.export-option-title {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-primary);
}

.export-option-desc {
  font-size: 0.65rem;
  color: var(--text-secondary);
}
</style>

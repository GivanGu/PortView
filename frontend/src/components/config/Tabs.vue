<template>
  <div class="tabs">
    <div class="tabs-header" role="tablist">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :id="`tab-${tab.key}`"
        class="tab-button"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
        :aria-selected="activeTab === tab.key"
        role="tab"
      >
        {{ tab.label }}
      </button>
    </div>
    <div class="tabs-body">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  tabs: Array<{ key: string; label: string }>
  activeTab?: string
}>(), {
  tabs: () => [],
})

const emit = defineEmits<{
  (e: 'update:activeTab', v: string): void
}>()

const activeTab = computed({
  get: () => props.activeTab ?? props.tabs[0]?.key ?? '',
  set: (v: string) => emit('update:activeTab', v),
})
</script>

<style scoped>
.tabs {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.tabs-header {
  display: flex;
  gap: 0.125rem;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  padding: 0 0.25rem;
  overflow-x: auto;
}

.tab-button {
  padding: 0.5rem 1.25rem;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all var(--transition-fast);
  white-space: nowrap;
}

.tab-button:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.tab-button.active {
  color: var(--brand);
  border-bottom-color: var(--brand);
  background: var(--bg-base);
}

.tabs-body {
  border: 1px solid var(--border);
  border-top: none;
  border-radius: 0 0 var(--radius-lg) var(--radius-lg);
  background: var(--bg-card);
  padding: 1.25rem;
}
</style>

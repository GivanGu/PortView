<template>
  <div class="stat-card">
    <div class="stat-icon" :style="{ color: colorValue }">
      <component :is="icon" class="w-4 h-4" />
    </div>
    <div class="stat-content">
      <div class="stat-label">{{ label }}</div>
      <div class="stat-value">
        {{ value }}
        <span v-if="sub" class="stat-sub">/{{ sub }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  label: string
  value?: string | number
  sub?: string | number
  color?: string
  icon: any
}>(), {
  value: '--',
  sub: undefined,
  color: 'var(--text-secondary)',
})

const colorMap: Record<string, string> = {
  green: 'var(--green)',
  blue: 'var(--blue)',
  amber: 'var(--amber)',
  purple: 'var(--purple)',
  cyan: 'var(--cyan)',
  orange: 'var(--orange)',
  red: 'var(--red)',
}

const colorValue = colorMap[props.color] || props.color
</script>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.75rem 1rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  transition: box-shadow var(--transition-fast);
}

.stat-card:hover {
  box-shadow: var(--shadow-sm);
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.stat-value {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.1;
}

.stat-sub {
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-weight: 400;
}
</style>

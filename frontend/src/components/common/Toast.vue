<template>
  <transition name="toast-fade">
    <div
      v-if="visible"
      class="toast"
      :class="`toast--${currentType}`"
    >
      <div class="toast-content">
        <component :is="icon" class="toast-icon" />
        <span class="toast-text">{{ currentMessage }}</span>
      </div>
      <div class="toast-progress" :style="{ width: `${progress}%` }" />
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, computed, type Component } from 'vue'
import { Check, X, AlertCircle, Info } from '@/icons'

const props = withDefaults(defineProps<{
  message?: string
  type?: 'success' | 'error' | 'warning' | 'info'
  duration?: number
}>(), {
  message: '',
  type: 'info',
  duration: 3000,
})

const visible = ref(false)
const progress = ref(100)
const currentMessage = ref('')
const currentType = ref<'success' | 'error' | 'warning' | 'info'>('info')

const iconMap: Record<string, Component> = {
  success: Check,
  error: X,
  warning: AlertCircle,
  info: Info,
}

const icon = computed(() => iconMap[currentType.value])

function show(msg: string, type: 'success' | 'error' | 'warning' | 'info' = 'info') {
  currentMessage.value = msg
  currentType.value = type
  progress.value = 100
  visible.value = true

  // Reset animation
  const interval = props.duration / 100
  let count = 0
  const timer = setInterval(() => {
    count++
    progress.value = 100 - (count / interval) * 100
  }, props.duration / 100)

  setTimeout(() => {
    visible.value = false
    clearInterval(timer)
  }, props.duration)
}

defineExpose({ show })
</script>

<style scoped>
.toast {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  min-width: 240px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  z-index: 9999;
}

.toast--success { border-left: 4px solid var(--green); }
.toast--error { border-left: 4px solid var(--red); }
.toast--warning { border-left: 4px solid var(--amber); }
.toast--info { border-left: 4px solid var(--blue); }

.toast-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 1rem;
}

.toast-icon {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
}

.toast-text {
  font-size: 0.8rem;
  color: var(--text-primary);
}

.toast-progress {
  height: 2px;
  background: var(--brand);
  transition: width 0.1s linear;
}

.toast-fade-enter-active {
  animation: toast-in 0.2s var(--ease-out);
}
.toast-fade-leave-active {
  animation: toast-out 0.2s var(--ease-in);
}
.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

@keyframes toast-in {
  from { opacity: 0; transform: translateX(20px); }
  to { opacity: 1; transform: translateX(0); }
}
@keyframes toast-out {
  from { opacity: 1; transform: translateX(0); }
  to { opacity: 0; transform: translateX(20px); }
}
</style>

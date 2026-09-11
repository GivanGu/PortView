<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Link, Settings2 } from 'lucide-vue-next'

const { t } = useI18n()

const emit = defineEmits<{
  (e: 'configure'): void
  (e: 'dismissed'): void
}>()

function goConfigure() {
  emit('configure')
}

function cancel() {
  emit('dismissed')
}
</script>

<template>
  <div class="addr-prompt-overlay" @click.self="cancel">
    <div class="addr-prompt-card">
      <div class="addr-prompt-head">
        <Link :size="22" class="addr-prompt-ico" />
        <h2>{{ t('addrPrompt.title') }}</h2>
      </div>
      <p class="addr-prompt-desc">{{ t('addrPrompt.desc') }}</p>
      <div class="addr-prompt-actions">
        <button type="button" class="addr-btn-ghost" @click="cancel">
          {{ t('addrPrompt.cancel') }}
        </button>
        <button type="button" class="addr-btn-primary" @click="goConfigure">
          <Settings2 :size="15" />
          {{ t('addrPrompt.configure') }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.addr-prompt-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  animation: addr-overlay-in 0.2s ease;
}
@keyframes addr-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
.addr-prompt-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 28px 30px;
  width: 380px;
  max-width: 100%;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.35);
  animation: addr-card-in 0.2s ease;
}
@keyframes addr-card-in {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}
.addr-prompt-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.addr-prompt-ico { color: var(--accent); }
.addr-prompt-card h2 {
  font-size: 18px;
  margin: 0;
  color: var(--text-primary);
}
.addr-prompt-desc {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
  margin: 0 0 20px;
}
.addr-prompt-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.addr-btn-ghost {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 9px 16px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
}
.addr-btn-ghost:hover { border-color: var(--accent); }
.addr-btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 10px;
  padding: 9px 18px;
  font-size: 13px;
  cursor: pointer;
}
.addr-btn-primary:hover { filter: brightness(1.1); }
</style>

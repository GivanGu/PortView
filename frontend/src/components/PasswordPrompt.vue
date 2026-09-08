<script setup lang="ts">
import { ref } from 'vue'
import { useAuth } from '@/store/auth'
import { ShieldCheck, ShieldAlert } from 'lucide-vue-next'

const emit = defineEmits<{
  (e: 'saved'): void
  (e: 'dismissed'): void
}>()

const { doSetPassword, doToggle, doLogin } = useAuth()

const password = ref('')
const confirm = ref('')
// 默认勾选「同时开启登录保护」
const enableAuth = ref(true)
const busy = ref(false)
const error = ref('')

async function save() {
  if (password.value.length < 4) {
    error.value = '密码至少 4 位'
    return
  }
  if (password.value !== confirm.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  busy.value = true
  error.value = ''
  try {
    // 设置密码会撤销所有旧会话
    await doSetPassword(password.value)
    if (enableAuth.value) {
      // 开启登录保护后，重新登录以建立新会话（避免被登出）
      await doToggle(true)
      await doLogin(password.value)
    }
    emit('saved')
  } catch {
    error.value = '保存失败，请重试'
  } finally {
    busy.value = false
  }
}

function skip() {
  emit('dismissed')
}
</script>

<template>
  <div class="pw-prompt-overlay" @click.self="skip">
    <div class="pw-prompt-card">
      <div class="pw-prompt-head">
        <ShieldCheck :size="22" class="pw-prompt-ico" />
        <h2>设置访问密码</h2>
      </div>
      <p class="pw-prompt-desc">
        为 PortView 设置一个访问密码，可防止他人查看你的端口信息。
        设置后需重新登录。
      </p>
      <form @submit.prevent="save">
        <label class="pw-field">
          <span>新密码（至少 4 位）</span>
          <input
            v-model="password"
            type="password"
            class="pw-input"
            placeholder="新密码"
            autocomplete="new-password"
            autofocus
          />
        </label>
        <label class="pw-field">
          <span>确认密码</span>
          <input
            v-model="confirm"
            type="password"
            class="pw-input"
            placeholder="再次输入密码"
            autocomplete="new-password"
          />
        </label>
        <label class="pw-check">
          <input v-model="enableAuth" type="checkbox" />
          <span>同时开启登录保护</span>
        </label>
        <p class="pw-warning">
          <ShieldAlert :size="13" />
          请牢记密码，忘记密码将无法恢复。
        </p>
        <p v-if="error" class="pw-error">{{ error }}</p>
        <div class="pw-actions">
          <button type="button" class="pw-btn-ghost" :disabled="busy" @click="skip">
            暂不设置
          </button>
          <button
            type="submit"
            class="pw-btn-primary"
            :disabled="busy || password.length < 4 || password !== confirm"
          >
            {{ busy ? '保存中…' : '保存' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.pw-prompt-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  animation: pw-overlay-in 0.2s ease;
}
@keyframes pw-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
.pw-prompt-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 28px 30px;
  width: 360px;
  max-width: 100%;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.35);
  animation: pw-card-in 0.2s ease;
}
@keyframes pw-card-in {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}
.pw-prompt-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.pw-prompt-ico { color: var(--accent); }
.pw-prompt-card h2 {
  font-size: 18px;
  margin: 0;
  color: var(--text-primary);
}
.pw-prompt-desc {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
  margin: 0 0 18px;
}
.pw-field {
  display: block;
  margin-bottom: 12px;
}
.pw-field > span {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}
.pw-input {
  width: 100%;
  box-sizing: border-box;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 14px;
  color: var(--text-primary);
  outline: none;
}
.pw-input:focus { border-color: var(--accent); }
.pw-check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  margin: 4px 0 12px;
  cursor: pointer;
  user-select: none;
}
.pw-check input { accent-color: var(--accent); }
.pw-warning {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #f59e0b;
  margin: 0 0 4px;
  padding: 8px 12px;
  background: rgba(245, 158, 11, 0.08);
  border-radius: 6px;
}
.pw-error {
  color: var(--rose);
  font-size: 12px;
  margin: 8px 0 0;
}
.pw-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}
.pw-btn-ghost {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 9px 16px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
}
.pw-btn-ghost:hover { border-color: var(--accent); }
.pw-btn-ghost:disabled { opacity: 0.6; cursor: not-allowed; }
.pw-btn-primary {
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 10px;
  padding: 9px 20px;
  font-size: 13px;
  cursor: pointer;
}
.pw-btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
</style>

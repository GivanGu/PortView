<template>
  <div class="login-bg">
    <div class="login-card">
      <div class="login-header">
        <h1 class="login-title">⚡ PortView</h1>
        <p class="login-subtitle">端口监控与可视化</p>
      </div>

      <form @submit.prevent="onLogin" class="login-form">
        <div class="form-field">
          <label class="form-label" for="password-input">密码</label>
          <input
            id="password-input"
            v-model="password"
            type="password"
            class="form-input"
            placeholder="请输入密码"
            autocomplete="current-password"
            minlength="6"
            required
          />
        </div>

        <button
          type="submit"
          class="login-btn"
          :disabled="loading || !password.trim()"
        >
          <span v-if="loading" class="spinner-border spinner-border-sm me-2"></span>
          登录
        </button>

        <div v-if="errorMsg" class="error-message">
          {{ errorMsg }}
        </div>

        <div class="login-footer">
          <p class="hint-text">
            默认密码: <code class="hint-code">portview123</code>
          </p>
          <p class="hint-text">
            登录后请尽快修改密码
          </p>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const password = ref('')
const errorMsg = ref<string | null>(null)
const loading = ref(false)

const router = useRouter()
const auth = useAuthStore()

async function onLogin() {
  if (!password.value.trim() || loading.value) return

  loading.value = true
  errorMsg.value = null

  const ok = await auth.login(password.value.trim())
  if (ok) {
    router.replace('/overview')
  } else {
    errorMsg.value = '密码错误，请重试'
  }
  loading.value = false
}
</script>

<style scoped>
.login-bg {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, hsl(200, 30%, 8%) 0%, hsl(200, 30%, 12%) 100%);
}

.login-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: 2.5rem;
  width: 100%;
  max-width: 360px;
}

.login-header {
  text-align: center;
  margin-bottom: 2rem;
}

.login-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.login-subtitle {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.form-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.form-input {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-base);
  color: var(--text-primary);
  font-size: 0.9rem;
  transition: border-color var(--transition-fast);
}

.form-input:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 2px var(--brand-soft);
}

.login-btn {
  background: var(--brand);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  padding: 0.6rem 1rem;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.login-btn:hover:not(:disabled) {
  background: var(--brand-hover);
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-message {
  color: var(--red);
  font-size: 0.8rem;
  text-align: center;
  padding: 0.25rem;
}

.login-footer {
  text-align: center;
  margin-top: 0.5rem;
}

.hint-text {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin: 0.125rem 0;
}

.hint-code {
  background: var(--bg-elevated);
  padding: 0.1rem 0.375rem;
  border-radius: var(--radius-sm);
  font-size: 0.7rem;
  color: var(--text-secondary);
}
</style>

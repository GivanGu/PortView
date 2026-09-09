<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuth } from '@/store/auth'

const { t } = useI18n()

const { state, doLogin } = useAuth()
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  if (!password.value) return
  busy.value = true
  error.value = ''
  try {
    await doLogin(password.value)
    if (state.value.logged_in) {
      window.location.reload()
    }
  } catch {
    error.value = t('login.wrongPassword')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="login-logo">📡</div>
      <h1>PortView</h1>
      <p class="login-sub">{{ t('login.subtitle') }}</p>
      <form @submit.prevent="submit">
        <input
          v-model="password"
          type="password"
          class="login-input"
          :placeholder="t('login.placeholder')"
          autofocus
        />
        <p v-if="error" class="login-error">{{ error }}</p>
        <button type="submit" class="login-btn" :disabled="busy || !password">
          {{ busy ? t('login.buttonLoading') : t('login.button') }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}
.login-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 32px 36px;
  width: 320px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
}
.login-logo { font-size: 40px; text-align: center; margin-bottom: 8px; }
.login-card h1 { text-align: center; font-size: 20px; margin: 0 0 4px; color: var(--text-primary); }
.login-sub { text-align: center; font-size: 13px; color: var(--text-muted); margin: 0 0 20px; }
.login-input {
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
.login-input:focus { border-color: var(--accent); }
.login-error { color: var(--rose); font-size: 12px; margin: 8px 0 0; }
.login-btn {
  width: 100%;
  margin-top: 14px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 10px;
  padding: 10px;
  font-size: 14px;
  cursor: pointer;
}
.login-btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>

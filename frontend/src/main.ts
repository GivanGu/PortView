/**
 * PortView 前端入口
 * - Vue 3 Composition API
 * - Pinia 状态管理
 * - Vue Router + 登录守卫
 * - @lucide/vue 图标
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from '@/router'

import App from './App.vue'
import './style.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// 初始化认证状态
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
auth.init()

app.mount('#app')

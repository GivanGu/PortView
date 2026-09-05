/**
 * Vue Router — 路由表 + 登录守卫
 *
 * 路由结构：
 *   /login         → LoginView (公开)
 *   /               → 重定向到 /overview
 *   /overview       → OverviewView
 *   /ports          → PortsView
 *   /hidden         → HiddenPortsView
 *   /config         → ConfigView
 *   /notifications  → NotificationsView
 */
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    redirect: '/overview',
  },
  {
    path: '/overview',
    name: 'Overview',
    component: () => import('@/views/OverviewView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/ports',
    name: 'Ports',
    component: () => import('@/views/PortsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/hidden',
    name: 'Hidden',
    component: () => import('@/views/HiddenPortsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/config',
    name: 'Config',
    component: () => import('@/views/ConfigView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/notifications',
    name: 'Notifications',
    component: () => import('@/views/NotificationsView.vue'),
    meta: { requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollRestoration: 'preserved',
})

// 全局前置守卫 — 登录态校验
router.beforeEach((to, from, next) => {
  const auth = useAuthStore()

  // 等待初始化完成
  if (!auth.initialized) {
    // 不阻塞，先放行
    next()
    return
  }

  const requiresAuth = to.meta.requiresAuth ?? true
  const isLogin = to.name === 'Login'

  if (requiresAuth && !auth.isAuthenticated && !isLogin) {
    next('/login')
  } else if (isLogin && auth.isAuthenticated && to.name === 'Login') {
    // 已登录访问登录页 → 跳转到首页
    next('/overview')
  } else {
    next()
  }
})

export default router

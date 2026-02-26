import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', component: () => import('../views/Login.vue') },
  { path: '/', component: () => import('../views/Dashboard.vue') },
  { path: '/alerts', component: () => import('../views/Alerts.vue') },
  { path: '/jobs', component: () => import('../views/Jobs.vue') },
  { path: '/settings', component: () => import('../views/Settings.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.path !== '/login' && !auth.token) return '/login'
})

export default router

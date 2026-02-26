<template>
  <div v-if="auth.token" class="layout">
    <div class="sidebar">
      <div class="sidebar-brand">🔥 热度脉冲</div>
      <router-link to="/">📊 监控面板</router-link>
      <router-link to="/alerts">🚨 告警历史</router-link>
      <router-link to="/jobs">⏱️ 任务管理</router-link>
      <router-link to="/settings">⚙️ 系统配置</router-link>
      <div class="sidebar-footer">
        <a href="#" @click.prevent="auth.logout(); $router.push('/login')">🚪 退出登录</a>
      </div>
    </div>
    <div class="content">
      <router-view />
    </div>
    <!-- Toast container -->
    <div class="toast-container">
      <div v-for="t in toasts" :key="t.id" :class="['toast', 'toast-' + t.type]">
        {{ t.type === 'ok' ? '✓' : t.type === 'error' ? '✗' : 'ℹ' }} {{ t.msg }}
      </div>
    </div>
  </div>
  <router-view v-else />
</template>

<script setup>
import { ref, provide, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()
const toasts = ref([])
let toastId = 0

function toast(msg, type = 'info') {
  const id = ++toastId
  toasts.value.push({ id, msg, type })
  setTimeout(() => { toasts.value = toasts.value.filter(t => t.id !== id) }, 3000)
}

// Global WebSocket
const wsData = ref({ ranking: [], anomalies: [], runningJobs: {} })
let ws = null

function connectWs() {
  if (!auth.token) return
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${proto}://${location.host}/ws`)
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data)
    if (msg.type === 'update') {
      if (msg.ranking) wsData.value.ranking = msg.ranking
      if (msg.anomalies) wsData.value.anomalies = msg.anomalies
    }
    if (msg.type === 'job_status') {
      wsData.value.runningJobs = msg.jobs || {}
    }
    if (msg.type === 'job_done') {
      wsData.value.runningJobs = msg.jobs || {}
      const label = msg.job
      if (msg.status === 'ok') toast(`${label} 完成 (${msg.duration}s)`, 'ok')
      else toast(`${label} 失败: ${msg.message}`, 'error')
    }
  }
  ws.onclose = () => setTimeout(connectWs, 3000)
}

onMounted(connectWs)
onUnmounted(() => { if (ws) ws.close() })

provide('toast', toast)
provide('wsData', wsData)
</script>

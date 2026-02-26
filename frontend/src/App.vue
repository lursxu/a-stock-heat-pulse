<template>
  <div v-if="auth.token" class="layout">
    <div class="sidebar">
      <h2>🔥 热度脉冲</h2>
      <router-link to="/">📊 监控面板</router-link>
      <router-link to="/alerts">🚨 告警历史</router-link>
      <router-link to="/settings">⚙️ 系统配置</router-link>
      <a href="#" @click.prevent="auth.logout(); $router.push('/login')">🚪 退出</a>
    </div>
    <div class="content"><router-view /></div>
  </div>
  <router-view v-else />
</template>

<script setup>
import { useAuthStore } from './stores/auth'
const auth = useAuthStore()
</script>

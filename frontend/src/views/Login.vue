<template>
  <div class="login-wrap">
    <div class="login-box card">
      <h2>🔥 A股热度脉冲</h2>
      <input v-model="pwd" type="password" placeholder="输入密码" @keyup.enter="doLogin" />
      <button class="btn btn-primary" @click="doLogin" :disabled="loading">{{ loading ? '登录中...' : '登 录' }}</button>
      <p v-if="err" style="color:var(--red);font-size:12px;margin-top:8px;text-align:center">{{ err }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const pwd = ref('')
const err = ref('')
const loading = ref(false)

async function doLogin() {
  loading.value = true; err.value = ''
  try { await auth.login(pwd.value); router.push('/') }
  catch { err.value = '密码错误' }
  finally { loading.value = false }
}
</script>

<template>
  <div class="login-box card">
    <h3>🔒 登录</h3>
    <input v-model="pwd" type="password" placeholder="请输入密码" @keyup.enter="doLogin" />
    <button class="btn" @click="doLogin">登录</button>
    <p v-if="err" class="tag-red" style="margin-top:8px;font-size:13px">{{ err }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const pwd = ref('')
const err = ref('')
const router = useRouter()
const auth = useAuthStore()

async function doLogin() {
  try { await auth.login(pwd.value); router.push('/') }
  catch { err.value = '密码错误' }
}
</script>

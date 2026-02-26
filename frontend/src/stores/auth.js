import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')

  async function login(password) {
    const { data } = await axios.post('/api/auth', { password })
    token.value = data.token
    localStorage.setItem('token', data.token)
    axios.defaults.headers.common['Authorization'] = `Bearer ${data.token}`
  }

  function logout() {
    token.value = ''
    localStorage.removeItem('token')
    delete axios.defaults.headers.common['Authorization']
  }

  if (token.value) {
    axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
  }

  // Auto logout on 401
  axios.interceptors.response.use(r => r, err => {
    if (err.response?.status === 401) {
      logout()
      window.location.href = '/login'
    }
    return Promise.reject(err)
  })

  return { token, login, logout }
})

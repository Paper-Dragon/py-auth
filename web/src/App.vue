<template>
  <div class="app">
    <LoginForm v-if="!isLoggedIn" @login-success="onLoginSuccess" />
    <AdminPanel v-else :username="username" @logout="onLogout" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import LoginForm from './components/LoginForm.vue'
import AdminPanel from './components/AdminPanel.vue'
import { api } from './api'

const isLoggedIn = ref(false)
const username = ref('')

const onLoginSuccess = (data) => {
  username.value = data.username
  isLoggedIn.value = true
  localStorage.setItem('username', data.username)
}

const onLogout = () => {
  api.logout()
  isLoggedIn.value = false
  username.value = ''
  localStorage.removeItem('username')
}

// 页面加载时恢复登录状态
onMounted(() => {
  const token = localStorage.getItem('authToken')
  const savedUsername = localStorage.getItem('username')
  
  if (token && savedUsername) {
    // 有保存的 token 和用户名，直接恢复登录状态
    api.setToken(token)
    username.value = savedUsername
    isLoggedIn.value = true
    
    // 后台静默验证 token（不影响用户体验）
    // 只有明确收到 401 响应时才会触发登出
  }
})
</script>


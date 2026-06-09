<template>
  <div class="login-page">
    <aside class="brand-panel" aria-hidden="true">
      <div class="brand-inner">
        <div class="brand-logo">
          <span class="logo-mark">
            <el-icon :size="22"><Lock /></el-icon>
          </span>
          <span class="logo-name">授权管理</span>
        </div>

        <div class="brand-copy">
          <h1>授权管理</h1>
        </div>
      </div>
      <div class="brand-grid" />
    </aside>

    <main class="form-panel">
      <div class="form-shell">
        <header class="form-header">
          <div class="mobile-logo">
            <el-icon :size="20"><Lock /></el-icon>
          </div>
          <h2>登录</h2>
        </header>

        <el-form
          ref="formRef"
          :model="formData"
          :rules="rules"
          class="login-form"
          label-position="top"
          @submit.prevent="handleLogin"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="formData.username"
              placeholder="请输入用户名"
              size="large"
              autocomplete="username"
            >
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="formData.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              show-password
              autocomplete="current-password"
              @keyup.enter="handleLogin"
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <transition name="fade">
            <el-alert
              v-if="error"
              :title="error"
              type="error"
              :closable="true"
              show-icon
              class="error-alert"
              @close="error = ''"
            />
          </transition>

          <el-button
            type="primary"
            size="large"
            class="submit-btn"
            :loading="loading"
            @click="handleLogin"
          >
            {{ loading ? '登录中…' : '登录' }}
          </el-button>
        </el-form>

        <footer class="form-footer">
          <span>授权管理面板</span>
        </footer>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const router = useRouter()
const formRef = ref(null)
const formData = ref({
  username: '',
  password: '',
})

const loading = ref(false)
const error = ref('')

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const handleLogin = async () => {
  if (!formRef.value) return

  try {
    const valid = await formRef.value.validate().catch(() => false)
    if (!valid) return

    loading.value = true
    error.value = ''

    const data = await api.login(formData.value.username, formData.value.password)
    localStorage.setItem('username', data.username)
    localStorage.setItem('isAdmin', data.is_admin ? '1' : '0')
    ElMessage.success('登录成功')
    router.push({ name: 'Overview' })
  } catch (e) {
    error.value = e.message || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  min-height: 100dvh;
  display: grid;
  grid-template-columns: minmax(320px, 1.1fr) minmax(360px, 0.9fr);
  background: var(--color-bg-secondary);
}

/* ── 左侧品牌区（与后台侧栏色调一致） ── */
.brand-panel {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 40px;
  background: linear-gradient(160deg, #001529 0%, #002140 55%, #0a2744 100%);
  color: #fff;
  overflow: hidden;
}

.brand-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: radial-gradient(ellipse 80% 70% at 30% 40%, #000 20%, transparent 75%);
  pointer-events: none;
}

.brand-inner {
  position: relative;
  z-index: 1;
  max-width: 420px;
  width: 100%;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 40px;
}

.logo-mark {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(24, 144, 255, 0.2);
  border: 1px solid rgba(24, 144, 255, 0.35);
  border-radius: 10px;
  color: #69b1ff;
}

.logo-name {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.brand-copy h1 {
  margin: 0 0 14px;
  font-size: clamp(24px, 3vw, 32px);
  font-weight: 700;
  line-height: 1.35;
  letter-spacing: -0.02em;
}

/* ── 右侧表单区 ── */
.form-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 24px;
  padding-top: max(32px, env(safe-area-inset-top));
  padding-bottom: max(32px, env(safe-area-inset-bottom));
}

.form-shell {
  width: 100%;
  max-width: 400px;
  animation: rise 0.45s ease-out;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.form-header {
  margin-bottom: 32px;
}

.mobile-logo {
  display: none;
  width: 44px;
  height: 44px;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  border-radius: 12px;
  background: var(--color-primary-gradient);
  color: #fff;
}

.form-header h2 {
  margin: 0 0 8px;
  font-size: 26px;
  font-weight: 700;
  color: var(--color-text-primary);
  letter-spacing: -0.02em;
}

.form-header p {
  margin: 0;
  font-size: 14px;
  color: var(--color-text-tertiary);
}

.login-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--color-text-secondary);
  padding-bottom: 6px;
}

.login-form :deep(.el-input__wrapper) {
  border-radius: 10px;
  padding: 4px 12px;
  box-shadow: 0 0 0 1px var(--color-border) inset;
  transition: box-shadow var(--transition-fast);
}

.login-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #c0c4cc inset;
}

.login-form :deep(.el-input.is-focus .el-input__wrapper) {
  box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.25) inset;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 22px;
}

.error-alert {
  margin-bottom: 16px;
  border-radius: 10px;
}

.submit-btn {
  width: 100%;
  height: 48px;
  margin-top: 4px;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  background: var(--color-primary-gradient);
  transition: transform var(--transition-fast), box-shadow var(--transition-fast);
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.35);
}

.form-footer {
  margin-top: 32px;
  text-align: center;
  font-size: 12px;
  color: var(--color-text-light);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ── 响应式：窄屏折叠品牌区 ── */
@media (max-width: 860px) {
  .login-page {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
  }

  .brand-panel {
    padding: 28px 24px 32px;
    align-items: flex-start;
  }

  .brand-inner {
    max-width: none;
  }

  .brand-logo {
    margin-bottom: 20px;
  }

  .brand-copy h1 {
    font-size: 20px;
  }

  .form-panel {
    padding: 24px 20px 32px;
  }

  .mobile-logo {
    display: flex;
  }

  .form-header h2 {
    font-size: 22px;
  }
}

@media (max-width: 480px) {
  .brand-panel {
    padding: 20px 16px 24px;
  }

  .brand-copy h1 {
    font-size: 18px;
  }

  .form-panel {
    padding: 20px 16px 28px;
  }
}
</style>

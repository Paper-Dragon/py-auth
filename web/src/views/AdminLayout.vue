<template>
  <el-container class="admin-layout">
    <el-aside class="aside" :class="{ collapsed: asideCollapsed }">
      <div class="logo">
        <el-icon :size="24"><Lock /></el-icon>
        <span v-show="!asideCollapsed" class="logo-text">授权管理</span>
      </div>
      <el-menu
        :key="menuKey"
        :default-active="activeMenu"
        class="menu"
        router
        :collapse="asideCollapsed"
        :collapse-transition="false"
      >
        <el-menu-item v-for="item in menuItems" :key="item.index" :index="item.index">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container class="main-container">
      <el-header class="header">
        <div class="header-left">
          <el-button class="collapse-btn" text @click="toggleAside">
            <el-icon :size="18"><Fold v-if="!asideCollapsed" /><Expand v-else /></el-icon>
          </el-button>
          <div>
            <div class="page-title">{{ pageTitle }}</div>
            <div v-if="pageSubtitle" class="page-subtitle">{{ pageSubtitle }}</div>
          </div>
        </div>
        <div class="header-right">
          <div class="user-info">
            <el-avatar :size="32">{{ username.charAt(0).toUpperCase() }}</el-avatar>
            <span class="username">{{ username }}</span>
            <el-tag v-if="isAdmin" size="small" type="success">管理员</el-tag>
          </div>
          <el-dropdown trigger="click">
            <span class="el-dropdown-link">
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="showChangePassword">修改密码</el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>

    <el-dialog v-model="showPasswordDialog" title="修改密码" width="400px">
      <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-width="80px">
        <el-form-item label="旧密码" prop="oldPassword">
          <el-input v-model="passwordForm.oldPassword" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="passwordForm.newPassword" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="passwordForm.confirmPassword"
            type="password"
            show-password
            @keyup.enter="handleChangePassword"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPasswordDialog = false">取消</el-button>
        <el-button type="primary" @click="handleChangePassword" :loading="changingPassword">确认</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Lock, Box, Goods, Tickets, Wallet, User, Setting, Document, ArrowDown, Reading,
  HomeFilled, Fold, Expand,
} from '@element-plus/icons-vue'
import { api, isSessionExpiredError } from '../api'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const username = ref(localStorage.getItem('username') || 'Admin')
const isAdmin = ref(localStorage.getItem('isAdmin') === '1')
const asideCollapsed = ref(false)

const activeMenu = computed(() => route.path)

const adminMenuItems = [
  { index: '/products', title: '产品管理', icon: Goods },
  { index: '/orders', title: '订单管理', icon: Tickets },
  { index: '/epay', title: '易支付', icon: Wallet },
  { index: '/users', title: '用户管理', icon: User },
  { index: '/settings', title: '系统配置', icon: Setting },
  { index: '/logs', title: '审计日志', icon: Document },
]

const menuItems = computed(() => {
  const items = [
    { index: '/overview', title: '概览', icon: HomeFilled },
    { index: '/devices', title: '设备管理', icon: Box },
  ]
  if (isAdmin.value) {
    items.push(...adminMenuItems)
  }
  items.push({ index: '/docs', title: '使用文档', icon: Reading })
  return items
})

const menuKey = computed(() => `${isAdmin.value}-${menuItems.value.length}`)

const pageMeta = {
  '/overview': { title: '概览' },
  '/devices': { title: '设备管理' },
  '/products': { title: '产品管理' },
  '/orders': { title: '订单管理' },
  '/epay': { title: '易支付' },
  '/users': { title: '用户管理' },
  '/settings': { title: '系统配置' },
  '/logs': { title: '审计日志' },
  '/docs': { title: '使用文档' },
}

const pageTitle = computed(() => pageMeta[route.path]?.title || '')
const pageSubtitle = computed(() => pageMeta[route.path]?.subtitle || '')

const showPasswordDialog = ref(false)
const changingPassword = ref(false)
const passwordFormRef = ref(null)
const passwordForm = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })

const passwordRules = {
  oldPassword: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '至少6位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (_, value, callback) => {
        if (value !== passwordForm.value.newPassword) callback(new Error('密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

const toggleAside = () => {
  asideCollapsed.value = !asideCollapsed.value
}

const showChangePassword = () => {
  passwordForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
  showPasswordDialog.value = true
}

const handleChangePassword = async () => {
  if (!passwordFormRef.value) return
  try {
    await passwordFormRef.value.validate()
    changingPassword.value = true
    await api.changePassword(passwordForm.value.oldPassword, passwordForm.value.newPassword)
    ElMessage.success('密码修改成功')
    showPasswordDialog.value = false
  } catch (e) {
    if (isSessionExpiredError(e)) {
      showPasswordDialog.value = false
      return
    }
    if (e?.message) ElMessage.error(e.message)
  } finally {
    changingPassword.value = false
  }
}

const handleLogout = () => {
  api.logout()
  localStorage.removeItem('username')
  localStorage.removeItem('isAdmin')
  router.push('/login')
}

onMounted(async () => {
  try {
    const me = await api.getMe()
    isAdmin.value = !!me?.is_admin
    username.value = me?.username || username.value
    localStorage.setItem('isAdmin', me?.is_admin ? '1' : '0')
    localStorage.setItem('username', username.value)
  } catch {
    // keep cached session info
  }
})
</script>

<style scoped>
.admin-layout {
  height: 100vh;
  overflow: hidden;
}

.aside {
  --aside-width: 220px;
  --aside-collapsed-width: 64px;
  width: var(--aside-width);
  flex: 0 0 var(--aside-width);
  background: #001529;
  color: white;
  display: flex;
  flex-direction: column;
  transition: width 0.2s, flex-basis 0.2s;
  overflow: hidden;
}

.aside.collapsed {
  width: var(--aside-collapsed-width);
  flex: 0 0 var(--aside-collapsed-width);
}

.logo {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  background: #002140;
  flex-shrink: 0;
  overflow: hidden;
}

.aside.collapsed .logo {
  justify-content: center;
  padding: 0;
  gap: 0;
}

.logo-text {
  white-space: nowrap;
  overflow: hidden;
}

.menu {
  border-right: none;
  background: transparent;
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
  width: 100% !important;
}

.menu:not(.el-menu--collapse) {
  min-width: var(--aside-width);
}

.menu.el-menu--collapse {
  min-width: var(--aside-collapsed-width);
}

.menu :deep(.el-menu-item) {
  color: rgba(255, 255, 255, 0.65);
}

.menu :deep(.el-menu-item.is-active) {
  background: #1890ff !important;
  color: white;
}

.menu :deep(.el-menu-item:hover) {
  color: white;
}

.main-container {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.header {
  background: white;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: 56px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.collapse-btn {
  padding: 4px;
  flex-shrink: 0;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  line-height: 1.3;
}

.page-subtitle {
  font-size: 12px;
  color: #909399;
  line-height: 1.3;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.username {
  font-size: 14px;
  color: #606266;
}

.main {
  background: #f0f2f5;
  padding: 16px 20px;
  overflow: auto;
}

@media (min-width: 1280px) {
  .main {
    padding: 20px 28px;
  }
}

@media (min-width: 1600px) {
  .main {
    padding: 24px 32px;
  }
}

@media (max-width: 768px) {
  .aside:not(.collapsed) {
    position: fixed;
    z-index: 1000;
    height: 100vh;
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.15);
  }

  .aside.collapsed {
    position: relative;
    z-index: 1;
  }

  .username {
    display: none;
  }
}
</style>

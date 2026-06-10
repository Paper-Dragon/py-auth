<template>
  <div class="page-container">
    <main class="page-content">
      <div class="card">
        <div class="card-header">
          <div class="header-meta">
            <h2>用户列表</h2>
          </div>
          <div class="header-actions">
            <el-button type="primary" @click="openCreateDialog">
              <el-icon><Plus /></el-icon>
              <span>新建用户</span>
            </el-button>
          </div>
        </div>
        <el-table
          :data="users"
          v-loading="loading"
          row-key="id"
          stripe
          border
          class="admin-data-table"
          empty-text="暂无用户"
        >
          <el-table-column prop="username" label="用户名" min-width="140" show-overflow-tooltip />
          <el-table-column label="管理员" min-width="88" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_admin ? 'success' : 'info'" size="small">
                {{ row.is_admin ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" min-width="88" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
                {{ row.is_active ? '已激活' : '已禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" min-width="160">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" min-width="120" align="center">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openEditDialog(row)">编辑</el-button>
              <el-popconfirm title="确定要删除此用户吗？" @confirm="handleDelete(row.id)">
                <template #reference>
                  <el-button link type="danger" size="small" :disabled="isCurrentUser(row)">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
        
        <el-dialog v-model="dialogVisible" :title="dialogTitle" width="90%" style="max-width: 450px;" @close="resetForm">
          <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="form.username" :disabled="isEditMode"></el-input>
            </el-form-item>
            <el-form-item label="密码" :prop="isEditMode ? 'password_optional' : 'password'">
              <el-input v-model="form.password" type="password" :placeholder="isEditMode ? '留空则不修改' : ''"></el-input>
            </el-form-item>
            <el-form-item label="管理员" prop="is_admin">
              <el-switch v-model="form.is_admin"></el-switch>
            </el-form-item>
            <el-form-item label="激活状态" prop="is_active">
              <el-switch v-model="form.is_active"></el-switch>
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" @click="handleSubmit">确定</el-button>
          </template>
        </el-dialog>
      </div>
    </main>
  </div>
</template>
<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import { api } from '../api'
import { ElMessage } from 'element-plus'
import { reportApiError } from '../utils/errorFeedback'
import { Plus } from '@element-plus/icons-vue'
const users = ref([])
const loading = ref(true)
const dialogVisible = ref(false)
const formRef = ref(null)
const currentUser = ref(null)
const form = ref({
  id: null,
  username: '',
  password: '',
  is_admin: false,
  is_active: true
})
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  password_optional: []
}
const isEditMode = computed(() => !!form.value.id)
const dialogTitle = computed(() => (isEditMode.value ? '编辑用户' : '新建用户'))
const formatTime = (value) => {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}
const fetchUsers = async () => {
  loading.value = true
  try {
    const [usersData, meData] = await Promise.all([api.getUsers(), api.getMe()])
    users.value = usersData
    currentUser.value = meData
  } catch (error) {
    if (reportApiError(error, '加载用户列表失败')) return
  } finally {
    loading.value = false
  }
}
const isCurrentUser = (user) => {
  return currentUser.value && currentUser.value.id === user.id
}
const resetForm = () => {
  form.value = {
    id: null,
    username: '',
    password: '',
    is_admin: false,
    is_active: true
  }
  if(formRef.value) {
    formRef.value.resetFields()
  }
}
const openCreateDialog = () => {
  resetForm()
  dialogVisible.value = true
}
const openEditDialog = (user) => {
  resetForm()
  dialogVisible.value = true
  nextTick(() => {
    form.value = { ...user, password: '' }
  })
}
const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      const userData = { ...form.value }
      if (isEditMode.value && !userData.password) {
        delete userData.password
      }
      
      try {
        if (isEditMode.value) {
          await api.updateUser(userData.id, userData)
          ElMessage.success('用户更新成功')
        } else {
          await api.createUser(userData)
          ElMessage.success('用户创建成功')
        }
        dialogVisible.value = false
        await fetchUsers()
      } catch (error) {
        if (reportApiError(error, '操作失败')) return
      }
    }
  })
}
const handleDelete = async (userId) => {
  try {
    await api.deleteUser(userId)
    ElMessage.success('用户删除成功')
    await fetchUsers()
  } catch (error) {
    if (reportApiError(error, '删除失败')) return
  }
}
onMounted(fetchUsers)
</script>
<style scoped>
.el-button--link {
  padding-left: 6px;
  padding-right: 6px;
}
</style>

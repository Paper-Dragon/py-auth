<template>
  <div class="admin-panel">
    <el-container>
      <el-header class="header">
        <div class="header-content">
          <div class="header-title-section">
            <div class="header-icon">
              <el-icon :size="24"><Lock /></el-icon>
            </div>
            <div>
              <h1>授权管理面板</h1>
              <p>设备授权管理系统</p>
            </div>
          </div>
        </div>
        <div class="user-info">
          <el-avatar class="user-avatar" :size="36">
            {{ username.charAt(0).toUpperCase() }}
          </el-avatar>
          <div class="user-details">
            <span class="welcome-text">欢迎回来</span>
            <span class="username-text">{{ username }}</span>
          </div>
          <el-button 
            type="default" 
            @click="showChangePasswordDialog = true"
            class="change-password-button"
            size="large"
          >
            <el-icon><Key /></el-icon>
            修改密码
          </el-button>
          <el-button 
            type="default" 
            @click="$emit('logout')"
            class="logout-button"
            size="large"
          >
            退出登录
          </el-button>
        </div>
      </el-header>
      
      <el-main class="content">
        <div class="stats-cards">
          <el-card class="stat-card" shadow="hover">
            <div class="stat-content">
              <div class="stat-icon total">
                <el-icon :size="32"><Box /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ devices.length }}</div>
                <div class="stat-label">总设备数</div>
              </div>
            </div>
          </el-card>
          <el-card class="stat-card" shadow="hover">
            <div class="stat-content">
              <div class="stat-icon authorized">
                <el-icon :size="32"><CircleCheck /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ authorizedCount }}</div>
                <div class="stat-label">已授权</div>
              </div>
            </div>
          </el-card>
          <el-card class="stat-card" shadow="hover">
            <div class="stat-content">
              <div class="stat-icon unauthorized">
                <el-icon :size="32"><CircleClose /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ unauthorizedCount }}</div>
                <div class="stat-label">未授权</div>
              </div>
            </div>
          </el-card>
        </div>

        <el-card class="table-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="card-title">设备列表</span>
              <el-button 
                type="primary" 
                @click="loadDevices" 
                :loading="loading"
                size="default"
                class="refresh-button"
              >
                <el-icon><Refresh /></el-icon>
                刷新列表
              </el-button>
            </div>
          </template>

          <el-table
            :data="devices"
            :loading="loading"
            stripe
            border
            class="devices-table"
            :default-sort="{ prop: 'created_at', order: 'descending' }"
          >
            <el-table-column prop="device_id" label="设备ID" min-width="250" show-overflow-tooltip>
              <template #default="{ row }">
                <code class="device-id">{{ row.device_id }}</code>
              </template>
            </el-table-column>
            
            <el-table-column prop="software_name" label="软件名称" min-width="100">
              <template #default="{ row }">
                {{ row.software_name || '-' }}
              </template>
            </el-table-column>
            
            <el-table-column prop="device_info" label="设备信息" min-width="100">
              <template #default="{ row }">
                <el-button 
                  type="primary" 
                  link
                  size="small"
                  @click="showDeviceInfo(row)"
                  v-if="row.device_info"
                >
                  查看详情
                </el-button>
                <span v-else>-</span>
              </template>
            </el-table-column>
            
            <el-table-column prop="remark" label="备注" min-width="140">
              <template #default="{ row }">
                <el-input
                  v-model="row._remarkValue"
                  placeholder="备注..."
                  size="small"
                  @keyup.enter="saveRemark(row)"
                  @blur="saveRemark(row)"
                  :loading="row._remarkSaving"
                  :class="{ 'input-error': row._remarkError }"
                />
              </template>
            </el-table-column>
            
            <el-table-column prop="is_authorized" label="状态" min-width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_authorized ? 'success' : 'danger'" size="small">
                  {{ row.is_authorized ? '已授权' : '未授权' }}
                </el-tag>
              </template>
            </el-table-column>
            
            <el-table-column prop="last_check" label="最后检查" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                {{ formatDate(row.last_check) }}
              </template>
            </el-table-column>
            
            <el-table-column prop="created_at" label="创建时间" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            
            <el-table-column label="操作" width="180" fixed="right" align="center">
              <template #default="{ row }">
                <el-button 
                  v-if="row.is_authorized"
                  type="danger" 
                  size="small"
                  @click="toggleAuth(row, false)"
                  :loading="row._updating"
                >
                  取消授权
                </el-button>
                <el-button 
                  v-else
                  type="primary" 
                  size="small"
                  @click="toggleAuth(row, true)"
                  :loading="row._updating"
                >
                  授权
                </el-button>
                
                <el-popconfirm
                  title="确定删除?"
                  @confirm="deleteDevice(row)"
                >
                  <template #reference>
                    <el-button type="danger" size="small" :loading="row._updating">
                      删除
                    </el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- 设备信息弹窗 -->
        <el-dialog
          v-model="deviceInfoModalVisible"
          title="设备详细信息"
          width="600px"
        >
          <el-descriptions :column="1" border v-if="selectedDevice?.device_info">
            <el-descriptions-item 
              v-for="(value, key) in selectedDevice.device_info" 
              :key="key"
              :label="key"
            >
              {{ value ?? '-' }}
            </el-descriptions-item>
          </el-descriptions>
          <el-empty v-else description="暂无设备信息" />
        </el-dialog>

        <!-- 修改密码弹窗 -->
        <el-dialog
          v-model="showChangePasswordDialog"
          title="修改密码"
          width="500px"
          @close="resetPasswordForm"
        >
          <el-form
            ref="passwordFormRef"
            :model="passwordForm"
            :rules="passwordRules"
            label-width="100px"
          >
            <el-form-item label="旧密码" prop="oldPassword">
              <el-input
                v-model="passwordForm.oldPassword"
                type="password"
                placeholder="请输入旧密码"
                show-password
                @keyup.enter="handleChangePassword"
              />
            </el-form-item>
            <el-form-item label="新密码" prop="newPassword">
              <el-input
                v-model="passwordForm.newPassword"
                type="password"
                placeholder="请输入新密码"
                show-password
                @keyup.enter="handleChangePassword"
              />
            </el-form-item>
            <el-form-item label="确认密码" prop="confirmPassword">
              <el-input
                v-model="passwordForm.confirmPassword"
                type="password"
                placeholder="请再次输入新密码"
                show-password
                @keyup.enter="handleChangePassword"
              />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showChangePasswordDialog = false">取消</el-button>
            <el-button 
              type="primary" 
              @click="handleChangePassword"
              :loading="changingPassword"
            >
              确认修改
            </el-button>
          </template>
        </el-dialog>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { 
  Lock,
  Refresh,
  Box,
  CircleCheck,
  CircleClose,
  Key
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

defineProps({
  username: String
})

const emit = defineEmits(['logout'])

const devices = ref([])
const loading = ref(false)
const deviceInfoModalVisible = ref(false)
const selectedDevice = ref(null)
const showChangePasswordDialog = ref(false)
const changingPassword = ref(false)
const passwordFormRef = ref(null)
const passwordForm = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})
let refreshTimer = null

const authorizedCount = computed(() => 
  devices.value.filter(d => d.is_authorized).length
)

const unauthorizedCount = computed(() => 
  devices.value.filter(d => !d.is_authorized).length
)

const loadDevices = async () => {
  loading.value = true

  try {
    const data = await api.getDevices()
    devices.value = data.map(d => ({
      ...d,
      _originalRemark: d.remark || '',
      _remarkValue: d.remark || '',
      _remarkSaving: false,
      _remarkError: false,
      _updating: false
    }))
  } catch (e) {
    if (e.message.includes('登录已过期') || e.message.includes('401')) {
      emit('logout')
      return
    }
    ElMessage.error(e.message || '加载设备列表失败')
  } finally {
    loading.value = false
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return '从未'
  try {
    return new Date(dateStr).toLocaleString('zh-CN')
  } catch {
    return dateStr
  }
}

const showDeviceInfo = (device) => {
  selectedDevice.value = device
  deviceInfoModalVisible.value = true
}

const saveRemark = async (device) => {
  if (device._remarkValue === device._originalRemark) return

  device._remarkSaving = true
  device._remarkError = false

  try {
    await api.updateDevice(device.device_id, { remark: device._remarkValue })
    device.remark = device._remarkValue
    device._originalRemark = device._remarkValue
    ElMessage.success('备注保存成功')
  } catch (e) {
    device._remarkValue = device._originalRemark
    device._remarkError = true
    if (e.message.includes('登录已过期')) {
      emit('logout')
    } else {
      ElMessage.error(e.message || '保存失败')
    }
  } finally {
    device._remarkSaving = false
  }
}

const toggleAuth = async (device, authorize) => {
  device._updating = true
  try {
    await api.updateDevice(device.device_id, { is_authorized: authorize })
    device.is_authorized = authorize
    ElMessage.success(authorize ? '设备已授权' : '已取消授权')
  } catch (e) {
    if (e.message.includes('登录已过期')) {
      emit('logout')
    } else {
      ElMessage.error(e.message || '操作失败')
    }
  } finally {
    device._updating = false
  }
}


const deleteDevice = async (device) => {
  device._updating = true
  try {
    await api.deleteDevice(device.device_id)
    devices.value = devices.value.filter(d => d.device_id !== device.device_id)
    ElMessage.success('设备已删除')
  } catch (e) {
    if (e.message.includes('登录已过期')) {
      emit('logout')
    } else {
      ElMessage.error(e.message || '删除失败')
    }
  } finally {
    device._updating = false
  }
}

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== passwordForm.value.newPassword) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const passwordRules = {
  oldPassword: [
    { required: true, message: '请输入旧密码', trigger: 'blur' }
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const resetPasswordForm = () => {
  passwordForm.value = {
    oldPassword: '',
    newPassword: '',
    confirmPassword: ''
  }
  if (passwordFormRef.value) {
    passwordFormRef.value.clearValidate()
  }
}

const handleChangePassword = async () => {
  if (!passwordFormRef.value) return
  
  try {
    await passwordFormRef.value.validate()
    
    if (passwordForm.value.oldPassword === passwordForm.value.newPassword) {
      ElMessage.warning('新密码不能与旧密码相同')
      return
    }
    
    changingPassword.value = true
    await api.changePassword(
      passwordForm.value.oldPassword,
      passwordForm.value.newPassword
    )
    ElMessage.success('密码修改成功')
    showChangePasswordDialog.value = false
    resetPasswordForm()
  } catch (e) {
    if (e.message.includes('登录已过期')) {
      emit('logout')
    } else {
      ElMessage.error(e.message || '密码修改失败')
    }
  } finally {
    changingPassword.value = false
  }
}

onMounted(() => {
  loadDevices()
  refreshTimer = setInterval(() => {
    if (!loading.value) {
      loadDevices()
    }
  }, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped>
.admin-panel {
  min-height: 100vh;
  background: #f5f7fa;
}

.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 0 40px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 80px !important;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.header-content {
  display: flex;
  align-items: center;
}

.header-title-section {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  backdrop-filter: blur(10px);
}

.header-title-section h1 {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 4px;
  color: white;
}

.header-title-section p {
  font-size: 14px;
  opacity: 0.9;
  margin: 0;
  color: white;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 16px;
  color: white;
}

.user-avatar {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  font-weight: 600;
}

.user-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.welcome-text {
  font-size: 12px;
  opacity: 0.8;
}

.username-text {
  font-size: 14px;
  font-weight: 600;
}

.change-password-button {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.3);
  color: white;
  backdrop-filter: blur(10px);
  margin-right: 8px;
}

.change-password-button:hover {
  background: rgba(255, 255, 255, 0.3);
  border-color: rgba(255, 255, 255, 0.4);
  color: white;
}

.logout-button {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.3);
  color: white;
  backdrop-filter: blur(10px);
}

.logout-button:hover {
  background: rgba(255, 255, 255, 0.3);
  border-color: rgba(255, 255, 255, 0.4);
  color: white;
}

.content {
  padding: 24px;
  max-width: 1600px;
  margin: 0 auto;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 20px;
  margin-bottom: 24px;
}

.stat-card {
  border-radius: 12px;
  transition: all 0.3s;
  border: none;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: white;
}

.stat-icon.total {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.stat-icon.authorized {
  background: linear-gradient(135deg, #56ab2f 0%, #a8e063 100%);
}

.stat-icon.unauthorized {
  background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #303133;
  line-height: 1;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.table-card {
  border-radius: 12px;
  border: none;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.refresh-button {
  border-radius: 8px;
}

.devices-table {
  border-radius: 8px;
  overflow: hidden;
}

.device-id {
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  color: #606266;
  background: #f5f7fa;
  padding: 4px 8px;
  border-radius: 4px;
  display: inline-block;
}


.input-error :deep(.el-input__wrapper) {
  border-color: #f56c6c;
}

:deep(.el-card__header) {
  padding: 20px 24px;
  border-bottom: 1px solid #ebeef5;
}

:deep(.el-card__body) {
  padding: 24px;
}

:deep(.el-table) {
  border-radius: 8px;
}

:deep(.el-table th) {
  background: #fafafa;
  font-weight: 600;
  color: #303133;
}

:deep(.el-table--border) {
  border: 1px solid #ebeef5;
}

:deep(.el-table--border::after) {
  background-color: #ebeef5;
}

:deep(.el-table--border::before) {
  background-color: #ebeef5;
}

@media (max-width: 768px) {
  .header {
    padding: 0 20px;
    flex-direction: column;
    height: auto !important;
    padding: 16px 20px;
    gap: 16px;
  }

  .header-content {
    width: 100%;
  }

  .user-info {
    width: 100%;
    justify-content: space-between;
  }

  .content {
    padding: 16px;
  }

  .stats-cards {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .refresh-button {
    width: 100%;
  }
}
</style>

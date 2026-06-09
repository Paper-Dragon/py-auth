<template>
  <div class="page-container">
    <main class="page-content page-content-narrow">
      <div class="card">
        <div class="config-header">
          <h2>系统配置</h2>
        </div>

        <div v-if="loading" class="loading-state">
          <el-icon class="is-loading" :size="20"><Refresh /></el-icon>
          <span>加载中...</span>
        </div>

        <div v-else class="settings-sections">
          <section class="settings-section">
            <h3 class="section-title">接口限速</h3>
            <el-form label-width="140px" label-position="left">
              <el-form-item label="启用速率限制">
                <el-switch v-model="rateLimit.enabled" />
              </el-form-item>
              <el-form-item label="限制规则">
                <el-table
                  :data="rateLimitRules"
                  row-key="scope"
                  stripe
                  border
                  size="small"
                  class="admin-data-table rate-limit-table"
                >
                  <el-table-column prop="label" label="接口" width="120" />
                  <el-table-column label="窗口(秒)" width="130">
                    <template #default="{ row }">
                      <el-input-number
                        v-model="rateLimit[row.scope].window_seconds"
                        :min="1"
                        :max="3600"
                        :disabled="!rateLimit.enabled"
                        controls-position="right"
                        size="small"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column label="最大次数" width="130">
                    <template #default="{ row }">
                      <el-input-number
                        v-model="rateLimit[row.scope].max_requests"
                        :min="1"
                        :max="10000"
                        :disabled="!rateLimit.enabled"
                        controls-position="right"
                        size="small"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column prop="hint" label="说明" min-width="160" />
                </el-table>
              </el-form-item>
            </el-form>
          </section>

          <section v-if="isAdmin" class="settings-section">
            <h3 class="section-title">维护</h3>
            <div class="cleanup-block">
              <h4>审计日志清理</h4>
              <div class="cleanup-actions">
                <el-input-number v-model="cleanupDays" :min="0" :max="3650" controls-position="right" />
                <el-button type="warning" :loading="cleaning" @click="cleanupOldLogs">
                  {{ cleanupDays === 0 ? '全部清空' : `清空 ${cleanupDays} 天前` }}
                </el-button>
              </div>
            </div>
          </section>

          <div class="settings-footer">
            <el-button type="primary" @click="saveSystemConfig" :loading="savingSystem">保存限速配置</el-button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { reportApiError } from '../utils/errorFeedback'
import { Refresh } from '@element-plus/icons-vue'

const defaultRateLimit = {
  enabled: true,
  login: { max_requests: 10, window_seconds: 60 },
  heartbeat: { max_requests: 120, window_seconds: 60 },
  payment_order: { max_requests: 20, window_seconds: 60 },
}

const rateLimitRules = [
  { scope: 'login', label: '登录', hint: '防暴力破解' },
  { scope: 'heartbeat', label: '心跳', hint: '限制单 IP 频率' },
  { scope: 'payment_order', label: '公开下单', hint: '限制支付页下单' },
]

const loading = ref(true)
const isAdmin = ref(false)
const savingSystem = ref(false)
const cleaning = ref(false)
const cleanupDays = ref(30)
const rateLimit = ref(structuredClone(defaultRateLimit))

const mergeRateLimit = (raw) => {
  const next = structuredClone(defaultRateLimit)
  if (!raw || typeof raw !== 'object') return next
  next.enabled = !!raw.enabled
  for (const scope of ['login', 'heartbeat', 'payment_order']) {
    if (raw[scope] && typeof raw[scope] === 'object') {
      next[scope] = { ...next[scope], ...raw[scope] }
    }
  }
  return next
}

const loadSystemConfig = async () => {
  const data = await api.getConfigs()
  if (data && typeof data === 'object') {
    rateLimit.value = mergeRateLimit(data.rate_limit)
  }
}

const loadAll = async () => {
  loading.value = true
  try {
    const me = await api.getMe()
    isAdmin.value = !!me?.is_admin
    localStorage.setItem('isAdmin', me?.is_admin ? '1' : '0')
    await loadSystemConfig()
  } catch (error) {
    if (reportApiError(error, '加载配置失败')) return
  } finally {
    loading.value = false
  }
}

const saveSystemConfig = async () => {
  savingSystem.value = true
  try {
    const payload = { rate_limit: rateLimit.value }
    await api.updateConfigs(payload)
    ElMessage.success('配置已保存')
  } catch (e) {
    if (reportApiError(e, '保存失败')) return
  } finally {
    savingSystem.value = false
  }
}

const cleanupOldLogs = async () => {
  const isClearAll = cleanupDays.value === 0
  try {
    await ElMessageBox.confirm(
      isClearAll ? '将清空全部审计日志且不可恢复，是否继续？' : `将删除 ${cleanupDays.value} 天前的审计日志，是否继续？`,
      isClearAll ? '高风险操作确认' : '确认清理',
      { type: isClearAll ? 'error' : 'warning' }
    )
  } catch {
    return
  }
  cleaning.value = true
  try {
    const result = await api.cleanupOperationLogs(cleanupDays.value)
    ElMessage.success(`已处理 ${result.deleted_count || 0} 条日志`)
  } catch (e) {
    if (reportApiError(e, '操作失败')) return
  } finally {
    cleaning.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.config-header h2 {
  margin: 0;
  font-size: 18px;
}

.config-header p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-text-tertiary);
}

.settings-sections {
  margin-top: 8px;
}

.settings-section {
  padding: 20px 0;
  border-bottom: 1px solid var(--color-border);
}

.settings-section:first-child {
  padding-top: 8px;
}

.settings-section:last-of-type {
  border-bottom: none;
}

.section-title {
  margin: 0 0 16px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.settings-footer {
  margin-top: 8px;
  padding-top: 16px;
}

.form-item-help {
  color: #909399;
  font-size: 12px;
  margin: 4px 0 0;
  line-height: 1.5;
}

.rate-limit-table {
  width: 100%;
}

.cleanup-block h4 {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.cleanup-block p {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--color-text-tertiary);
}

.cleanup-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.loading-state {
  padding: 40px;
  text-align: center;
  color: #909399;
  display: flex;
  justify-content: center;
  gap: 8px;
}
</style>

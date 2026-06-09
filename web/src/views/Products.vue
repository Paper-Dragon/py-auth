<template>
  <div class="page-container">
    <main class="page-content">
      <div class="card">
        <div class="card-header">
          <div class="header-meta">
            <h2>产品列表</h2>
          </div>
          <div class="header-actions">
            <el-button type="primary" @click="openCreateDialog">
              <el-icon><Plus /></el-icon>
              <span>新建产品</span>
            </el-button>
          </div>
        </div>

        <el-table
          :data="products"
          v-loading="loading"
          row-key="id"
          stripe
          border
          class="admin-data-table"
          empty-text="暂无产品"
        >
          <el-table-column label="软件名称" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <span>{{ productNameLabel(row) }}</span>
              <el-tag v-if="row.is_default" size="small" type="info" style="margin-left: 6px">默认</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="UUID" min-width="180" class-name="mono-cell">
            <template #default="{ row }">
              <span
                class="mono-text uuid-cell"
                @click="toggleUuid(row.id)"
              >
                {{ expandedUuidIds.has(row.id) ? row.key : maskUuid(row.key) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="Client Secret" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="secret-cell">
                <template v-if="row.client_secret_configured">
                  <span class="mono-text">{{ maskSecret(row.client_secret) }}</span>
                  <el-button link type="primary" size="small" @click="copyText(row.client_secret)">复制</el-button>
                </template>
                <el-tag v-else size="small" type="warning">未配置</el-tag>
                <el-tag v-if="row.is_default" size="small" type="info">环境变量</el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="授权模式" min-width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="authModeTagType(row.auth_mode)" size="small">
                {{ authModeLabel(row.auth_mode) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="授权配置" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ formatConfigSummary(row) }}</template>
          </el-table-column>
          <el-table-column prop="device_count" label="设备数" min-width="72" align="center" />
          <el-table-column label="状态" min-width="72" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                {{ row.is_active ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" min-width="160">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" min-width="108" align="center">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openEditDialog(row)">编辑</el-button>
              <el-popconfirm
                v-if="!row.is_default"
                title="确定删除此产品？"
                @confirm="handleDelete(row.id)"
              >
                <template #reference>
                  <el-button link type="danger" size="small">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>

        <el-dialog
          v-model="dialogVisible"
          :title="dialogTitle"
          width="90%"
          style="max-width: 520px;"
          @close="resetForm"
        >
          <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
            <el-form-item :label="form.is_default ? '显示名称' : '软件名称'" prop="software_name">
              <el-input
                v-model="form.software_name"
                :disabled="form.is_default"
                :placeholder="form.is_default ? '未登记产品（默认）' : '例如：绘图工具 Pro'"
              />
            </el-form-item>
            <el-form-item label="UUID" prop="key">
              <el-input
                v-model="form.key"
                disabled
                placeholder="自动生成 UUID"
                class="key-readonly"
              />
            </el-form-item>
            <el-form-item v-if="isEditMode" label="Client Secret">
              <div class="key-input-row">
                <el-input v-model="form.client_secret" readonly class="key-readonly" />
                <el-button :disabled="!form.client_secret" @click="copyText(form.client_secret)">复制</el-button>
              </div>
            </el-form-item>
            <el-form-item label="授权模式" prop="auth_mode">
              <el-select v-model="form.auth_mode" style="width: 100%" @change="onAuthModeChange">
                <el-option
                  v-for="item in authModeOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item v-if="form.auth_mode === 'trial'" label="试用天数" prop="trial_days">
              <el-input-number v-model="form.trial_days" :min="1" :max="3650" controls-position="right" />
            </el-form-item>
            <template v-if="form.auth_mode === 'paid' || form.auth_mode === 'hybrid'">
              <el-form-item label="付费档位" prop="plan_on_paid">
                <el-input v-model="form.plan_on_paid" placeholder="例如：pro" />
              </el-form-item>
              <el-form-item label="价格(元)" prop="price">
                <el-input v-model="form.price" placeholder="例如：29.00" />
              </el-form-item>
              <el-form-item label="支付方式" prop="pay_type">
                <el-select v-model="form.pay_type" style="width: 100%">
                  <el-option
                    v-for="item in payChannelOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </el-form-item>
            </template>
            <el-form-item label="启用状态" prop="is_active">
              <el-switch v-model="form.is_active" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
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
import { PAY_CHANNELS } from '../constants/payChannels'

const authModeOptions = [
  { value: 'open', label: '开放' },
  { value: 'manual', label: '手动审核' },
  { value: 'trial', label: '试用' },
  { value: 'paid', label: '付费' },
  { value: 'hybrid', label: '免费+付费' },
]

const authModeLabels = Object.fromEntries(authModeOptions.map((item) => [item.value, item.label]))

const payChannelOptions = PAY_CHANNELS

const products = ref([])
const expandedUuidIds = ref(new Set())
const loading = ref(true)
const submitting = ref(false)
const dialogVisible = ref(false)
const formRef = ref(null)
const form = ref({
  id: null,
  key: '',
  software_name: '',
  auth_mode: 'open',
  trial_days: 7,
  plan_on_paid: 'pro',
  price: '0.00',
  pay_type: 'wxpay',
  is_active: true,
  is_default: false,
  client_secret: '',
})

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const legacyKeyPattern = /^prod_[a-zA-Z0-9_-]+$/

const rules = {
  software_name: [
    { required: true, message: '请输入软件名称', trigger: 'blur' },
    {
      validator: (_, value, callback) => {
        const text = String(value || '').trim()
        if (!text) {
          callback(new Error('请输入软件名称'))
          return
        }
        if (text.length < 2 || text.length > 64) {
          callback(new Error('软件名称须为 2~64 个字符'))
          return
        }
        if (uuidPattern.test(text)) {
          callback(new Error('软件名称不能使用 UUID 格式'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
  key: [
    { required: true, message: 'UUID 未生成', trigger: 'blur' },
    {
      validator: (_, value, callback) => {
        if (!value || uuidPattern.test(value) || legacyKeyPattern.test(value)) callback()
        else callback(new Error('UUID 格式不正确'))
      },
      trigger: 'blur',
    },
  ],
  auth_mode: [{ required: true, message: '请选择授权模式', trigger: 'change' }],
  trial_days: [{ required: true, message: '请设置试用天数', trigger: 'change' }],
  plan_on_paid: [{ required: true, message: '请填写付费档位', trigger: 'blur' }],
  price: [{ required: true, message: '请填写价格', trigger: 'blur' }],
}

const isEditMode = computed(() => !!form.value.id)
const dialogTitle = computed(() => {
  if (form.value.is_default) return '编辑默认产品'
  return isEditMode.value ? '编辑产品' : '新建产品'
})

const productNameLabel = (row) => {
  if (row.is_default) return row.display_name || '未登记产品（默认）'
  return row.software_name || row.display_name || '-'
}

const formatTime = (value) => {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

const authModeLabel = (mode) => authModeLabels[mode] || mode

const authModeTagType = (mode) => {
  const map = {
    open: 'success',
    manual: 'warning',
    trial: '',
    paid: 'danger',
    hybrid: 'info',
  }
  return map[mode] || 'info'
}

const formatConfigSummary = (row) => {
  const config = row.config || {}
  if (row.auth_mode === 'trial') {
    return `试用 ${config.trial_days ?? 7} 天`
  }
  if (row.auth_mode === 'paid' || row.auth_mode === 'hybrid') {
    const price = config.price ?? '0.00'
    const plan = config.plan_on_paid ?? 'pro'
    const pay = config.pay_type ?? 'wxpay'
    return `¥${price} → ${plan} · ${pay}`
  }
  return '-'
}

const buildConfigPayload = () => {
  const mode = form.value.auth_mode
  if (mode === 'trial') {
    return { trial_days: form.value.trial_days }
  }
  if (mode === 'paid' || mode === 'hybrid') {
    return {
      plan_on_paid: form.value.plan_on_paid,
      price: form.value.price,
      pay_type: form.value.pay_type,
    }
  }
  return {}
}

const fillFormFromProduct = (product) => {
  const config = product.config || {}
  form.value = {
    id: product.id,
    key: product.key,
    software_name: product.is_default
      ? (product.display_name || '未登记产品（默认）')
      : (product.software_name || product.display_name || ''),
    auth_mode: product.auth_mode,
    trial_days: config.trial_days ?? 7,
    plan_on_paid: config.plan_on_paid ?? 'pro',
    price: config.price ?? '0.00',
    pay_type: config.pay_type ?? 'wxpay',
    is_active: product.is_active,
    is_default: !!product.is_default,
    client_secret: product.client_secret || '',
  }
}

const fetchProducts = async () => {
  loading.value = true
  try {
    products.value = await api.getProducts()
  } catch (error) {
    if (reportApiError(error, '加载产品列表失败')) return
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  form.value = {
    id: null,
    key: '',
    software_name: '',
    auth_mode: 'open',
    trial_days: 7,
    plan_on_paid: 'pro',
    price: '0.00',
    pay_type: 'wxpay',
    is_active: true,
    is_default: false,
    client_secret: '',
  }
  if (formRef.value) {
    formRef.value.resetFields()
  }
}

const onAuthModeChange = () => {
  if (form.value.auth_mode === 'trial' && !form.value.trial_days) {
    form.value.trial_days = 7
  }
  if ((form.value.auth_mode === 'paid' || form.value.auth_mode === 'hybrid') && !form.value.plan_on_paid) {
    form.value.plan_on_paid = 'pro'
  }
}

const createProductKey = () => crypto.randomUUID()

const openCreateDialog = () => {
  resetForm()
  form.value.key = createProductKey()
  dialogVisible.value = true
}

const openEditDialog = (product) => {
  resetForm()
  dialogVisible.value = true
  nextTick(() => {
    fillFormFromProduct(product)
  })
}

const maskUuid = (uuid) => {
  const value = String(uuid || '')
  if (value.length <= 14) return value
  return `${value.slice(0, 8)}…${value.slice(-5)}`
}

const toggleUuid = (id) => {
  const next = new Set(expandedUuidIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedUuidIds.value = next
}

const maskSecret = (secret) => {
  const value = String(secret || '')
  if (value.length <= 10) return value
  return `${value.slice(0, 6)}…${value.slice(-4)}`
}

const copyText = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    const name = form.value.software_name.trim()
    const payload = {
      software_name: form.value.is_default ? undefined : name,
      display_name: name,
      auth_mode: form.value.auth_mode,
      config: buildConfigPayload(),
      is_active: form.value.is_active,
    }
    try {
      if (isEditMode.value) {
        await api.updateProduct(form.value.id, payload)
        ElMessage.success('产品配置已更新')
      } else {
        await api.createProduct({ ...payload, key: form.value.key || undefined })
        ElMessage.success('产品已创建，可在列表中复制 Client Secret')
      }
      dialogVisible.value = false
      await fetchProducts()
    } catch (error) {
      if (reportApiError(error, '操作失败')) return
    } finally {
      submitting.value = false
    }
  })
}

const handleDelete = async (productId) => {
  try {
    await api.deleteProduct(productId)
    ElMessage.success('产品已删除')
    await fetchProducts()
  } catch (error) {
    if (reportApiError(error, '删除失败')) return
  }
}

onMounted(fetchProducts)
</script>

<style scoped>
.uuid-cell {
  cursor: pointer;
}

.uuid-cell:hover {
  color: var(--color-primary);
}

.secret-cell {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 6px;
}

.key-input-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.key-input-row .el-input {
  flex: 1;
}

.key-readonly :deep(.el-input__wrapper) {
  background-color: var(--color-bg-secondary);
}

.key-readonly :deep(.el-input__inner) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: var(--color-text-secondary);
  -webkit-text-fill-color: var(--color-text-secondary);
}
</style>

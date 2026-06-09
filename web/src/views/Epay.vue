<template>
  <div class="page-container">
    <main class="page-content">
      <div class="card">
        <div class="card-header">
          <div class="header-meta">
            <h2>易支付</h2>
          </div>
          <div class="header-actions">
            <el-tag :type="epayForm.enabled ? 'success' : 'info'" size="large">
              {{ epayForm.enabled ? '已启用' : '未启用' }}
            </el-tag>
            <el-button @click="openPayPage">打开支付页</el-button>
            <el-button type="primary" link @click="goOrders">订单管理</el-button>
          </div>
        </div>

        <div v-if="loading" class="loading-state">
          <el-icon class="is-loading" :size="20"><Refresh /></el-icon>
          <span>加载中...</span>
        </div>

        <template v-else>
          <el-form
            :model="epayForm"
            :rules="epayRules"
            ref="epayFormRef"
            label-width="140px"
            label-position="left"
            @submit.prevent="saveEpayConfig"
          >
            <section class="section-block">
              <div class="section-title">
                <h3>基础配置</h3>
              </div>
              <el-form-item label="启用易支付" prop="enabled">
                <el-switch v-model="epayForm.enabled" />
              </el-form-item>
              <el-form-item label="接口地址" prop="api_url">
                <el-input v-model="epayForm.api_url" placeholder="https://pay.example.com" />
              </el-form-item>
              <el-form-item label="商户 ID" prop="pid">
                <el-input v-model="epayForm.pid" placeholder="商户 PID" />
              </el-form-item>
              <el-form-item label="商户密钥" prop="key">
                <el-input
                  v-model="epayForm.key"
                  type="password"
                  show-password
                  :placeholder="epayForm.key_configured ? '留空则保持原密钥' : '请输入商户密钥'"
                />
              </el-form-item>
            </section>

            <section class="section-block">
              <div class="section-title">
                <h3>支付渠道</h3>
              </div>
              <div class="channel-grid">
                <div
                  v-for="channel in PAY_CHANNELS"
                  :key="channel.value"
                  class="channel-card"
                  :class="{ active: isChannelEnabled(channel.value) }"
                >
                  <div class="channel-card-head">
                    <span class="channel-name">{{ channel.label }}</span>
                    <el-switch
                      :model-value="isChannelEnabled(channel.value)"
                      @change="(val) => toggleChannel(channel.value, val)"
                    />
                  </div>
                  <p class="channel-desc">{{ channel.description }}</p>
                </div>
              </div>
              <el-alert
                v-if="epayForm.enabled && enabledChannelCount === 0"
                type="error"
                :closable="false"
                show-icon
                title="启用易支付时须至少开通一种支付渠道"
                style="margin-top: 12px"
              />
            </section>

            <section class="section-block">
              <div class="section-title">
                <h3>回调与参数</h3>
              </div>
              <el-form-item label="下单方式">
                <el-select v-model="epayForm.order_mode" style="width: 100%">
                  <el-option label="API 接口（MAPI）" value="mapi" />
                  <el-option label="页面跳转（submit）" value="submit" />
                </el-select>
                <p class="form-item-help">
                  {{ epayForm.order_mode === 'submit'
                    ? '提交表单跳转至易支付收银台完成支付'
                    : '调用 MAPI 接口下单，返回支付链接/二维码后跳转' }}
                </p>
              </el-form-item>
              <el-form-item label="网站名称">
                <el-input v-model="epayForm.sitename" placeholder="可选" />
              </el-form-item>
              <el-form-item label="异步通知">
                <el-input v-model="epayForm.notify_url" placeholder="留空则自动生成" />
                <p class="form-item-help resolved-url">
                  实际回调：{{ epayForm.resolved_notify_url || '保存后根据公网地址生成' }}
                </p>
              </el-form-item>
              <el-form-item label="同步跳转">
                <el-input v-model="epayForm.return_url" placeholder="留空则自动生成 /pay/result" />
                <p class="form-item-help resolved-url">
                  实际跳转：{{ epayForm.resolved_return_url || '保存后根据公网地址生成' }}
                </p>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="saveEpayConfig" :loading="saving">保存配置</el-button>
                <el-button @click="copyText(epayForm.resolved_notify_url)">复制回调地址</el-button>
              </el-form-item>
              <p class="form-item-help resolved-url">
                支付页：{{ epayForm.resolved_pay_url || '请配置 PUBLIC_BASE_URL 或同步跳转地址' }}
              </p>
            </section>

            <section class="section-block">
              <div class="section-title">
                <h3>连接测试</h3>
              </div>
              <div class="test-actions">
                <el-select v-model="testPayType" style="width: 140px" placeholder="支付渠道">
                  <el-option
                    v-for="item in enabledChannelOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
                <el-button
                  @click="runTestConnection"
                  :loading="testingConnection"
                  :disabled="!testPayType"
                >
                  测试连接
                </el-button>
                <el-input v-model="testPayMoney" style="width: 100px" placeholder="0.01" />
                <el-button
                  type="warning"
                  @click="runTestPayment"
                  :loading="testingPayment"
                  :disabled="!enabledChannelOptions.length"
                >
                  测试支付
                </el-button>
              </div>
              <p
                v-if="testConnectionMessage"
                class="form-item-help"
                :class="{ 'test-success': testConnectionOk, 'test-fail': !testConnectionOk }"
              >
                {{ testConnectionMessage }}
              </p>
            </section>
          </el-form>
        </template>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { reportApiError } from '../utils/errorFeedback'
import { Refresh } from '@element-plus/icons-vue'
import { redirectToEpayOrder } from '../utils/epayPay'
import { PAY_CHANNELS } from '../constants/payChannels'
const router = useRouter()
const loading = ref(true)
const saving = ref(false)
const epayFormRef = ref(null)

const epayForm = ref({
  enabled: false,
  api_url: '',
  pid: '',
  key: '',
  key_configured: false,
  notify_url: '',
  return_url: '',
  order_mode: 'mapi',
  sitename: '',
  enabled_channels: ['alipay', 'wxpay', 'qqpay'],
  resolved_notify_url: '',
  resolved_return_url: '',
  resolved_pay_url: '',
})

const testingConnection = ref(false)
const testingPayment = ref(false)
const testPayType = ref('alipay')
const testPayMoney = ref('0.01')
const testConnectionMessage = ref('')
const testConnectionOk = ref(false)

const enabledChannelOptions = computed(() =>
  PAY_CHANNELS.filter((item) => epayForm.value.enabled_channels.includes(item.value))
)

const enabledChannelCount = computed(() => epayForm.value.enabled_channels.length)

const epayRules = {
  api_url: [{
    validator: (_, value, callback) => {
      if (!epayForm.value.enabled || (value && value.trim())) callback()
      else callback(new Error('启用时须填写接口地址'))
    },
    trigger: 'blur',
  }],
  pid: [{
    validator: (_, value, callback) => {
      if (!epayForm.value.enabled || (value && value.trim())) callback()
      else callback(new Error('启用时须填写商户 ID'))
    },
    trigger: 'blur',
  }],
}

const isChannelEnabled = (value) => epayForm.value.enabled_channels.includes(value)

const toggleChannel = (value, enabled) => {
  const current = [...epayForm.value.enabled_channels]
  if (enabled) {
    if (!current.includes(value)) current.push(value)
  } else {
    const idx = current.indexOf(value)
    if (idx >= 0) current.splice(idx, 1)
  }
  epayForm.value.enabled_channels = current
}

const syncTestPayType = () => {
  if (!enabledChannelOptions.value.length) {
    testPayType.value = ''
    return
  }
  if (!enabledChannelOptions.value.some((item) => item.value === testPayType.value)) {
    testPayType.value = enabledChannelOptions.value[0].value
  }
}

const fillEpayForm = (data) => {
  epayForm.value = {
    enabled: !!data.enabled,
    api_url: data.api_url || '',
    pid: data.pid || '',
    key: data.key || '',
    key_configured: !!data.key_configured,
    notify_url: data.notify_url || '',
    return_url: data.return_url || '',
    order_mode: data.order_mode || 'mapi',
    sitename: data.sitename || '',
    enabled_channels: Array.isArray(data.enabled_channels)
      ? [...data.enabled_channels]
      : ['alipay', 'wxpay', 'qqpay'],
    resolved_notify_url: data.resolved_notify_url || '',
    resolved_return_url: data.resolved_return_url || '',
    resolved_pay_url: data.resolved_pay_url || '',
  }
  syncTestPayType()
}

const loadEpayConfig = async () => {
  const data = await api.getEpayConfig()
  fillEpayForm(data)
}

const buildPayload = () => {
  const payload = {
    enabled: epayForm.value.enabled,
    api_url: epayForm.value.api_url,
    pid: epayForm.value.pid,
    notify_url: epayForm.value.notify_url,
    return_url: epayForm.value.return_url,
    order_mode: epayForm.value.order_mode,
    sitename: epayForm.value.sitename,
    enabled_channels: epayForm.value.enabled_channels,
  }
  if (epayForm.value.key) {
    payload.key = epayForm.value.key
  }
  return payload
}

const saveEpayConfig = async () => {
  if (!epayFormRef.value) return
  if (epayForm.value.enabled && !epayForm.value.enabled_channels.length) {
    ElMessage.error('启用易支付时须至少开通一种支付渠道')
    return
  }
  await epayFormRef.value.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try {
      const data = await api.updateEpayConfig(buildPayload())
      fillEpayForm(data)
      ElMessage.success('易支付配置已保存')
    } catch (error) {
      if (reportApiError(error, '保存失败')) return
    } finally {
      saving.value = false
    }
  })
}

const persistEpayConfig = async () => {
  if (!epayFormRef.value) return false
  if (epayForm.value.enabled && !epayForm.value.enabled_channels.length) {
    ElMessage.error('启用易支付时须至少开通一种支付渠道')
    return false
  }
  let saved = false
  await epayFormRef.value.validate(async (valid) => {
    if (!valid) return
    const data = await api.updateEpayConfig(buildPayload())
    fillEpayForm(data)
    saved = true
  })
  return saved
}

const copyText = async (text) => {
  if (!text) {
    ElMessage.warning('暂无可复制的地址')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

const openPayPage = () => {
  const url = epayForm.value.resolved_pay_url
  if (!url) {
    ElMessage.warning('请先配置 PUBLIC_BASE_URL 或填写同步跳转地址')
    return
  }
  window.open(url, '_blank')
}

const goOrders = () => {
  router.push('/orders')
}

const runTestConnection = async () => {
  if (!testPayType.value) {
    ElMessage.warning('请先选择支付渠道')
    return
  }
  testingConnection.value = true
  testConnectionMessage.value = ''
  try {
    const saved = await persistEpayConfig()
    if (!saved) return
    const result = await api.testEpayConnection({ pay_type: testPayType.value })
    testConnectionOk.value = !!result.success
    testConnectionMessage.value = result.message
    if (result.success) ElMessage.success(result.message)
    else ElMessage.error(result.message)
  } catch (error) {
    testConnectionOk.value = false
    testConnectionMessage.value = error.message || '测试连接失败'
    if (reportApiError(error, '测试连接失败')) return
  } finally {
    testingConnection.value = false
  }
}

const runTestPayment = async () => {
  if (!testPayType.value) {
    ElMessage.warning('请先开通至少一种支付渠道')
    return
  }
  testingPayment.value = true
  try {
    const saved = await persistEpayConfig()
    if (!saved) return
    const order = await api.testEpayPayment({
      pay_type: testPayType.value,
      money: testPayMoney.value || '0.01',
    })
    if (order.pay_mode === 'qrcode' && order.qr_image) {
      await ElMessageBox.alert(
        `<div style="text-align:center"><img src="${order.qr_image}" alt="支付二维码" style="width:220px;height:220px" /><p style="margin-top:8px">请使用对应客户端扫码（金额 ¥${order.money}）</p></div>`,
        '扫码支付测试',
        { dangerouslyUseHTMLString: true, confirmButtonText: '关闭' },
      )
      return
    }
    redirectToEpayOrder(order)
  } catch (error) {
    if (reportApiError(error, '测试支付失败')) return
  } finally {
    testingPayment.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    await loadEpayConfig()
  } catch (error) {
    if (reportApiError(error, '加载易支付配置失败')) return
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}

.header-meta h2 {
  margin: 0;
  font-size: 18px;
  color: var(--color-text-primary);
}

.header-meta p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-text-tertiary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.section-block {
  margin-bottom: 28px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}

.section-block:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.section-title {
  margin-bottom: 16px;
}

.section-title h3 {
  margin: 0;
  font-size: 15px;
  color: #303133;
}

.section-title p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #909399;
}

.channel-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.channel-card {
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 14px;
  background: #fafafa;
  transition: border-color 0.2s, background 0.2s;
}

.channel-card.active {
  border-color: #b3d8ff;
  background: #f0f9ff;
}

.channel-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.channel-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.channel-desc {
  margin: 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}

.form-item-help {
  color: #909399;
  font-size: 12px;
  margin: 4px 0 0;
  line-height: 1.5;
}

.resolved-url {
  color: #409eff;
  word-break: break-all;
}

.test-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.test-success {
  color: #67c23a;
}

.test-fail {
  color: #f56c6c;
}

.loading-state {
  padding: 48px 20px;
  text-align: center;
  color: #909399;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
}

@media (max-width: 768px) {
  .card-header {
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
  }

  :deep(.el-form-item__label) {
    width: 110px !important;
  }
}
</style>

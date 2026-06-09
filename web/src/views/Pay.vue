<template>

  <div class="pay-page">

    <div class="pay-card">

      <div v-if="loading" class="loading-state">

        <el-icon class="is-loading" :size="24"><Loading /></el-icon>

        <span>正在加载…</span>

      </div>



      <template v-else-if="!paymentEnabled">

        <div class="pay-header">

          <h1>暂不可支付</h1>

          <p>支付功能未开启，请联系提供方。</p>

        </div>

      </template>



      <template v-else-if="qrState">

        <div class="pay-header">

          <h1>扫码支付</h1>

          <p>请使用{{ qrChannelLabel }}扫描下方二维码完成支付</p>

        </div>

        <div class="qr-box">

          <img :src="qrState.qr_image" alt="支付二维码" class="qr-img" />

          <div class="qr-amount">¥{{ qrState.money }}</div>

          <div class="qr-status">

            <el-icon class="is-loading"><Loading /></el-icon>

            <span>支付完成后将自动跳转…</span>

          </div>

        </div>

        <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

        <el-button class="pay-btn" size="large" @click="cancelQrPay">取消</el-button>

      </template>



      <template v-else>

        <div class="pay-header">

          <h1>{{ deviceContext.display_name || '产品授权' }}</h1>

          <p v-if="deviceContext.can_pay">为本设备购买授权，支付后返回客户端即可生效</p>

        </div>



        <div v-if="deviceContext.can_pay" class="order-summary">

          <div class="price-row">

            <span class="price-label">授权费用</span>

            <span class="price-value">¥{{ deviceContext.price }}</span>

          </div>

          <div v-if="form.device_id" class="meta-row">

            <span class="meta-label">设备</span>

            <span class="meta-value">{{ shortDeviceId(form.device_id) }}</span>

          </div>

          <div v-if="payChannelLabel" class="meta-row">

            <span class="meta-label">支付方式</span>

            <span class="meta-value">{{ payChannelLabel }}</span>

          </div>

        </div>



        <el-form

          v-if="needDeviceInput"

          ref="formRef"

          :model="form"

          :rules="rules"

          @submit.prevent="submit"

        >

          <el-form-item prop="device_id">

            <el-input

              v-model="form.device_id"

              size="large"

              placeholder="请输入设备 ID"

              @keyup.enter="submit"

              @blur="refreshDeviceContext"

            />

          </el-form-item>

        </el-form>



        <el-button

          type="primary"

          size="large"

          class="pay-btn"

          :loading="submitting"

          :disabled="!readyToPay"

          @click="submit"

        >

          {{ payButtonText }}

        </el-button>



        <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

      </template>

    </div>

  </div>

</template>



<script setup>

import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

import { useRoute, useRouter } from 'vue-router'

import { Loading } from '@element-plus/icons-vue'

import { ElMessage } from 'element-plus'

import { api } from '../api'

import { redirectToEpayOrder } from '../utils/epayPay'

import { payTypeLabel } from '../constants/payChannels'

import { parsePayPageQuery } from '../utils/payPageUrl'

import { savePaymentOrderContext } from '../utils/paymentOrderContext'



const route = useRoute()

const router = useRouter()

const formRef = ref(null)

const loading = ref(true)

const submitting = ref(false)

const paymentEnabled = ref(false)

const errorMessage = ref('')

const pendingQuery = ref(parsePayPageQuery(route.query))

const autoPayPending = ref(false)

const qrState = ref(null)

let qrPollTimer = null



const deviceContext = ref({

  display_name: '',

  price: '',

  pay_type: '',

  can_pay: false,

  message: '',

})



const form = ref({

  device_id: '',

})



const rules = {

  device_id: [{ required: true, message: '请输入设备 ID', trigger: 'blur' }],

}



const payChannelLabel = computed(() =>

  deviceContext.value.pay_type ? payTypeLabel(deviceContext.value.pay_type) : ''

)



const qrChannelLabel = computed(() => {

  const t = qrState.value?.pay_type || deviceContext.value.pay_type

  return t ? payTypeLabel(t) : '对应'

})



const needDeviceInput = computed(() => !form.value.device_id.trim())



const readyToPay = computed(() =>

  !!form.value.device_id.trim() &&

  deviceContext.value.can_pay &&

  !!deviceContext.value.pay_type &&

  paymentEnabled.value

)



const payButtonText = computed(() => {

  if (!form.value.device_id.trim()) return '请输入设备 ID 后支付'

  if (!deviceContext.value.can_pay) return '暂不可支付'

  const price = deviceContext.value.price

  return price ? `立即支付 ¥${price}` : '立即支付'

})



const shortDeviceId = (id) => {

  const s = String(id || '')

  if (s.length <= 16) return s

  return `${s.slice(0, 8)}…${s.slice(-6)}`

}



const refreshDeviceContext = async () => {

  const deviceId = form.value.device_id.trim()

  if (!deviceId) {

    deviceContext.value = {

      display_name: '',

      price: '',

      pay_type: '',

      can_pay: false,

      message: '',

    }

    return

  }

  try {

    const ctx = await api.getPaymentDeviceContext(deviceId)

    deviceContext.value = {

      display_name: ctx.display_name || '',

      price: ctx.price || '',

      pay_type: ctx.pay_type || '',

      can_pay: !!ctx.can_pay,

      message: ctx.message || '',

    }

    errorMessage.value = ctx.can_pay ? '' : (ctx.message || '暂不可支付')

  } catch (error) {

    deviceContext.value = {

      display_name: '',

      price: '',

      pay_type: '',

      can_pay: false,

      message: error.message || '加载失败',

    }

    errorMessage.value = deviceContext.value.message

  }

}



const applyQuery = async () => {

  const q = pendingQuery.value

  if (q.device_id) {

    form.value.device_id = q.device_id

    await refreshDeviceContext()

  }

  autoPayPending.value = q.auto_pay

}



const loadPaymentMeta = async () => {

  const channelData = await api.getPaymentChannels()

  paymentEnabled.value = !!channelData?.enabled

  await applyQuery()

}



const submit = async () => {

  if (!readyToPay.value) return false



  if (needDeviceInput.value && formRef.value) {

    let valid = false

    await formRef.value.validate((ok) => { valid = ok })

    if (!valid) return false

  }



  submitting.value = true

  errorMessage.value = ''

  try {

    const deviceId = form.value.device_id.trim()

    const order = await api.createPaymentOrder({

      device_id: deviceId,

    })

    savePaymentOrderContext(order.out_trade_no, deviceId)

    if (order.pay_mode === 'qrcode' && order.qr_image) {

      startQrPay(order, deviceId)

      return true

    }

    redirectToEpayOrder(order)

    return true

  } catch (error) {

    errorMessage.value = error.message || '创建订单失败'

    ElMessage.error(errorMessage.value)

    return false

  } finally {

    submitting.value = false

  }

}



const stopQrPoll = () => {

  if (qrPollTimer) {

    clearInterval(qrPollTimer)

    qrPollTimer = null

  }

}



const startQrPay = (order, deviceId) => {

  errorMessage.value = ''

  qrState.value = {

    out_trade_no: order.out_trade_no,

    qr_image: order.qr_image,

    money: order.money,

    pay_type: order.pay_type,

    device_id: deviceId,

  }

  stopQrPoll()

  qrPollTimer = setInterval(pollQrOrder, 3000)

}



const pollQrOrder = async () => {

  const state = qrState.value

  if (!state) return

  try {

    const order = await api.getPaymentOrder(state.out_trade_no, true, state.device_id)

    if (order.status === 'paid') {

      stopQrPoll()

      router.push({ path: '/pay/result', query: { out_trade_no: state.out_trade_no } })

    }

  } catch (error) {

    // 轮询失败忽略，等待下次重试

  }

}



const cancelQrPay = () => {

  stopQrPoll()

  qrState.value = null

  errorMessage.value = ''

}



const tryAutoPay = async () => {

  if (!readyToPay.value) return

  const q = pendingQuery.value

  if (!autoPayPending.value && !q.device_id) return

  autoPayPending.value = false

  await submit()

}



const initFromRoute = async () => {

  pendingQuery.value = parsePayPageQuery(route.query)

  loading.value = true

  try {

    await loadPaymentMeta()

    await tryAutoPay()

  } catch (error) {

    errorMessage.value = error.message || '加载失败'

    ElMessage.error(errorMessage.value)

  } finally {

    loading.value = false

  }

}



onMounted(initFromRoute)



onUnmounted(stopQrPoll)



watch(() => route.query, () => {

  void initFromRoute()

})

</script>



<style scoped>

.pay-page {

  min-height: 100vh;

  display: flex;

  align-items: center;

  justify-content: center;

  background: linear-gradient(160deg, #eef2ff 0%, #f0fdf4 100%);

  padding: 24px;

}



.pay-card {

  width: 100%;

  max-width: 400px;

  background: #fff;

  border-radius: 20px;

  padding: 32px 28px;

  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.06);

}



.pay-header h1 {

  margin: 0;

  font-size: 22px;

  font-weight: 600;

  color: #303133;

  text-align: center;

}



.pay-header p {

  margin: 10px 0 0;

  color: #909399;

  font-size: 14px;

  text-align: center;

}



.loading-state {

  display: flex;

  flex-direction: column;

  align-items: center;

  gap: 12px;

  padding: 40px 0;

  color: #909399;

}



.order-summary {

  margin: 24px 0 20px;

  padding: 16px 18px;

  background: #f8fafc;

  border-radius: 12px;

}



.price-row {

  display: flex;

  justify-content: space-between;

  align-items: baseline;

  margin-bottom: 12px;

}



.price-label {

  font-size: 14px;

  color: #606266;

}



.price-value {

  font-size: 28px;

  font-weight: 700;

  color: #f56c6c;

}



.meta-row {

  display: flex;

  justify-content: space-between;

  font-size: 13px;

  padding-top: 8px;

  border-top: 1px solid #ebeef5;

  margin-top: 8px;

}



.meta-label {

  color: #909399;

}



.meta-value {

  color: #606266;

  font-family: monospace;

  max-width: 60%;

  overflow: hidden;

  text-overflow: ellipsis;

  white-space: nowrap;

}



.pay-btn {

  width: 100%;

  height: 48px;

  font-size: 16px;

  font-weight: 600;

  border-radius: 12px;

  margin-top: 8px;

}



.error-text {

  margin: 12px 0 0;

  font-size: 13px;

  color: #f56c6c;

  text-align: center;

}



.qr-box {

  display: flex;

  flex-direction: column;

  align-items: center;

  gap: 14px;

  margin: 24px 0 20px;

}



.qr-img {

  width: 220px;

  height: 220px;

  padding: 12px;

  background: #fff;

  border: 1px solid #ebeef5;

  border-radius: 12px;

}



.qr-amount {

  font-size: 26px;

  font-weight: 700;

  color: #f56c6c;

}



.qr-status {

  display: flex;

  align-items: center;

  gap: 8px;

  color: #909399;

  font-size: 13px;

}

</style>



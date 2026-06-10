<template>
  <div class="result-page">
    <div class="result-card">
      <el-result
        :icon="success ? 'success' : 'warning'"
        :title="success ? '支付成功' : '支付处理中'"
        :sub-title="message"
      >
        <template #extra>
          <p v-if="outTradeNo" class="order-no">订单号：{{ outTradeNo }}</p>
          <el-button type="primary" @click="recheck" :loading="checking">刷新状态</el-button>
          <el-button @click="goPay">返回支付页</el-button>
        </template>
      </el-result>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import {
  clearPaymentOrderContext,
  resolvePaymentDeviceId,
} from '../utils/paymentOrderContext'
const route = useRoute()
const router = useRouter()
const success = ref(false)
const message = ref('正在确认支付结果...')
const outTradeNo = ref('')
const deviceId = ref('')
const checking = ref(false)
const applyResult = (data) => {
  success.value = !!data?.success
  message.value = data?.message || (success.value ? '授权已开通' : '请稍后重试')
  outTradeNo.value = data?.out_trade_no || outTradeNo.value
}
const recheck = async () => {
  if (!outTradeNo.value) return
  deviceId.value = resolvePaymentDeviceId(route.query, outTradeNo.value)
  if (!deviceId.value) {
    message.value = '无法验证订单归属，请从支付页重新发起支付'
    return
  }
  checking.value = true
  try {
    const order = await api.getPaymentOrder(outTradeNo.value, true, deviceId.value)
    success.value = order.status === 'paid'
    message.value = success.value ? '支付成功，授权已开通' : '订单尚未支付完成'
    if (success.value) {
      clearPaymentOrderContext()
    }
  } catch (error) {
    message.value = error.message || '查询失败'
  } finally {
    checking.value = false
  }
}
const goPay = () => {
  router.push('/pay')
}
onMounted(async () => {
  outTradeNo.value = String(route.query.out_trade_no || '')
  deviceId.value = resolvePaymentDeviceId(route.query, outTradeNo.value)
  try {
    const data = await api.getEpayReturn(route.query, deviceId.value)
    applyResult(data)
    if (success.value) {
      clearPaymentOrderContext()
    }
  } catch (error) {
    message.value = error.message || '无法确认支付结果'
    if (outTradeNo.value) {
      await recheck()
    }
  }
})
</script>
<style scoped>
.result-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  padding: 24px;
}
.result-card {
  width: 100%;
  max-width: 560px;
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
}
.order-no {
  margin: 0 0 12px;
  color: #606266;
  font-size: 13px;
  word-break: break-all;
}
</style>

import { ref, onUnmounted } from 'vue'
import { api } from '../api'

const DEFAULT_INTERVAL_MS = 3000

/**
 * 扫码支付订单轮询：管理二维码状态与定时查询，支付成功时回调 onPaid。
 * 将轮询/定时器等传输细节从支付页中解耦出来。
 */
export function useQrOrderPolling({ onPaid, intervalMs = DEFAULT_INTERVAL_MS } = {}) {
  const qrState = ref(null)
  let timer = null

  const stop = () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  const poll = async () => {
    const state = qrState.value
    if (!state) return
    try {
      const order = await api.getPaymentOrder(state.out_trade_no, true, state.device_id)
      if (order.status === 'paid') {
        stop()
        onPaid?.(state)
      }
    } catch {
      // 轮询失败忽略，等待下次重试
    }
  }

  const start = (order, deviceId) => {
    qrState.value = {
      out_trade_no: order.out_trade_no,
      qr_image: order.qr_image,
      money: order.money,
      pay_type: order.pay_type,
      device_id: deviceId,
    }
    stop()
    timer = setInterval(poll, intervalMs)
  }

  const cancel = () => {
    stop()
    qrState.value = null
  }

  onUnmounted(stop)

  return { qrState, start, cancel, stop }
}

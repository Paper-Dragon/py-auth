const STORAGE_KEY = 'payment_pending_order'

export function savePaymentOrderContext(outTradeNo, deviceId) {
  const out_trade_no = String(outTradeNo || '').trim()
  const device_id = String(deviceId || '').trim()
  if (!out_trade_no || !device_id) return
  try {
    sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ out_trade_no, device_id }),
    )
  } catch (_) {
  }
}

export function loadPaymentOrderContext(outTradeNo) {
  const expected = String(outTradeNo || '').trim()
  if (!expected) return ''
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return ''
    const ctx = JSON.parse(raw)
    if (ctx?.out_trade_no === expected && ctx?.device_id) {
      return String(ctx.device_id).trim()
    }
  } catch (_) {
  }
  return ''
}

export function clearPaymentOrderContext() {
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch (_) {
  }
}

export function resolvePaymentDeviceId(query, outTradeNo) {
  const fromQuery = String(query?.device_id || '').trim()
  if (fromQuery) return fromQuery
  return loadPaymentOrderContext(outTradeNo)
}

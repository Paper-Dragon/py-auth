const TRUTHY = new Set(['1', 'true', 'yes', 'on'])

/** 支付页仅需 device_id，产品与支付方式由服务端按设备绑定解析。 */
export function parsePayPageQuery(query = {}) {
  const deviceId = String(query.device_id ?? query.deviceId ?? '').trim()
  const autoRaw = String(query.auto_pay ?? query.auto ?? '').trim().toLowerCase()
  return {
    device_id: deviceId,
    auto_pay: TRUTHY.has(autoRaw),
  }
}

export function buildPayPageUrl(base = '/pay', params = {}) {
  const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost'
  const path = base.startsWith('http') ? base : `${origin}${base.startsWith('/') ? base : `/${base}`}`
  const url = new URL(path)

  const parsed = typeof params.device_id !== 'undefined'
    ? { device_id: params.device_id, auto_pay: params.auto_pay }
    : parsePayPageQuery(params)

  if (parsed.device_id) url.searchParams.set('device_id', parsed.device_id)
  if (parsed.auto_pay) url.searchParams.set('auto_pay', '1')

  return url.pathname + url.search
}

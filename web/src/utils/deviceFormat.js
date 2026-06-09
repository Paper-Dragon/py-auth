export function formatDeviceInfoJson(raw) {
  if (raw == null || raw === '') return ''
  try {
    const o = typeof raw === 'string' ? JSON.parse(raw) : raw
    return JSON.stringify(o, null, 2)
  } catch {
    return typeof raw === 'string' ? raw : JSON.stringify(raw, null, 2)
  }
}

export function maskDeviceId(id) {
  const value = String(id || '')
  if (value.length <= 14) return value
  return `${value.slice(0, 8)}…${value.slice(-5)}`
}

export function formatDate(dateStr) {
  if (!dateStr) return '-'
  try {
    return new Date(dateStr).toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return dateStr
  }
}

export function productLabel(row) {
  if (row?.product_display_name) return row.product_display_name
  if (row?.product_key) return row.product_key
  return '未绑定'
}

export function showSoftwareName(row) {
  const name = (row?.software_name || '').trim()
  return !!name && name !== productLabel(row)
}

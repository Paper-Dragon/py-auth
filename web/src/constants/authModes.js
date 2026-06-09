export const AUTH_MODES = [
  { value: 'open', label: '默认', tagType: 'success' },
  { value: 'manual', label: '手动审核', tagType: 'warning' },
  { value: 'paid', label: '付费', tagType: 'danger' },
]

const AUTH_MODE_MAP = Object.fromEntries(AUTH_MODES.map((item) => [item.value, item]))

export const authModeLabel = (mode, fallback = '') =>
  AUTH_MODE_MAP[mode]?.label || mode || fallback

export const authModeTagType = (mode) => AUTH_MODE_MAP[mode]?.tagType || 'info'

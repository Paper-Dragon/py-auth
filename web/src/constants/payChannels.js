export const PAY_CHANNELS = [
  { value: 'alipay', label: '支付宝', description: '支付宝扫码或网页支付' },
  { value: 'wxpay', label: '微信支付', description: '微信扫码或 H5 支付' },
  { value: 'qqpay', label: 'QQ 钱包', description: 'QQ 钱包扫码支付' },
]

export const payTypeLabel = (type) => {
  const item = PAY_CHANNELS.find((c) => c.value === type)
  return item?.label || type
}

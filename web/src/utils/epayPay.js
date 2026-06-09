export function redirectToEpayOrder(order) {
  if (!order) {
    throw new Error('订单数据为空')
  }

  if (order.pay_mode === 'form' && order.submit_action && order.form_fields) {
    const form = document.createElement('form')
    form.method = 'POST'
    form.action = order.submit_action
    form.style.display = 'none'

    Object.entries(order.form_fields).forEach(([key, value]) => {
      const input = document.createElement('input')
      input.type = 'hidden'
      input.name = key
      input.value = String(value ?? '')
      form.appendChild(input)
    })

    document.body.appendChild(form)
    form.submit()
    return
  }

  if (order.pay_url) {
    window.location.href = order.pay_url
    return
  }

  if (order.pay_mode === 'qrcode') {
    throw new Error('该订单为扫码支付，需展示二维码而非跳转')
  }

  throw new Error('未获取到支付跳转信息')
}

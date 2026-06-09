const API_BASE = '/api'


export const SESSION_EXPIRED_MESSAGE = '登录已过期，请重新登录'

let onSessionExpired = null


export function configureSessionExpired(handler) {
  onSessionExpired = handler
}

export function notifySessionExpired() {
  api.setToken(null)
  try {
    localStorage.removeItem('username')
    localStorage.removeItem('isAdmin')
  } catch (_) {
  }
  onSessionExpired?.()
}

export function isSessionExpiredError(err) {
  const m = err?.message
  return typeof m === 'string' && m.includes('登录已过期')
}

class ApiService {
  constructor() {
    this.token = localStorage.getItem('authToken')
  }

  setToken(token) {
    this.token = token
    if (token) {
      localStorage.setItem('authToken', token)
    } else {
      localStorage.removeItem('authToken')
    }
  }

  getToken() {
    return this.token
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    const response = await fetch(url, {
      ...options,
      headers
    })

    if (response.status === 401) {
      notifySessionExpired()
      throw new Error(SESSION_EXPIRED_MESSAGE)
    }

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}`
      try {
        const errorData = await response.json()
        errorMessage = errorData.detail || errorData.message || errorMessage
      } catch (e) {
      }
      throw new Error(errorMessage)
    }

    if (response.status === 204) {
      return null
    }
    return response.json()
  }

  
  async login(username, password) {
    
    this.setToken(null)

    const data = await this.request('/user/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    })
    this.setToken(data.access_token)
    return data
  }

  async verifyToken() {
    try {
      await this.request('/user/verify')
      return true
    } catch (e) {
      return false
    }
  }

  async changePassword(oldPassword, newPassword) {
    return this.request('/user/change-password', {
      method: 'POST',
      body: JSON.stringify({
        old_password: oldPassword,
        new_password: newPassword
      })
    })
  }

  logout() {
    this.setToken(null)
    try {
      localStorage.removeItem('username')
      localStorage.removeItem('isAdmin')
    } catch (_) {
    }
  }

  
  async getConfigs() {
    return this.request('/admin/config')
  }

  async updateConfigs(configs) {
    return this.request('/admin/config', {
      method: 'PUT',
      body: JSON.stringify({ configs })
    })
  }

  async getOperationLogs(page = 1, pageSize = 50) {
    return this.request(`/admin/logs?page=${page}&page_size=${pageSize}`)
  }

  async cleanupOperationLogs(days) {
    if (!Number.isInteger(days) || days < 0) {
      throw new Error('days 必须是大于等于 0 的整数')
    }
    return this.request(`/admin/logs?days=${days}`, {
      method: 'DELETE'
    })
  }

  
  async getUsers() {
    return this.request('/admin/users')
  }

  async createUser(userData) {
    return this.request('/admin/users', {
      method: 'POST',
      body: JSON.stringify(userData)
    })
  }

  async updateUser(userId, userData) {
    return this.request(`/admin/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(userData)
    })
  }

  async deleteUser(userId) {
    return this.request(`/admin/users/${userId}`, {
      method: 'DELETE'
    })
  }

  async getMe() {
    return this.request('/user/me')
  }

  async getProducts() {
    return this.request('/admin/products')
  }

  async getProductOptions() {
    return this.request('/admin/products/options')
  }

  async createProduct(productData) {
    return this.request('/admin/products', {
      method: 'POST',
      body: JSON.stringify(productData)
    })
  }

  async updateProduct(productId, productData) {
    return this.request(`/admin/products/${productId}`, {
      method: 'PUT',
      body: JSON.stringify(productData)
    })
  }

  async deleteProduct(productId) {
    return this.request(`/admin/products/${productId}`, {
      method: 'DELETE'
    })
  }

  async generateProductKey() {
    return this.request('/admin/products/generate-key', {
      method: 'POST'
    })
  }

  async regenerateProductClientSecret(productId) {
    return this.request(`/admin/products/${productId}/regenerate-client-secret`, {
      method: 'POST'
    })
  }

  async getEpayConfig() {
    return this.request('/admin/payment/epay')
  }

  async updateEpayConfig(configData) {
    return this.request('/admin/payment/epay', {
      method: 'PUT',
      body: JSON.stringify(configData)
    })
  }

  async getPaymentOrders({
    page = 1,
    pageSize = 20,
    status = '',
    payType = '',
    keyword = '',
    testOnly = '',
  } = {}) {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    })
    if (status) params.set('status', status)
    if (payType) params.set('pay_type', payType)
    if (keyword) params.set('keyword', keyword)
    if (testOnly !== '' && testOnly !== null && testOnly !== undefined) {
      params.set('test_only', String(testOnly))
    }
    return this.request(`/admin/payment/orders?${params.toString()}`)
  }

  async syncPaymentOrder(outTradeNo) {
    return this.request(`/admin/payment/orders/${encodeURIComponent(outTradeNo)}/sync`, {
      method: 'POST',
    })
  }

  async getPaymentDeviceContext(deviceId) {
    const params = new URLSearchParams({ device_id: deviceId })
    return this.request(`/payment/device-context?${params}`)
  }

  async getPaymentChannels() {
    return this.request('/payment/channels')
  }

  async createPaymentOrder(orderData) {
    return this.request('/payment/orders', {
      method: 'POST',
      body: JSON.stringify(orderData)
    })
  }

  async getPaymentOrder(outTradeNo, sync = false, deviceId = '') {
    const params = new URLSearchParams()
    if (sync) params.set('sync', 'true')
    const did = String(deviceId || '').trim()
    if (did) params.set('device_id', did)
    const qs = params.toString() ? `?${params.toString()}` : ''
    return this.request(`/payment/orders/${encodeURIComponent(outTradeNo)}${qs}`)
  }

  async testEpayConnection(payload) {
    return this.request('/admin/payment/epay/test-connection', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  async testEpayPayment(payload) {
    return this.request('/admin/payment/epay/test-pay', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  async getEpayReturn(query = {}, deviceId = '') {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(query)) {
      if (key === 'device_id') continue
      if (value !== undefined && value !== null && value !== '') {
        params.set(key, String(value))
      }
    }
    const did = String(deviceId || '').trim()
    if (did) params.set('device_id', did)
    const qs = params.toString()
    return this.request(`/payment/epay/return${qs ? `?${qs}` : ''}`)
  }
}

export const api = new ApiService()

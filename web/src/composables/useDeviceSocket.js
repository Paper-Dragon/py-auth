import { api, notifySessionExpired, SESSION_EXPIRED_MESSAGE } from '../api'

const REQUEST_TIMEOUT_MS = 8000
const RECONNECT_DELAY_MS = 3000

/**
 * 封装设备管理 WebSocket 的连接、断线重连与请求/响应关联逻辑。
 *
 * 通过回调把业务事件交还给调用方，使组件无需关心传输细节：
 * - onDevicesList(data): 收到设备列表推送
 * - onDevicesChanged():  收到设备变更广播
 * - onOpen():            连接建立
 */
export function useDeviceSocket({ onDevicesList, onDevicesChanged, onOpen } = {}) {
  let socket = null
  let reconnectTimer = null
  let reconnectEnabled = true
  let requestSeq = 0
  const pendingRequests = new Map()

  const isOpen = () => !!socket && socket.readyState === WebSocket.OPEN

  const rejectPendingRequests = (message) => {
    for (const [, pending] of pendingRequests) {
      pending.reject(new Error(message))
    }
    pendingRequests.clear()
  }

  const sendRequest = (payload) => {
    return new Promise((resolve, reject) => {
      if (!isOpen()) {
        reject(new Error('实时连接未就绪'))
        return
      }

      requestSeq += 1
      const requestId = `r_${Date.now()}_${requestSeq}`
      pendingRequests.set(requestId, { resolve, reject, requestType: payload.type })
      socket.send(JSON.stringify({ ...payload, request_id: requestId }))

      setTimeout(() => {
        const pending = pendingRequests.get(requestId)
        if (!pending) return
        pendingRequests.delete(requestId)
        pending.reject(new Error('实时请求超时'))
      }, REQUEST_TIMEOUT_MS)
    })
  }

  const handleMessage = (event) => {
    let data
    try {
      data = JSON.parse(event.data)
    } catch {
      return
    }

    if (data?.request_id) {
      const pending = pendingRequests.get(data.request_id)
      if (pending) {
        pendingRequests.delete(data.request_id)
        if (data.type === 'error') {
          pending.reject(new Error(data.message || '实时请求失败'))
          return
        }
        pending.resolve(data)
        if (data.type === 'devices_list') {
          onDevicesList?.(data)
        }
        return
      }
    }

    if (data?.type === 'devices_list') {
      onDevicesList?.(data)
      return
    }
    if (data?.type === 'devices_changed') {
      onDevicesChanged?.()
    }
  }

  const cleanup = () => {
    if (socket) {
      socket.close()
      socket = null
    }
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  const connect = () => {
    if (socket) return

    const token = api.getToken()
    if (!token) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws?token=${encodeURIComponent(token)}`
    socket = new WebSocket(wsUrl)

    socket.onmessage = handleMessage

    socket.onclose = (event) => {
      socket = null
      if (event.code === 4401) {
        rejectPendingRequests(SESSION_EXPIRED_MESSAGE)
        notifySessionExpired()
        return
      }
      rejectPendingRequests('实时连接已断开')

      if (!reconnectEnabled) return
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null
        connect()
      }, RECONNECT_DELAY_MS)
    }

    socket.onerror = () => {
      if (socket) socket.close()
    }

    socket.onopen = () => {
      onOpen?.()
    }
  }

  const setReconnectEnabled = (enabled) => {
    reconnectEnabled = enabled
  }

  return {
    connect,
    cleanup,
    sendRequest,
    isOpen,
    rejectPendingRequests,
    setReconnectEnabled,
  }
}

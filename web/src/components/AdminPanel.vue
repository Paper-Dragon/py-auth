<template>
  <div class="admin-panel">
    <div class="content">
      
      <div class="stats">
        <div class="stat-card">
          <div class="stat-icon total"><el-icon :size="24"><Box /></el-icon></div>
          <div class="stat-info">
            <span class="stat-value">{{ total }}</span>
            <span class="stat-label">总设备</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon success"><el-icon :size="24"><CircleCheck /></el-icon></div>
          <div class="stat-info">
            <span class="stat-value">{{ authorizedCount }}</span>
            <span class="stat-label">已授权</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon danger"><el-icon :size="24"><CircleClose /></el-icon></div>
          <div class="stat-info">
            <span class="stat-value">{{ unauthorizedCount }}</span>
            <span class="stat-label">未授权</span>
          </div>
        </div>
      </div>

      
      <div class="device-section">
        <div class="section-header">
          <h2>设备列表</h2>
          <div v-if="selectedCount > 0" class="section-actions">
            <span class="selected-hint">已选 {{ selectedCount }} 项</span>
            <el-button type="danger" size="small" :loading="bulkDeleting" @click="deleteSelectedDevices">
              批量删除
            </el-button>
            <el-button type="primary" link size="small" @click="clearDeviceSelection">取消选择</el-button>
          </div>
        </div>

        <div class="filter-row">
          <el-select
            v-model="filterProductKey"
            clearable
            placeholder="全部产品"
            style="width: 200px"
            @change="applyFilters"
          >
            <el-option label="未绑定产品" value="__none__" />
            <el-option
              v-for="item in productOptions"
              :key="item.key"
              :label="item.display_name"
              :value="item.key"
            />
          </el-select>
          <el-select v-model="filterAuthStatus" style="width: 120px" @change="applyFilters">
            <el-option label="全部状态" value="" />
            <el-option label="已授权" value="authorized" />
            <el-option label="未授权" value="unauthorized" />
          </el-select>
          <el-input
            v-model="filterKeyword"
            clearable
            placeholder="搜索设备 ID / 软件名称 / 备注"
            style="width: 240px"
            @keyup.enter="applyFilters"
            @clear="applyFilters"
          />
          <el-button type="primary" @click="applyFilters">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>

        <el-table
          ref="tableRef"
          row-key="device_id"
          :data="devices"
          :loading="loading"
          stripe
          border
          class="admin-data-table desktop-table"
          empty-text="暂无设备"
          @sort-change="handleSortChange"
          @selection-change="handleSelectionChange"
          :default-sort="{ prop: sortBy, order: sortOrder === 'asc' ? 'ascending' : 'descending' }"
        >
          <el-table-column type="selection" width="48" :selectable="rowSelectable" />
          <el-table-column prop="device_id" label="设备ID" min-width="128">
            <template #default="{ row }">
              <code
                class="device-id device-id-toggle"
                :title="expandedDeviceIds.has(row.device_id) ? undefined : row.device_id"
                @click="toggleDeviceId(row.device_id)"
              >{{ expandedDeviceIds.has(row.device_id) ? row.device_id : maskDeviceId(row.device_id) }}</code>
            </template>
          </el-table-column>
          <el-table-column prop="software_name" label="软件名称" min-width="140" sortable="custom" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="product-cell">
                <span class="product-name">{{ row.software_name || '—' }}</span>
                <el-tag
                  v-if="row.product_display_name && !row.product_known"
                  size="small"
                  type="info"
                >默认</el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="device_info" label="详情" width="64" align="center">
            <template #default="{ row }">
              <el-button v-if="row.device_info" type="primary" link size="small" @click="showDeviceInfo(row)">查看</el-button>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="100" class-name="remark-cell">
            <template #default="{ row }">
              <el-input v-model="row._remarkValue" size="small" placeholder="备注" @blur="saveRemark(row)" @keyup.enter="saveRemark(row)" />
            </template>
          </el-table-column>
          <el-table-column prop="is_authorized" label="状态" width="76" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_authorized ? 'success' : 'danger'" size="small">
                {{ row.is_authorized ? '已授权' : '未授权' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" min-width="148" sortable="custom" show-overflow-tooltip>
            <template #header>
              <el-tooltip content="设备首次请求后不变" placement="top">
                <span class="col-head-tip">注册时间</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="updated_at" min-width="148" sortable="custom" show-overflow-tooltip>
            <template #header>
              <el-tooltip content="管理员改授权/备注或设备信息变更" placement="top">
                <span class="col-head-tip">管理变更追踪</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column prop="last_check" min-width="136" sortable="custom" show-overflow-tooltip>
            <template #header>
              <el-tooltip content="每次成功心跳/授权校验" placement="top">
                <span class="col-head-tip">活跃度</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">{{ formatDate(row.last_check) }}</template>
          </el-table-column>
          <el-table-column label="操作" min-width="192" fixed="right" align="center">
            <template #default="{ row }">
              <div class="op-btns">
                <el-button v-if="row.is_authorized" type="warning" size="small" @click="toggleAuth(row, false)" :loading="row._updating">取消授权</el-button>
                <el-button v-else type="success" size="small" @click="toggleAuth(row, true)" :loading="row._updating">授权</el-button>
                <el-button type="danger" size="small" @click="deleteDevice(row)" :loading="row._updating">删除设备</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        
        <div class="mobile-list">
          <div v-if="loading" class="loading-state">
            <el-icon class="is-loading" :size="20"><Refresh /></el-icon>
            <span>加载中...</span>
          </div>
          <div v-else-if="devices.length === 0" class="empty-state">
            <el-empty description="暂无设备" />
          </div>
          <div v-else class="device-cards">
            <div v-for="device in devices" :key="device.device_id" class="device-card">
              <div class="card-header">
                <el-checkbox
                  class="card-select"
                  :model-value="selectedIds.has(device.device_id)"
                  :disabled="device._updating || bulkDeleting"
                  @change="(v) => toggleMobileSelect(device.device_id, v)"
                />
                <code
                  class="device-id device-id-toggle"
                  :title="expandedDeviceIds.has(device.device_id) ? undefined : device.device_id"
                  @click="toggleDeviceId(device.device_id)"
                >{{ expandedDeviceIds.has(device.device_id) ? device.device_id : maskDeviceId(device.device_id) }}</code>
                <el-tag :type="device.is_authorized ? 'success' : 'danger'" size="small">
                  {{ device.is_authorized ? '已授权' : '未授权' }}
                </el-tag>
              </div>
              <div class="card-body">
                <div class="info-row" v-if="device.software_name">
                  <span class="label">软件：</span>
                  <span class="value">{{ device.software_name }}</span>
                </div>
                <div
                  v-if="device.product_display_name && !device.product_known"
                  class="info-row"
                >
                  <span class="label">产品：</span>
                  <el-tag size="small" type="info">默认</el-tag>
                </div>
                <div class="info-row">
                  <span class="label">注册时间：</span>
                  <span class="value">{{ formatDate(device.created_at) }}</span>
                </div>
                <div class="info-row" v-if="device.updated_at">
                  <span class="label">管理变更追踪：</span>
                  <span class="value">{{ formatDate(device.updated_at) }}</span>
                </div>
                <div class="info-row" v-if="device.last_check">
                  <span class="label">活跃度：</span>
                  <span class="value">{{ formatDate(device.last_check) }}</span>
                </div>
                <div class="info-row" v-if="device.device_info">
                  <el-button type="primary" link size="small" @click="showDeviceInfo(device)">查看设备详情</el-button>
                </div>
                <div class="info-row">
                  <span class="label">备注：</span>
                  <el-input v-model="device._remarkValue" size="small" placeholder="备注" @blur="saveRemark(device)" />
                </div>
              </div>
              <div class="card-footer">
                <el-button v-if="device.is_authorized" type="warning" size="small" @click="toggleAuth(device, false)" :loading="device._updating">取消授权</el-button>
                <el-button v-else type="success" size="small" @click="toggleAuth(device, true)" :loading="device._updating">授权</el-button>
                <el-button type="danger" size="small" @click="deleteDevice(device)" :loading="device._updating">删除</el-button>
              </div>
            </div>
          </div>
        </div>

        
        <div class="pagination">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[50, 80, 100]"
            :total="total"
            layout="total, sizes, prev, pager, next"
            @size-change="loadDevices"
            @current-change="loadDevices"
          />
        </div>
      </div>

      
      <el-dialog v-model="deviceInfoVisible" title="设备详情" width="90%" style="max-width: 640px;">
        <pre v-if="deviceInfoJsonText" class="device-info-json">{{ deviceInfoJsonText }}</pre>
        <el-empty v-else description="暂无 device_info" />
      </el-dialog>

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'


function formatDeviceInfoJson(raw) {
  if (raw == null || raw === '') return ''
  try {
    const o = typeof raw === 'string' ? JSON.parse(raw) : raw
    return JSON.stringify(o, null, 2)
  } catch {
    return typeof raw === 'string' ? raw : JSON.stringify(raw, null, 2)
  }
}
import { Refresh, Box, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, notifySessionExpired, SESSION_EXPIRED_MESSAGE } from '../api'
import { reportApiError } from '../utils/errorFeedback'
const devices = ref([])
const expandedDeviceIds = ref(new Set())
const tableRef = ref(null)
const loading = ref(false)
const bulkDeleting = ref(false)
const selectedIds = ref(new Set())
let syncingTableSelection = false

const selectedCount = computed(() => selectedIds.value.size)

const setSelectedIds = (iter) => {
  selectedIds.value = iter instanceof Set ? new Set(iter) : new Set(iter)
}

const rowSelectable = (row) => !row._updating && !bulkDeleting.value

const handleSelectionChange = (rows) => {
  if (syncingTableSelection) return
  setSelectedIds(rows.map((r) => r.device_id))
}

const syncTableSelectionFromIds = () => {
  const tbl = tableRef.value
  if (!tbl) return
  syncingTableSelection = true
  const ids = selectedIds.value
  for (const row of devices.value) {
    tbl.toggleRowSelection(row, ids.has(row.device_id))
  }
  syncingTableSelection = false
}

const toggleMobileSelect = (deviceId, checked) => {
  const s = new Set(selectedIds.value)
  if (checked) s.add(deviceId)
  else s.delete(deviceId)
  setSelectedIds(s)
  nextTick(() => syncTableSelectionFromIds())
}

const clearDeviceSelection = () => {
  setSelectedIds([])
  nextTick(() => tableRef.value?.clearSelection())
}
const deviceInfoVisible = ref(false)
const deviceInfoJsonText = ref('')
const currentPage = ref(1)
const pageSize = ref(50)
const total = ref(0)
const summary = ref({ total: 0, authorized: 0, unauthorized: 0 })
const productOptions = ref([])
const filterProductKey = ref('')
const filterKeyword = ref('')
const filterAuthStatus = ref('')
const sortBy = ref('updated_at')
const sortOrder = ref('desc')
let deviceSocket = null
let reconnectTimer = null
let reconnectEnabled = true

let pendingDevicesReload = false
let lastPageHiddenAt = 0
let wsRequestSeq = 0
const pendingWsRequests = new Map()

const authorizedCount = computed(() => summary.value.authorized ?? 0)
const unauthorizedCount = computed(() => summary.value.unauthorized ?? 0)

const maskDeviceId = (id) => {
  const value = String(id || '')
  if (value.length <= 14) return value
  return `${value.slice(0, 8)}…${value.slice(-5)}`
}

const toggleDeviceId = (deviceId) => {
  const next = new Set(expandedDeviceIds.value)
  if (next.has(deviceId)) next.delete(deviceId)
  else next.add(deviceId)
  expandedDeviceIds.value = next
}

const requestDevicesReload = () => {
  if (!loading.value) {
    void loadDevices()
  } else {
    pendingDevicesReload = true
  }
}

const applyDevicesPayload = (data) => {
  total.value = Number(data?.total || 0)
  summary.value = {
    total: Number(data?.summary?.total ?? data?.total ?? 0),
    authorized: Number(data?.summary?.authorized ?? 0),
    unauthorized: Number(data?.summary?.unauthorized ?? 0),
  }
  const list = Array.isArray(data?.devices) ? data.devices : []
  devices.value = list.map(d => ({
    ...d,
    _originalRemark: d.remark || '',
    _remarkValue: d.remark || '',
    _updating: false
  }))
}

const rejectPendingWsRequests = (message) => {
  for (const [, pending] of pendingWsRequests) {
    pending.reject(new Error(message))
  }
  pendingWsRequests.clear()
}

const sendWsRequest = (payload) => {
  return new Promise((resolve, reject) => {
    if (!deviceSocket || deviceSocket.readyState !== WebSocket.OPEN) {
      reject(new Error('实时连接未就绪'))
      return
    }

    wsRequestSeq += 1
    const requestId = `r_${Date.now()}_${wsRequestSeq}`
    pendingWsRequests.set(requestId, { resolve, reject, requestType: payload.type })
    deviceSocket.send(JSON.stringify({ ...payload, request_id: requestId }))

    setTimeout(() => {
      const pending = pendingWsRequests.get(requestId)
      if (!pending) return
      pendingWsRequests.delete(requestId)
      pending.reject(new Error('实时请求超时'))
    }, 8000)
  })
}

const cleanupWebSocket = () => {
  if (deviceSocket) {
    deviceSocket.close()
    deviceSocket = null
  }
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
}

const connectWebSocket = () => {
  if (deviceSocket) return

  const token = api.getToken()
  if (!token) return

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ws?token=${encodeURIComponent(token)}`
  deviceSocket = new WebSocket(wsUrl)

  deviceSocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data?.request_id) {
        const pending = pendingWsRequests.get(data.request_id)
        if (pending) {
          pendingWsRequests.delete(data.request_id)
          if (data.type === 'error') {
            pending.reject(new Error(data.message || '实时请求失败'))
            return
          }
          pending.resolve(data)
          if (data.type === 'devices_list') {
            applyDevicesPayload(data)
          }
          return
        }
      }

      if (data?.type === 'devices_list') {
        applyDevicesPayload(data)
        return
      }
      if (data?.type === 'devices_changed') {
        requestDevicesReload()
      }
    } catch {
    }
  }

  deviceSocket.onclose = (event) => {
    deviceSocket = null
    if (event.code === 4401) {
      rejectPendingWsRequests(SESSION_EXPIRED_MESSAGE)
      notifySessionExpired()
      return
    }
    rejectPendingWsRequests('实时连接已断开')

    if (!reconnectEnabled) return
    const delay = 3000
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connectWebSocket()
    }, delay)
  }

  deviceSocket.onerror = () => {
    if (deviceSocket) {
      deviceSocket.close()
    }
  }

  deviceSocket.onopen = () => {
    requestDevicesReload()
  }
}

const loadDevices = async () => {
  if (!deviceSocket || deviceSocket.readyState !== WebSocket.OPEN) {
    connectWebSocket()
    return
  }
  loading.value = true
  try {
    const data = await sendWsRequest({
      type: 'get_devices',
      page: currentPage.value,
      page_size: pageSize.value,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
      product_key: filterProductKey.value || null,
      keyword: filterKeyword.value || null,
      auth_status: filterAuthStatus.value || null,
    })
    applyDevicesPayload(data)
  } catch (e) {
    if (reportApiError(e, '加载失败')) return
  } finally {
    loading.value = false
    setSelectedIds([])
    nextTick(() => tableRef.value?.clearSelection())
    if (pendingDevicesReload) {
      pendingDevicesReload = false
      void loadDevices()
    }
  }
}

const applyFilters = () => {
  currentPage.value = 1
  loadDevices()
}

const resetFilters = () => {
  filterProductKey.value = ''
  filterKeyword.value = ''
  filterAuthStatus.value = ''
  currentPage.value = 1
  loadDevices()
}

const loadProductOptions = async () => {
  try {
    productOptions.value = await api.getProductOptions()
  } catch {
    productOptions.value = []
  }
}

const handleSortChange = ({ prop, order }) => {
  if (!prop || !order) {
    sortBy.value = 'updated_at'
    sortOrder.value = 'desc'
  } else {
    sortBy.value = prop
    sortOrder.value = order === 'ascending' ? 'asc' : 'desc'
  }
  loadDevices()
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  try {
    return new Date(dateStr).toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return dateStr
  }
}

const showDeviceInfo = (device) => {
  deviceInfoJsonText.value = formatDeviceInfoJson(device?.device_info)
  deviceInfoVisible.value = true
}

const saveRemark = async (device) => {
  if (device._remarkValue === device._originalRemark) return
  try {
    const result = await sendWsRequest({
      type: 'update_device',
      device_id: device.device_id,
      data: { remark: device._remarkValue }
    })
    const updatedDevice = result.device
    Object.assign(device, {
      ...updatedDevice,
      _originalRemark: updatedDevice.remark || '',
      _remarkValue: updatedDevice.remark || ''
    })
    ElMessage.success('备注已保存')
  } catch (e) {
    device._remarkValue = device._originalRemark
    reportApiError(e, '保存失败')
  }
}

const toggleAuth = async (device, authorize) => {
  
  if (device._updating) return
  device._updating = true
  try {
    const result = await sendWsRequest({
      type: 'update_device',
      device_id: device.device_id,
      data: { is_authorized: authorize }
    })
    const updatedDevice = result.device
    Object.assign(device, {
      ...updatedDevice,
      _originalRemark: updatedDevice.remark || '',
      _remarkValue: updatedDevice.remark || ''
    })
    ElMessage.success(authorize ? '已授权' : '已取消授权')
  } catch (e) {
    reportApiError(e, '操作失败')
  } finally {
    device._updating = false
  }
}

const deleteDevice = async (device) => {
  device._updating = true
  try {
    await sendWsRequest({
      type: 'delete_device',
      device_id: device.device_id
    })
    devices.value = devices.value.filter(d => d.device_id !== device.device_id)
    const s = new Set(selectedIds.value)
    s.delete(device.device_id)
    setSelectedIds(s)
    nextTick(() => syncTableSelectionFromIds())
    ElMessage.success('已删除')
  } catch (e) {
    reportApiError(e, '删除失败')
  } finally {
    device._updating = false
  }
}

const deleteSelectedDevices = async () => {
  const ids = [...selectedIds.value]
  if (ids.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${ids.length} 台设备？此操作不可恢复。`,
      '批量删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  bulkDeleting.value = true
  try {
    const result = await sendWsRequest({
      type: 'delete_devices',
      device_ids: ids
    })
    const n = Number(result?.deleted_count ?? ids.length)
    ElMessage.success(n > 0 ? `已删除 ${n} 台设备` : '已删除')
    clearDeviceSelection()
    await loadDevices()
  } catch (e) {
    reportApiError(e, '批量删除失败')
  } finally {
    bulkDeleting.value = false
  }
}

const onVisibilityChange = () => {
  if (document.hidden) {
    lastPageHiddenAt = Date.now()
    return
  }
  const awayMs = lastPageHiddenAt ? Date.now() - lastPageHiddenAt : 0
  lastPageHiddenAt = 0

  if (!deviceSocket || deviceSocket.readyState !== WebSocket.OPEN) {
    reconnectEnabled = true
    connectWebSocket()
    return
  }
  
  if (awayMs >= 3000) {
    requestDevicesReload()
  }
}

onMounted(() => {
  reconnectEnabled = true
  document.addEventListener('visibilitychange', onVisibilityChange)
  void loadProductOptions()
  connectWebSocket()
})

onUnmounted(() => {
  document.removeEventListener('visibilitychange', onVisibilityChange)
  reconnectEnabled = false
  pendingDevicesReload = false
  rejectPendingWsRequests('页面已关闭')
  cleanupWebSocket()
})
</script>

<style scoped>
.admin-panel {
  width: 100%;
}


.content {
  max-width: 1400px;
  margin: 0 auto;
}


.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  background: white;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.stat-icon.total { background: linear-gradient(135deg, #667eea, #764ba2); }
.stat-icon.success { background: linear-gradient(135deg, #56ab2f, #a8e063); }
.stat-icon.danger { background: linear-gradient(135deg, #eb3349, #f45c43); }

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
}

.stat-label {
  font-size: 12px;
  color: #909399;
}


.device-section {
  background: white;
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.section-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.selected-hint {
  font-size: 13px;
  color: #606266;
}

.col-head-tip {
  cursor: help;
  border-bottom: 1px dotted var(--el-border-color);
}

.section-header h2 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: #303133;
}


.desktop-table {
  display: block;
}

.device-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: var(--table-mono-font-size);
  color: var(--color-text-secondary);
  background: var(--color-bg-secondary);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.device-id-toggle {
  cursor: pointer;
  white-space: nowrap;
}

.device-id-toggle:hover {
  color: var(--color-primary);
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.product-cell {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.product-name {
  font-size: var(--table-font-size);
  color: var(--color-text-primary);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-cell .el-tag {
  flex-shrink: 0;
}

.device-section :deep(.remark-cell .cell) {
  overflow: visible;
}

.device-section :deep(.remark-cell .el-input) {
  width: 100%;
}

.product-key {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: var(--table-mono-font-size);
  color: var(--color-text-tertiary);
  word-break: break-all;
}

.op-btns {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 4px;
}

.op-btns .el-button {
  width: 100%;
  min-width: 0;
  padding: 5px 0;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}


.mobile-list {
  display: none;
}

.loading-state, .empty-state {
  padding: 40px 20px;
  text-align: center;
  color: #909399;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.device-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.device-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 12px;
}

.card-select {
  flex-shrink: 0;
  margin-top: 4px;
}

.card-header .device-id {
  flex: 1;
  min-width: 0;
  word-break: break-all;
  display: block;
  padding: 6px 8px;
}

.card-header .el-tag {
  flex-shrink: 0;
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.info-row .label {
  color: #909399;
  min-width: 50px;
}

.info-row .value {
  color: #303133;
}

.info-row .el-input {
  flex: 1;
}

.card-footer {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}

.card-footer .el-button {
  flex: 1;
}


@media (max-width: 768px) {
  .desktop-table {
    display: none !important;
  }
  
  .mobile-list {
    display: block;
  }
  
  .btn-label {
    display: none;
  }
  
  .stats {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .stat-card {
    padding: 12px;
    flex-direction: column;
    text-align: center;
    gap: 8px;
  }
  
  .stat-icon {
    width: 40px;
    height: 40px;
  }
  
  .stat-value {
    font-size: 20px;
  }
}

@media (max-width: 480px) {
  .content {
    padding: 12px;
  }
  
  .stats {
    grid-template-columns: 1fr;
    gap: 8px;
  }
  
  .stat-card {
    padding: 10px;
  }
  
  .stat-icon {
    width: 36px;
    height: 36px;
  }
  
  .stat-value {
    font-size: 18px;
  }
  
  .stat-label {
    font-size: 11px;
  }

  .card-footer {
    flex-wrap: wrap;
  }

  .card-footer .el-button {
    flex: 1 1 calc(50% - 4px);
  }
}

.device-info-json {
  margin: 0;
  padding: 12px;
  font-size: 12px;
  line-height: 1.45;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: min(70vh, 520px);
  overflow: auto;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  border: 1px solid var(--el-border-color-lighter);
}
</style>

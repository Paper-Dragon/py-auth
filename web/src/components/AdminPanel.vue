<template>
  <div class="admin-panel">
    <div class="content">
      
      <div class="stats">
        <div class="stat-card">
          <div class="stat-icon primary"><el-icon :size="22"><Box /></el-icon></div>
          <div class="stat-info">
            <span class="stat-value">{{ total }}</span>
            <span class="stat-label">总设备</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon success"><el-icon :size="22"><CircleCheck /></el-icon></div>
          <div class="stat-info">
            <span class="stat-value">{{ onlineCount }}</span>
            <span class="stat-label">可上线</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon warning"><el-icon :size="22"><Warning /></el-icon></div>
          <div class="stat-info">
            <span class="stat-value">{{ bannedCount }}</span>
            <span class="stat-label">已封禁</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon danger"><el-icon :size="22"><CircleClose /></el-icon></div>
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
            <el-option label="可上线" value="online" />
            <el-option label="未授权" value="unauthorized" />
            <el-option label="已封禁" value="banned" />
          </el-select>
          <el-input
            v-model="filterKeyword"
            clearable
            placeholder="搜索设备 ID / 所属产品 / 备注"
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
          fit
          style="width: 100%"
          class="admin-data-table desktop-table device-data-table"
          empty-text="暂无设备"
          table-layout="fixed"
          @sort-change="handleSortChange"
          @selection-change="handleSelectionChange"
          :default-sort="{ prop: sortBy, order: sortOrder === 'asc' ? 'ascending' : 'descending' }"
        >
          <el-table-column type="selection" width="48" :selectable="rowSelectable" />
          <el-table-column prop="device_id" label="设备ID" min-width="108" show-overflow-tooltip>
            <template #default="{ row }">
              <code
                class="device-id device-id-toggle"
                :title="expandedDeviceIds.has(row.device_id) ? undefined : row.device_id"
                @click="toggleDeviceId(row.device_id)"
              >{{ expandedDeviceIds.has(row.device_id) ? row.device_id : maskDeviceId(row.device_id) }}</code>
            </template>
          </el-table-column>
          <el-table-column prop="product_display_name" label="所属产品" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="product-cell">
                <span class="product-name">{{ productLabel(row) }}</span>
                <span v-if="showSoftwareName(row)" class="product-software">{{ row.software_name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="plan" label="套餐信息" min-width="124" align="center">
            <template #default="{ row }">
              <span class="clickable-tag" title="点击设置套餐" @click="setManualPlan(row)">
                <span v-if="row.plan_label" class="plan-cell">
                  <el-tag :type="row.plan_tag || 'info'" size="small">{{ row.plan_label }}</el-tag>
                  <span v-if="row.plan_hint" class="plan-hint-text">{{ row.plan_hint }}</span>
                </span>
                <span v-else class="text-muted">—</span>
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="device_info" label="设备信息" min-width="72" align="center">
            <template #default="{ row }">
              <el-button v-if="row.device_info" type="primary" link size="small" @click="showDeviceInfo(row)">查看</el-button>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="88" class-name="remark-cell">
            <template #default="{ row }">
              <el-input v-model="row._remarkValue" size="small" placeholder="备注" @blur="saveRemark(row)" @keyup.enter="saveRemark(row)" />
            </template>
          </el-table-column>
          <el-table-column prop="is_authorized" label="授权状态" min-width="84" align="center">
            <template #default="{ row }">
              <el-tooltip :content="row.auth_message" placement="top" :disabled="!row.auth_message">
                <el-tag :type="authStatusType(row)" size="small">
                  {{ authStatusLabel(row) }}
                </el-tag>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column prop="is_banned" label="封禁状态" min-width="84" align="center">
            <template #default="{ row }">
              <el-popconfirm
                :title="row.is_banned
                  ? '确定解封该设备？解封且仍满足授权规则后即可恢复上线。'
                  : '确定封禁该设备？封禁后即使已授权 / 已付款也无法上线。'"
                :confirm-button-text="row.is_banned ? '解封' : '封禁'"
                cancel-button-text="取消"
                confirm-button-type="warning"
                width="260"
                @confirm="toggleBan(row, !row.is_banned)"
              >
                <template #reference>
                  <el-tag :type="banStatusType(row)" size="small" class="clickable-tag">
                    {{ banStatusLabel(row) }}
                  </el-tag>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" min-width="112" sortable="custom" show-overflow-tooltip>
            <template #header>
              <el-tooltip content="设备首次接入后不变" placement="top">
                <span class="col-head-tip">首次注册</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="updated_at" min-width="112" sortable="custom" show-overflow-tooltip>
            <template #header>
              <el-tooltip content="授权、备注或设备信息变更时刷新" placement="top">
                <span class="col-head-tip">最近更新</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column prop="last_check" min-width="112" sortable="custom" show-overflow-tooltip>
            <template #header>
              <el-tooltip content="最后一次心跳或授权校验" placement="top">
                <span class="col-head-tip">最近活跃</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">{{ formatDate(row.last_check) }}</template>
          </el-table-column>
          <el-table-column label="操作" min-width="120" align="center" class-name="op-cell">
            <template #default="{ row }">
              <div class="op-btns">
                <el-button
                  v-if="needsManualApprove(row)"
                  type="primary"
                  size="small"
                  @click="toggleAuth(row, true)"
                  :loading="row._updating"
                >
                  授权
                </el-button>
                <el-button
                  v-else-if="canRevokeManualAuth(row)"
                  size="small"
                  @click="toggleAuth(row, false)"
                  :loading="row._updating"
                >
                  取消授权
                </el-button>
                <el-popconfirm
                  title="确定删除该设备？此操作不可恢复。"
                  confirm-button-text="删除"
                  cancel-button-text="取消"
                  confirm-button-type="danger"
                  width="220"
                  @confirm="deleteDevice(row)"
                >
                  <template #reference>
                    <el-button type="danger" size="small" :loading="row._updating">删除</el-button>
                  </template>
                </el-popconfirm>
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
                <div class="card-status-tags">
                  <el-tag :type="authStatusType(device)" size="small">
                    {{ authStatusLabel(device) }}
                  </el-tag>
                  <el-popconfirm
                    :title="device.is_banned
                      ? '确定解封该设备？解封且仍满足授权规则后即可恢复上线。'
                      : '确定封禁该设备？封禁后即使已授权 / 已付款也无法上线。'"
                    :confirm-button-text="device.is_banned ? '解封' : '封禁'"
                    cancel-button-text="取消"
                    confirm-button-type="warning"
                    width="260"
                    @confirm="toggleBan(device, !device.is_banned)"
                  >
                    <template #reference>
                      <el-tag :type="banStatusType(device)" size="small" class="clickable-tag">
                        {{ banStatusLabel(device) }}
                      </el-tag>
                    </template>
                  </el-popconfirm>
                </div>
              </div>
              <div class="card-body">
                <div class="info-row">
                  <span class="label">所属产品：</span>
                  <span class="value">{{ productLabel(device) }}</span>
                </div>
                <div class="info-row" v-if="showSoftwareName(device)">
                  <span class="label">客户端软件名：</span>
                  <span class="value">{{ device.software_name }}</span>
                </div>
                <div class="info-row">
                  <span class="label">授权模式：</span>
                  <span class="value">{{ authModeLabel(device.product_auth_mode) }}</span>
                </div>
                <div class="info-row">
                  <span class="label">套餐信息：</span>
                  <span class="clickable-tag" @click="setManualPlan(device)">
                    <template v-if="device.plan_label">
                      <el-tag :type="device.plan_tag || 'info'" size="small">{{ device.plan_label }}</el-tag>
                      <span v-if="device.plan_hint" class="plan-hint-text">{{ device.plan_hint }}</span>
                    </template>
                    <span v-else class="text-muted">—</span>
                  </span>
                </div>
                <div class="info-row">
                  <span class="label">首次注册：</span>
                  <span class="value">{{ formatDate(device.created_at) }}</span>
                </div>
                <div class="info-row" v-if="device.updated_at">
                  <span class="label">最近更新：</span>
                  <span class="value">{{ formatDate(device.updated_at) }}</span>
                </div>
                <div class="info-row" v-if="device.last_check">
                  <span class="label">最近活跃：</span>
                  <span class="value">{{ formatDate(device.last_check) }}</span>
                </div>
                <div class="info-row" v-if="device.device_info">
                  <el-button type="primary" link size="small" @click="showDeviceInfo(device)">查看设备信息</el-button>
                </div>
                <div class="info-row">
                  <span class="label">备注：</span>
                  <el-input v-model="device._remarkValue" size="small" placeholder="备注" @blur="saveRemark(device)" />
                </div>
              </div>
              <div class="card-footer">
                <el-button
                  v-if="needsManualApprove(device)"
                  type="primary"
                  size="small"
                  @click="toggleAuth(device, true)"
                  :loading="device._updating"
                >
                  授权
                </el-button>
                <el-button
                  v-else-if="canRevokeManualAuth(device)"
                  size="small"
                  @click="toggleAuth(device, false)"
                  :loading="device._updating"
                >
                  取消授权
                </el-button>
                <el-popconfirm
                  title="确定删除该设备？此操作不可恢复。"
                  confirm-button-text="删除"
                  cancel-button-text="取消"
                  confirm-button-type="danger"
                  width="220"
                  @confirm="deleteDevice(device)"
                >
                  <template #reference>
                    <el-button type="danger" size="small" :loading="device._updating">删除</el-button>
                  </template>
                </el-popconfirm>
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

      <el-dialog v-model="deviceInfoVisible" title="设备信息" width="90%" style="max-width: 640px;">
        <pre v-if="deviceInfoJsonText" class="device-info-json">{{ deviceInfoJsonText }}</pre>
        <el-empty v-else description="暂无 device_info" />
      </el-dialog>

      <el-dialog v-model="planDialogVisible" title="设置套餐" width="90%" style="max-width: 420px;">
        <el-form label-position="top">
          <el-form-item label="套餐档位">
            <el-select
              v-model="planDialogValue"
              clearable
              placeholder="选择套餐档位"
              style="width: 100%"
            >
              <el-option
                v-for="item in planOptions"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </el-form-item>
        </el-form>
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="清空选择并保存即清除手动套餐，恢复按付款或产品默认计算。"
        />
        <template #footer>
          <el-button @click="planDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="planDialogSaving" @click="saveManualPlan">保存</el-button>
        </template>
      </el-dialog>

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { Refresh, Box, CircleCheck, CircleClose, Warning } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { reportApiError } from '../utils/errorFeedback'
import { authModeLabel as sharedAuthModeLabel } from '../constants/authModes'
import { useDeviceSocket } from '../composables/useDeviceSocket'
import {
  formatDate,
  formatDeviceInfoJson,
  maskDeviceId,
  productLabel,
  showSoftwareName,
} from '../utils/deviceFormat'

const devices = ref([])
const expandedDeviceIds = ref(new Set())
const tableRef = ref(null)
const loading = ref(false)
let tableResizeObserver = null
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
const summary = ref({ total: 0, online: 0, banned: 0, unauthorized: 0 })
const productOptions = ref([])
const filterProductKey = ref('')
const filterKeyword = ref('')
const filterAuthStatus = ref('')
const sortBy = ref('updated_at')
const sortOrder = ref('desc')

let pendingDevicesReload = false
let lastPageHiddenAt = 0

const onlineCount = computed(() => summary.value.online ?? 0)
const bannedCount = computed(() => summary.value.banned ?? 0)
const unauthorizedCount = computed(() => summary.value.unauthorized ?? 0)

const authModeLabel = (mode) => sharedAuthModeLabel(mode, '未绑定产品')

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
    online: Number(data?.summary?.online ?? 0),
    banned: Number(data?.summary?.banned ?? 0),
    unauthorized: Number(data?.summary?.unauthorized ?? 0),
  }
  const list = Array.isArray(data?.devices) ? data.devices : []
  devices.value = list.map(d => ({
    ...d,
    _originalRemark: d.remark || '',
    _remarkValue: d.remark || '',
    _updating: false
  }))
  nextTick(() => tableRef.value?.doLayout())
}

const socket = useDeviceSocket({
  onDevicesList: applyDevicesPayload,
  onDevicesChanged: requestDevicesReload,
  onOpen: requestDevicesReload,
})

const loadDevices = async () => {
  if (!socket.isOpen()) {
    socket.connect()
    return
  }
  loading.value = true
  try {
    const data = await socket.sendRequest({
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

const showDeviceInfo = (device) => {
  deviceInfoJsonText.value = formatDeviceInfoJson(device?.device_info)
  deviceInfoVisible.value = true
}

const saveRemark = async (device) => {
  if (device._remarkValue === device._originalRemark) return
  try {
    const result = await socket.sendRequest({
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

const authStatusLabel = (device) => (device.is_authorized ? '已授权' : '未授权')

const authStatusType = (device) => (device.is_authorized ? 'success' : 'info')

const banStatusLabel = (device) => (device.is_banned ? '已封禁' : '正常')

const banStatusType = (device) => (device.is_banned ? 'danger' : 'info')

const needsManualApprove = (device) => (
  device.product_auth_mode === 'manual'
  && !device.is_authorized
  && !device.is_banned
)

const canRevokeManualAuth = (device) => (
  device.product_auth_mode === 'manual'
  && device.is_authorized
  && !device.is_banned
)

const applyDeviceUpdate = (device, updatedDevice) => {
  Object.assign(device, {
    ...updatedDevice,
    _originalRemark: updatedDevice.remark || '',
    _remarkValue: updatedDevice.remark || '',
  })
}

const toggleBan = async (device, banned) => {
  if (device._updating) return
  device._updating = true
  try {
    const result = await socket.sendRequest({
      type: 'update_device',
      device_id: device.device_id,
      data: { is_banned: banned },
    })
    applyDeviceUpdate(device, result.device)
    ElMessage.success(banned ? '已封禁' : '已解封')
    requestDevicesReload()
  } catch (e) {
    reportApiError(e, '操作失败')
  } finally {
    device._updating = false
  }
}

const toggleAuth = async (device, authorize) => {
  if (device._updating) return
  device._updating = true
  try {
    const result = await socket.sendRequest({
      type: 'update_device',
      device_id: device.device_id,
      data: { is_authorized: authorize },
    })
    applyDeviceUpdate(device, result.device)
    ElMessage.success(authorize ? '已授权' : '已取消授权')
    requestDevicesReload()
  } catch (e) {
    reportApiError(e, '操作失败')
  } finally {
    device._updating = false
  }
}

const planDialogVisible = ref(false)
const planDialogSaving = ref(false)
const planDialogValue = ref('')
const planOptions = ref([])
let planDialogDevice = null

const setManualPlan = (device) => {
  if (device._updating) return
  planDialogDevice = device
  planDialogValue.value = device.manual_plan || ''
  planOptions.value = device.plan_options || []
  planDialogVisible.value = true
}

const saveManualPlan = async () => {
  const device = planDialogDevice
  if (!device) return
  const plan = (planDialogValue.value || '').trim()
  if (plan === (device.manual_plan || '')) {
    planDialogVisible.value = false
    return
  }
  planDialogSaving.value = true
  device._updating = true
  try {
    const result = await socket.sendRequest({
      type: 'update_device',
      device_id: device.device_id,
      data: { manual_plan: plan },
    })
    applyDeviceUpdate(device, result.device)
    ElMessage.success(plan ? '已设置手动套餐' : '已清除手动套餐')
    planDialogVisible.value = false
    requestDevicesReload()
  } catch (e) {
    reportApiError(e, '操作失败')
  } finally {
    planDialogSaving.value = false
    device._updating = false
  }
}

const deleteDevice = async (device) => {
  device._updating = true
  try {
    await socket.sendRequest({
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
    const result = await socket.sendRequest({
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

  if (!socket.isOpen()) {
    socket.setReconnectEnabled(true)
    socket.connect()
    return
  }

  if (awayMs >= 3000) {
    requestDevicesReload()
  }
}

onMounted(() => {
  socket.setReconnectEnabled(true)
  document.addEventListener('visibilitychange', onVisibilityChange)
  void loadProductOptions()
  socket.connect()
  nextTick(() => {
    const section = document.querySelector('.device-section')
    if (!section || !tableRef.value) return
    tableResizeObserver = new ResizeObserver(() => {
      tableRef.value?.doLayout()
    })
    tableResizeObserver.observe(section)
  })
})

onUnmounted(() => {
  document.removeEventListener('visibilitychange', onVisibilityChange)
  tableResizeObserver?.disconnect()
  tableResizeObserver = null
  socket.setReconnectEnabled(false)
  pendingDevicesReload = false
  socket.rejectPendingRequests('页面已关闭')
  socket.cleanup()
})
</script>

<style scoped>
.admin-panel {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.content {
  width: 100%;
  max-width: none;
  margin: 0;
  min-width: 0;
  box-sizing: border-box;
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.device-section {
  background: white;
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.device-section :deep(.device-data-table.el-table) {
  width: 100%;
}

.device-section :deep(.device-data-table .el-table__body-wrapper table) {
  table-layout: auto;
  width: auto;
  min-width: 100%;
}

.device-section :deep(.device-data-table th.el-table__cell .cell),
.device-section :deep(.device-data-table td.el-table__cell .cell) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.device-section :deep(.device-data-table td.remark-cell .cell),
.device-section :deep(.device-data-table td.op-cell .cell) {
  overflow: visible;
  text-overflow: clip;
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
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
}

.product-name {
  font-size: var(--table-font-size);
  color: var(--color-text-primary);
  flex-shrink: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-software {
  font-size: 12px;
  color: var(--color-text-tertiary);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.plan-cell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 0;
}

.plan-hint-text {
  font-size: 12px;
  color: var(--color-text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.text-muted {
  color: var(--color-text-tertiary);
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
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.op-btns .el-button {
  flex: 0 0 auto;
  min-width: 0;
  padding: 5px 7px;
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

.card-status-tags {
  display: flex;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px;
}

.clickable-tag {
  cursor: pointer;
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
    grid-template-columns: repeat(2, minmax(0, 1fr));
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

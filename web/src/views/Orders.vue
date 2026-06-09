<template>
  <div class="page-container">
    <main class="page-content">
      <div class="card">
        <div class="card-header">
          <div class="header-meta">
            <h2>订单管理</h2>
          </div>
          <div class="header-actions">
            <el-button @click="loadOrders" :loading="loading">
              <el-icon><Refresh /></el-icon>
              <span>刷新</span>
            </el-button>
          </div>
        </div>

        <div class="summary-row" v-if="summary">
          <div class="summary-item">
            <span class="label">全部</span>
            <span class="value">{{ summary.total }}</span>
          </div>
          <div class="summary-item pending">
            <span class="label">待支付</span>
            <span class="value">{{ summary.pending }}</span>
          </div>
          <div class="summary-item paid">
            <span class="label">已支付</span>
            <span class="value">{{ summary.paid }}</span>
          </div>
          <div class="summary-item test">
            <span class="label">测试单</span>
            <span class="value">{{ summary.test }}</span>
          </div>
        </div>

        <div class="filter-row">
          <el-input
            v-model="keyword"
            placeholder="搜索订单号 / 设备 ID / 产品"
            clearable
            style="width: 240px"
            @keyup.enter="applyFilters"
            @clear="applyFilters"
          />
          <el-select v-model="status" style="width: 120px" @change="applyFilters">
            <el-option label="全部状态" value="" />
            <el-option label="待支付" value="pending" />
            <el-option label="已支付" value="paid" />
          </el-select>
          <el-select v-model="payType" style="width: 120px" @change="applyFilters">
            <el-option label="全部支付" value="" />
            <el-option
              v-for="channel in PAY_CHANNELS"
              :key="channel.value"
              :label="channel.label"
              :value="channel.value"
            />
          </el-select>
          <el-select v-model="testOnly" style="width: 120px" @change="applyFilters">
            <el-option label="全部订单" :value="''" />
            <el-option label="仅正式" :value="false" />
            <el-option label="仅测试" :value="true" />
          </el-select>
          <el-button type="primary" @click="applyFilters">查询</el-button>
        </div>

        <el-table
          :data="orders"
          v-loading="loading"
          row-key="out_trade_no"
          stripe
          border
          class="admin-data-table"
          empty-text="暂无订单"
        >
            <el-table-column prop="out_trade_no" label="商户订单号" min-width="180" show-overflow-tooltip />
            <el-table-column prop="trade_no" label="平台订单号" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ row.trade_no || '-' }}</template>
            </el-table-column>
            <el-table-column prop="device_id" label="设备 ID" min-width="140" show-overflow-tooltip />
            <el-table-column prop="product_name" label="产品" min-width="120">
              <template #default="{ row }">
                <span>{{ row.product_name || '-' }}</span>
                <el-tag v-if="row.is_test" size="small" type="info" style="margin-left: 4px">测试</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="money" label="金额" width="90" align="right">
              <template #default="{ row }">¥{{ row.money }}</template>
            </el-table-column>
            <el-table-column prop="pay_type" label="支付方式" width="100" align="center">
              <template #default="{ row }">{{ payTypeLabel(row.pay_type) }}</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.status === 'paid' ? 'success' : 'warning'" size="small">
                  {{ row.status === 'paid' ? '已支付' : '待支付' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" min-width="160">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column prop="paid_at" label="支付时间" min-width="160">
              <template #default="{ row }">{{ row.paid_at ? formatTime(row.paid_at) : '-' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="150" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
                <el-button
                  v-if="row.status !== 'paid'"
                  link
                  type="warning"
                  size="small"
                  :loading="row._syncing"
                  @click="syncOrder(row)"
                >
                  同步
                </el-button>
              </template>
            </el-table-column>
        </el-table>

        <div class="pagination-wrap">
          <el-pagination
            background
            layout="total, prev, pager, next"
            :total="orderTotal"
            :page-size="pageSize"
            :current-page="page"
            @current-change="onPageChange"
          />
        </div>
      </div>
    </main>

    <el-drawer v-model="detailVisible" title="订单详情" size="420px">
      <template v-if="currentOrder">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="商户订单号">{{ currentOrder.out_trade_no }}</el-descriptions-item>
          <el-descriptions-item label="平台订单号">{{ currentOrder.trade_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="currentOrder.status === 'paid' ? 'success' : 'warning'">
              {{ currentOrder.status === 'paid' ? '已支付' : '待支付' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="类型">
            {{ currentOrder.is_test ? '测试订单' : '正式订单' }}
          </el-descriptions-item>
          <el-descriptions-item label="设备 ID">{{ currentOrder.device_id }}</el-descriptions-item>
          <el-descriptions-item label="产品">{{ currentOrder.product_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="付费档位">{{ currentOrder.plan || '-' }}</el-descriptions-item>
          <el-descriptions-item label="金额">¥{{ currentOrder.money }}</el-descriptions-item>
          <el-descriptions-item label="支付方式">{{ payTypeLabel(currentOrder.pay_type) }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(currentOrder.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="支付时间">
            {{ currentOrder.paid_at ? formatTime(currentOrder.paid_at) : '-' }}
          </el-descriptions-item>
        </el-descriptions>
        <div class="drawer-actions">
          <el-button @click="copyText(currentOrder.out_trade_no)">复制订单号</el-button>
          <el-button
            v-if="currentOrder.status !== 'paid'"
            type="warning"
            :loading="detailSyncing"
            @click="syncCurrentOrder"
          >
            同步支付状态
          </el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { ElMessage } from 'element-plus'
import { reportApiError } from '../utils/errorFeedback'
import { Refresh } from '@element-plus/icons-vue'
import { PAY_CHANNELS, payTypeLabel } from '../constants/payChannels'

const loading = ref(false)
const orders = ref([])
const orderTotal = ref(0)
const page = ref(1)
const pageSize = ref(20)
const status = ref('')
const payType = ref('')
const keyword = ref('')
const testOnly = ref('')
const summary = ref(null)

const detailVisible = ref(false)
const currentOrder = ref(null)
const detailSyncing = ref(false)

const formatTime = (value) => (value ? new Date(value).toLocaleString() : '-')

const loadOrders = async () => {
  loading.value = true
  try {
    const data = await api.getPaymentOrders({
      page: page.value,
      pageSize: pageSize.value,
      status: status.value,
      payType: payType.value,
      keyword: keyword.value,
      testOnly: testOnly.value,
    })
    orders.value = (data.orders || []).map((item) => ({ ...item, _syncing: false }))
    orderTotal.value = data.total || 0
    summary.value = data.summary || null
  } catch (error) {
    if (reportApiError(error, '加载订单失败')) return
  } finally {
    loading.value = false
  }
}

const applyFilters = () => {
  page.value = 1
  loadOrders()
}

const onPageChange = (nextPage) => {
  page.value = nextPage
  loadOrders()
}

const openDetail = (row) => {
  currentOrder.value = { ...row }
  detailVisible.value = true
}

const syncOrder = async (row) => {
  row._syncing = true
  try {
    const updated = await api.syncPaymentOrder(row.out_trade_no)
    Object.assign(row, updated, { _syncing: false })
    if (updated.status === 'paid') {
      ElMessage.success('订单已支付')
      await loadOrders()
    } else {
      ElMessage.info('订单仍为待支付')
    }
  } catch (error) {
    row._syncing = false
    if (reportApiError(error, '同步失败')) return
  }
}

const syncCurrentOrder = async () => {
  if (!currentOrder.value) return
  detailSyncing.value = true
  try {
    const updated = await api.syncPaymentOrder(currentOrder.value.out_trade_no)
    currentOrder.value = { ...updated }
    await loadOrders()
    if (updated.status === 'paid') {
      ElMessage.success('订单已支付')
    } else {
      ElMessage.info('订单仍为待支付')
    }
  } catch (error) {
    if (reportApiError(error, '同步失败')) return
  } finally {
    detailSyncing.value = false
  }
}

const copyText = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

onMounted(loadOrders)
</script>

<style scoped>
.header-meta h2 {
  margin: 0;
  font-size: 16px;
  color: var(--color-text-primary);
}

.header-meta p {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.summary-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.summary-item {
  background: #f5f7fa;
  border-radius: 10px;
  padding: 12px 14px;
}

.summary-item .label {
  display: block;
  font-size: 12px;
  color: #909399;
}

.summary-item .value {
  display: block;
  margin-top: 4px;
  font-size: 22px;
  font-weight: 600;
  color: #303133;
}

.summary-item.pending .value { color: #e6a23c; }
.summary-item.paid .value { color: #67c23a; }
.summary-item.test .value { color: #909399; }

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.pagination-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.drawer-actions {
  margin-top: 16px;
  display: flex;
  gap: 8px;
}

@media (max-width: 768px) {
  .card-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-row {
    flex-direction: column;
  }

  .filter-row .el-input,
  .filter-row .el-select,
  .filter-row .el-button {
    width: 100%;
  }
}
</style>

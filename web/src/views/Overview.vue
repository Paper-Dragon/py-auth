<template>
  <div class="page-container overview-page">
    <main class="page-content overview-content">
      <header class="welcome-card">
        <div class="welcome-text">
          <h2>欢迎，{{ username }}</h2>
          <p>{{ isAdmin ? '查看运行概况，或从下方快捷入口进入各模块' : '管理设备授权，或查阅使用文档' }}</p>
        </div>
      </header>

      <section v-if="isAdmin" class="overview-section" v-loading="loadingStats">
        <h3 class="overview-section-title">数据概览</h3>
        <div class="stats-row">
          <div class="stat-card">
            <div class="stat-icon primary"><el-icon :size="22"><Goods /></el-icon></div>
            <div class="stat-info">
              <span class="stat-value">{{ stats.products }}</span>
              <span class="stat-label">产品</span>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon success"><el-icon :size="22"><Tickets /></el-icon></div>
            <div class="stat-info">
              <span class="stat-value">{{ stats.ordersPaid }}</span>
              <span class="stat-label">已支付订单</span>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon danger"><el-icon :size="22"><Clock /></el-icon></div>
            <div class="stat-info">
              <span class="stat-value">{{ stats.ordersPending }}</span>
              <span class="stat-label">待支付订单</span>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon" :class="stats.epayEnabled ? 'success' : 'danger'">
              <el-icon :size="22"><Wallet /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-value stat-value-text">{{ stats.epayEnabled ? '已启用' : '未启用' }}</span>
              <span class="stat-label">易支付</span>
            </div>
          </div>
        </div>
      </section>

      <section class="overview-section">
        <h3 class="overview-section-title">快捷入口</h3>
        <div class="shortcut-grid">
          <router-link
            v-for="item in visibleShortcuts"
            :key="item.to"
            :to="item.to"
            class="shortcut-card"
          >
            <el-icon :size="28" class="shortcut-icon"><component :is="item.icon" /></el-icon>
            <span class="shortcut-title">{{ item.title }}</span>
            <el-icon class="shortcut-arrow"><ArrowRight /></el-icon>
          </router-link>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  Box, Goods, Tickets, Wallet, Setting, Document, Reading, ArrowRight, Clock,
} from '@element-plus/icons-vue'
import { api } from '../api'
import { reportApiError } from '../utils/errorFeedback'

const username = ref(localStorage.getItem('username') || '管理员')
const isAdmin = ref(localStorage.getItem('isAdmin') === '1')
const loadingStats = ref(false)
const stats = ref({
  products: 0,
  ordersPaid: 0,
  ordersPending: 0,
  epayEnabled: false,
})

const shortcuts = [
  { to: '/devices', title: '设备管理', icon: Box, admin: false },
  { to: '/products', title: '产品管理', icon: Goods, admin: true },
  { to: '/orders', title: '订单管理', icon: Tickets, admin: true },
  { to: '/epay', title: '易支付', icon: Wallet, admin: true },
  { to: '/settings', title: '系统配置', icon: Setting, admin: true },
  { to: '/logs', title: '审计日志', icon: Document, admin: true },
  { to: '/docs', title: '使用文档', icon: Reading, admin: false },
]

const visibleShortcuts = computed(() =>
  shortcuts.filter((item) => !item.admin || isAdmin.value)
)

const loadStats = async () => {
  if (!isAdmin.value) return
  loadingStats.value = true
  try {
    const [products, orders, epay] = await Promise.all([
      api.getProducts(),
      api.getPaymentOrders({ page: 1, pageSize: 1 }),
      api.getEpayConfig(),
    ])
    stats.value.products = Array.isArray(products) ? products.length : 0
    stats.value.ordersPaid = orders?.summary?.paid ?? 0
    stats.value.ordersPending = orders?.summary?.pending ?? 0
    stats.value.epayEnabled = !!epay?.enabled
  } catch (error) {
    if (reportApiError(error, '加载概况失败')) return
  } finally {
    loadingStats.value = false
  }
}

onMounted(async () => {
  try {
    const me = await api.getMe()
    isAdmin.value = !!me?.is_admin
    localStorage.setItem('isAdmin', me?.is_admin ? '1' : '0')
    username.value = me?.username || username.value
  } catch {
    // keep cached flags
  }
  await loadStats()
})
</script>

<style scoped>
.overview-content {
  width: 100%;
  max-width: 1480px;
  margin: 0 auto;
}

.welcome-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border-radius: var(--radius-xl);
  padding: 24px 28px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-md);
}

.welcome-text h2 {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 600;
}

.welcome-text p {
  margin: 0;
  opacity: 0.9;
  font-size: 14px;
  line-height: 1.5;
}

.overview-section {
  margin-bottom: 28px;
}

.overview-section:last-child {
  margin-bottom: 0;
}

.overview-section-title {
  margin: 0 0 14px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.stats-row .stat-value {
  font-size: 24px;
}

.stats-row .stat-value-text {
  font-size: 20px;
}

.shortcut-grid {
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
  gap: 12px;
}

.shortcut-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 64px;
  padding: 16px 18px;
  background: var(--color-bg-primary);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  text-decoration: none;
  color: inherit;
  border: 1px solid transparent;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
}

.shortcut-card:hover {
  border-color: #c6e2ff;
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.shortcut-icon {
  color: #409eff;
  flex-shrink: 0;
}

.shortcut-title {
  flex: 1;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.shortcut-arrow {
  color: #c0c4cc;
  flex-shrink: 0;
}

@media (min-width: 768px) {
  .shortcut-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (min-width: 1024px) {
  .stats-row {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 16px;
  }

  .shortcut-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
  }

  .welcome-card {
    padding: 28px 32px;
  }
}

@media (min-width: 1280px) {
  .overview-content {
    max-width: 100%;
    padding: 0 4px;
  }

  .welcome-card {
    padding: 32px 40px;
    margin-bottom: 32px;
  }

  .welcome-text h2 {
    font-size: 28px;
  }

  .welcome-text p {
    font-size: 15px;
  }

  .overview-section-title {
    font-size: 16px;
    margin-bottom: 16px;
  }

  .stats-row .stat-value {
    font-size: 28px;
  }

  .stats-row .stat-value-text {
    font-size: 22px;
  }

  .shortcut-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 16px;
  }

  .shortcut-card {
    min-height: 76px;
    padding: 20px 22px;
  }

  .shortcut-title {
    font-size: 16px;
  }
}

@media (min-width: 1600px) {
  .overview-content {
    max-width: 1560px;
    margin: 0 auto;
  }

  .stats-row {
    gap: 20px;
  }

  .shortcut-grid {
    gap: 18px;
  }
}

@media (max-width: 480px) {
  .stats-row {
    grid-template-columns: 1fr;
  }
}
</style>

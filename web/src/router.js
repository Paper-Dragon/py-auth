import { createRouter, createWebHistory } from 'vue-router'
import AdminPanel from './components/AdminPanel.vue'
import Settings from './views/Settings.vue'
import Products from './views/Products.vue'
import Orders from './views/Orders.vue'
import Epay from './views/Epay.vue'
import Overview from './views/Overview.vue'
import Users from './views/Users.vue'
import AuditLogs from './views/AuditLogs.vue'
import Docs from './views/Docs.vue'
import LoginForm from './components/LoginForm.vue'
import AdminLayout from './views/AdminLayout.vue'
import Pay from './views/Pay.vue'
import PayResult from './views/PayResult.vue'

const routes = [
  {
    path: '/pay',
    name: 'Pay',
    meta: { title: '在线支付' },
    component: Pay,
  },
  {
    path: '/pay/result',
    name: 'PayResult',
    meta: { title: '支付结果' },
    component: PayResult,
  },
  {
    path: '/login',
    name: 'Login',
    meta: { title: '登录' },
    component: LoginForm,
  },
  {
    path: '/',
    component: AdminLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/overview',
      },
      {
        path: 'overview',
        name: 'Overview',
        meta: { title: '概览' },
        component: Overview,
      },
      {
        path: 'devices',
        name: 'Dashboard',
        meta: { title: '设备管理' },
        component: AdminPanel,
      },
      {
        path: 'products',
        name: 'Products',
        meta: { title: '产品管理', requiresAdmin: true },
        component: Products,
      },
      {
        path: 'orders',
        name: 'Orders',
        meta: { title: '订单管理', requiresAdmin: true },
        component: Orders,
      },
      {
        path: 'epay',
        name: 'Epay',
        meta: { title: '易支付', requiresAdmin: true },
        component: Epay,
      },
      {
        path: 'settings',
        name: 'Settings',
        meta: { title: '系统配置', requiresAdmin: true },
        component: Settings,
      },
      {
        path: 'users',
        name: 'Users',
        meta: { title: '用户管理', requiresAdmin: true },
        component: Users,
      },
      {
        path: 'logs',
        name: 'AuditLogs',
        meta: { title: '审计日志', requiresAdmin: true },
        component: AuditLogs,
      },
      {
        path: 'docs',
        name: 'Docs',
        meta: { title: '使用文档' },
        component: Docs,
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

router.beforeEach((to) => {
  const isLoggedIn = !!localStorage.getItem('authToken')

  if (to.matched.some(record => record.meta.requiresAuth) && !isLoggedIn) {
    return { name: 'Login' }
  }

  if (to.name === 'Login' && isLoggedIn) {
    return { name: 'Overview' }
  }

  if (to.matched.some((record) => record.meta?.requiresAdmin)) {
    const isAdmin = localStorage.getItem('isAdmin') === '1'
    if (!isAdmin) {
      return { name: 'Dashboard' }
    }
  }

  return true
})

const appTitle = '授权管理面板'
router.afterEach((to) => {
  const leaf = [...to.matched].reverse().find((r) => r.meta?.title)
  const section = leaf?.meta?.title
  document.title = section ? `${section} · ${appTitle}` : appTitle
})

export default router

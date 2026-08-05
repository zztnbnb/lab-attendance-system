import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { accessRedirect } from './access'

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean
    admin?: boolean
    title?: string
  }
}

const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true, title: '登录' } },
  { path: '/kiosk/setup', name: 'kiosk-setup', component: () => import('@/views/kiosk/KioskSetupView.vue'), meta: { public: true, title: '终端配对' } },
  { path: '/kiosk', name: 'kiosk', component: () => import('@/views/kiosk/KioskView.vue'), meta: { public: true, title: '人脸打卡' } },
  {
    path: '/',
    component: () => import('@/layouts/AppLayout.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', name: 'dashboard', component: () => import('@/views/user/DashboardView.vue'), meta: { title: '个人首页' } },
      { path: 'attendance', name: 'my-attendance', component: () => import('@/views/user/AttendanceView.vue'), meta: { title: '我的打卡记录' } },
      { path: 'face', name: 'my-face', component: () => import('@/views/user/FaceEnrollmentView.vue'), meta: { title: '人脸录入' } },
      { path: 'profile', name: 'profile', component: () => import('@/views/user/ProfileView.vue'), meta: { title: '个人资料' } },
      { path: 'admin', redirect: '/admin/dashboard', meta: { admin: true } },
      { path: 'admin/dashboard', name: 'admin-dashboard', component: () => import('@/views/admin/AdminDashboardView.vue'), meta: { admin: true, title: '数据总览' } },
      { path: 'admin/users', name: 'admin-users', component: () => import('@/views/admin/UsersView.vue'), meta: { admin: true, title: '用户管理' } },
      { path: 'admin/faces', name: 'admin-faces', component: () => import('@/views/admin/FacesView.vue'), meta: { admin: true, title: '人脸档案' } },
      { path: 'admin/attendance', name: 'admin-attendance', component: () => import('@/views/admin/AdminAttendanceView.vue'), meta: { admin: true, title: '考勤与异常' } },
      { path: 'admin/statistics', name: 'admin-statistics', component: () => import('@/views/admin/StatisticsView.vue'), meta: { admin: true, title: '时长统计' } },
      { path: 'admin/devices', name: 'admin-devices', component: () => import('@/views/admin/DevicesView.vue'), meta: { admin: true, title: '终端管理' } },
      { path: 'admin/audit', name: 'admin-audit', component: () => import('@/views/admin/AuditView.vue'), meta: { admin: true, title: '审计日志' } },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  document.title = `${to.meta.title ?? '实验室打卡'} · LabTime`
  const auth = useAuthStore()
  if (!to.meta.public || to.name === 'login') await auth.initialize()
  const redirect = accessRedirect(to.meta, auth.user?.role ?? null, to.name)
  if (redirect === '/login') return { name: 'login', query: { redirect: to.fullPath } }
  if (redirect) return redirect
  return true
})

export default router

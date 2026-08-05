import { describe, expect, it } from 'vitest'
import { accessRedirect } from '@/router/access'

describe('路由权限判定', () => {
  it('允许未登录用户进入打卡终端', () => {
    expect(accessRedirect({ public: true }, null, 'kiosk')).toBeNull()
  })

  it('将未登录用户送到登录页', () => {
    expect(accessRedirect({}, null, 'dashboard')).toBe('/login')
  })

  it('阻止普通用户进入管理页', () => {
    expect(accessRedirect({ admin: true }, 'USER', 'admin-users')).toBe('/dashboard')
    expect(accessRedirect({ admin: true }, 'ADMIN', 'admin-users')).toBeNull()
  })

  it('已登录用户访问登录页时进入对应首页', () => {
    expect(accessRedirect({ public: true }, 'USER', 'login')).toBe('/dashboard')
    expect(accessRedirect({ public: true }, 'ADMIN', 'login')).toBe('/admin/dashboard')
  })
})

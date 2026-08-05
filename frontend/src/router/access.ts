import type { Role, User } from '@/types'

export interface AccessMeta { public?: boolean; admin?: boolean }
export function accessRedirect(meta: AccessMeta, role: Role | null, routeName?: string | symbol | null): string | null {
  if (routeName === 'login' && role) return role === 'ADMIN' ? '/admin/dashboard' : '/dashboard'
  if (meta.public) return null
  if (!role) return '/login'
  if (meta.admin && role !== 'ADMIN') return '/dashboard'
  return null
}

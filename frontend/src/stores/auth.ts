import { defineStore } from 'pinia'
import axios from 'axios'
import { http, setAccessToken } from '@/api/http'
import type { User } from '@/types'

export const useAuthStore = defineStore('auth', {
  state: () => ({ user: null as User | null, initialized: false, loading: false }),
  getters: {
    isAuthenticated: (state) => Boolean(state.user),
    isAdmin: (state) => state.user?.role === 'ADMIN',
  },
  actions: {
    async login(username: string, password: string) {
      this.loading = true
      try {
        const { data } = await http.post('/auth/login', { username, password })
        setAccessToken(data.access_token)
        this.user = data.user
        this.initialized = true
      } finally { this.loading = false }
    },
    async initialize() {
      if (this.initialized) return
      try {
        const { data } = await axios.post('/api/v1/auth/refresh', {}, { withCredentials: true })
        setAccessToken(data.access_token)
        this.user = data.user
      } catch {
        setAccessToken(null)
        this.user = null
      } finally { this.initialized = true }
    },
    async logout() {
      try { await http.post('/auth/logout') } finally {
        setAccessToken(null)
        this.user = null
        this.initialized = true
      }
    },
  },
})

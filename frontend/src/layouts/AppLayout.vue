<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  Avatar, Camera, DataAnalysis, Document, Fold, House, List, Monitor, Operation,
  Setting, SwitchButton, User, UserFilled, View,
} from '@element-plus/icons-vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const active = computed(() => route.path)
const initials = computed(() => auth.user?.real_name.slice(-2) ?? '用户')

async function logout() {
  await auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="app-shell" :class="{ 'is-collapsed': collapsed }">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand__mark">L</div>
        <div class="brand__text"><strong>LabTime</strong><small>实验室打卡系统</small></div>
      </div>
      <el-menu :default-active="active" router class="side-menu">
        <template v-if="!auth.isAdmin">
          <el-menu-item index="/dashboard"><el-icon><House /></el-icon><span>个人首页</span></el-menu-item>
          <el-menu-item index="/attendance"><el-icon><List /></el-icon><span>打卡记录</span></el-menu-item>
          <el-menu-item index="/face"><el-icon><Camera /></el-icon><span>人脸录入</span></el-menu-item>
          <el-menu-item index="/profile"><el-icon><Setting /></el-icon><span>个人资料</span></el-menu-item>
        </template>
        <template v-else>
          <p class="menu-label">管理</p>
          <el-menu-item index="/admin/dashboard"><el-icon><DataAnalysis /></el-icon><span>数据总览</span></el-menu-item>
          <el-menu-item index="/admin/users"><el-icon><UserFilled /></el-icon><span>用户管理</span></el-menu-item>
          <el-menu-item index="/admin/faces"><el-icon><View /></el-icon><span>人脸档案</span></el-menu-item>
          <el-menu-item index="/admin/attendance"><el-icon><Operation /></el-icon><span>考勤与异常</span></el-menu-item>
          <el-menu-item index="/admin/statistics"><el-icon><DataAnalysis /></el-icon><span>时长统计</span></el-menu-item>
          <el-menu-item index="/admin/devices"><el-icon><Monitor /></el-icon><span>终端管理</span></el-menu-item>
          <el-menu-item index="/admin/audit"><el-icon><Document /></el-icon><span>审计日志</span></el-menu-item>
        </template>
      </el-menu>
      <a href="/kiosk" target="_blank" rel="noopener" class="kiosk-link"><el-icon><Monitor /></el-icon><span>打开打卡台</span></a>
    </aside>
    <div class="main-column">
      <header class="topbar">
        <button class="icon-button" aria-label="折叠菜单" @click="collapsed = !collapsed"><el-icon><Fold /></el-icon></button>
        <div class="topbar__right">
          <div class="user-chip">
            <el-avatar :size="36">{{ initials }}</el-avatar>
            <div><strong>{{ auth.user?.real_name }}</strong><small>{{ auth.isAdmin ? '管理员' : auth.user?.identifier || '普通用户' }}</small></div>
          </div>
          <el-tooltip content="退出登录"><button class="icon-button" @click="logout"><el-icon><SwitchButton /></el-icon></button></el-tooltip>
        </div>
      </header>
      <main class="page-content"><router-view /></main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import { useAuthStore } from '@/stores/auth'
import { http, errorMessage } from '@/api/http'

const auth = useAuthStore()
const form = reactive({ current_password: '', new_password: '', confirm: '' })
const busy = ref(false)
async function changePassword() {
  if (form.new_password !== form.confirm) return ElMessage.warning('两次输入的新密码不一致')
  busy.value = true
  try {
    await http.post('/auth/change-password', { current_password: form.current_password, new_password: form.new_password })
    ElMessage.success('密码已修改，请重新登录')
    await auth.logout(); window.location.href = '/login'
  } catch (err) { ElMessage.error(errorMessage(err)) }
  finally { busy.value = false }
}
</script>

<template>
  <PageHeader title="个人资料" description="查看账号资料并维护登录密码。" />
  <div class="profile-grid">
    <section class="panel">
      <div class="profile-hero"><el-avatar :size="72">{{ auth.user?.real_name.slice(-2) }}</el-avatar><div><h2>{{ auth.user?.real_name }}</h2><p>@{{ auth.user?.username }}</p></div></div>
      <div class="info-rows"><div><span>学号 / 工号</span><b>{{ auth.user?.identifier || '未设置' }}</b></div><div><span>账号角色</span><b>{{ auth.user?.role === 'ADMIN' ? '管理员' : '普通用户' }}</b></div><div><span>账号状态</span><b class="success">正常</b></div></div>
    </section>
    <section class="panel">
      <div class="panel__header"><h2>修改密码</h2></div>
      <el-form class="password-form" label-position="top" @submit.prevent="changePassword">
        <el-form-item label="当前密码"><el-input v-model="form.current_password" type="password" show-password autocomplete="current-password" /></el-form-item>
        <el-form-item label="新密码"><el-input v-model="form.new_password" type="password" show-password autocomplete="new-password" /></el-form-item>
        <el-form-item label="确认新密码"><el-input v-model="form.confirm" type="password" show-password autocomplete="new-password" /></el-form-item>
        <el-button type="primary" native-type="submit" :loading="busy">保存新密码</el-button>
      </el-form>
    </section>
  </div>
</template>

<style scoped>
.profile-grid { max-width: 900px; display: grid; grid-template-columns: 1fr 1.15fr; gap: 18px; }
.profile-hero { display: flex; align-items: center; gap: 18px; padding: 26px; background: linear-gradient(120deg, #edf2ff, #fff0f8); }
.profile-hero .el-avatar { color: white; background: linear-gradient(135deg, #5b7cff, #f15ca8); font-size: 21px; }.profile-hero h2 { margin: 0; }.profile-hero p { margin: 7px 0 0; color: #7d7f9d; }
.info-rows { padding: 8px 24px 20px; }.info-rows div { display: flex; justify-content: space-between; padding: 15px 0; border-bottom: 1px solid #efedf8; font-size: 13px; }.info-rows span { color: #80829e; }.success { color: #626cf0; }
.password-form { padding: 22px; }
@media (max-width: 760px) { .profile-grid { grid-template-columns: 1fr; } }
</style>

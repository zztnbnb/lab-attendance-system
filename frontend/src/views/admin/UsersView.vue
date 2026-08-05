<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import { http, errorMessage } from '@/api/http'
import type { Page, Role, User } from '@/types'
import { formatDateTime } from '@/utils/format'

const loading = ref(false)
const query = ref('')
const page = ref(1)
const result = ref<Page<User>>({ items: [], total: 0, page: 1, page_size: 20 })
const dialog = ref(false)
const editing = ref<User | null>(null)
const form = reactive({ username: '', real_name: '', identifier: '', password: '', role: 'USER' as Role, is_active: true })

function validateForm() {
  form.username = form.username.trim()
  form.real_name = form.real_name.trim()
  form.identifier = form.identifier.trim()
  if (!editing.value && !/^[A-Za-z0-9_.-]{3,64}$/.test(form.username)) {
    ElMessage.warning('账号需为 3–64 位，只能包含字母、数字、点、下划线或短横线')
    return false
  }
  if (!form.real_name) {
    ElMessage.warning('请输入真实姓名')
    return false
  }
  if (!editing.value && form.password.length < 10) {
    ElMessage.warning('初始密码至少需要 10 位')
    return false
  }
  return true
}

async function load() {
  loading.value = true
  try { result.value = (await http.get('/admin/users', { params: { q: query.value || undefined, page: page.value, page_size: 20 } })).data }
  catch (err) { ElMessage.error(errorMessage(err)) }
  finally { loading.value = false }
}
function openCreate() { editing.value = null; Object.assign(form, { username: '', real_name: '', identifier: '', password: '', role: 'USER', is_active: true }); dialog.value = true }
function openEdit(user: User) { editing.value = user; Object.assign(form, { username: user.username, real_name: user.real_name, identifier: user.identifier ?? '', password: '', role: user.role, is_active: user.is_active }); dialog.value = true }
async function save() {
  if (!validateForm()) return
  try {
    if (editing.value) await http.patch(`/admin/users/${editing.value.id}`, { real_name: form.real_name, identifier: form.identifier || null, role: form.role, is_active: form.is_active })
    else await http.post('/admin/users', { username: form.username, real_name: form.real_name, identifier: form.identifier || null, password: form.password, role: form.role })
    ElMessage.success(editing.value ? '用户资料已更新' : '用户已创建'); dialog.value = false; await load()
  } catch (err) { ElMessage.error(errorMessage(err)) }
}
async function toggle(user: User) {
  try { await http.patch(`/admin/users/${user.id}`, { is_active: !user.is_active }); ElMessage.success(user.is_active ? '账号已停用' : '账号已启用'); await load() }
  catch (err) { ElMessage.error(errorMessage(err)) }
}
async function resetPassword(user: User) {
  try {
    const { value } = await ElMessageBox.prompt(`为 ${user.real_name} 设置新密码`, '重置密码', { inputType: 'password', inputPattern: /^.{8,}$/, inputErrorMessage: '密码至少 8 位', confirmButtonText: '确认重置' })
    await http.post(`/admin/users/${user.id}/reset-password`, { new_password: value }); ElMessage.success('密码已重置')
  } catch (err) { if (err !== 'cancel' && err !== 'close') ElMessage.error(errorMessage(err)) }
}
onMounted(load)
</script>

<template>
  <PageHeader title="用户管理" description="账号由管理员统一创建；普通用户无公共注册入口。"><el-button type="primary" :icon="Plus" @click="openCreate">创建用户</el-button></PageHeader>
  <section class="panel"><div class="panel__body">
    <div class="toolbar"><el-input v-model="query" :prefix-icon="Search" clearable placeholder="搜索姓名、账号或学号" @keyup.enter="page = 1; load()" /><el-button @click="page = 1; load()">搜索</el-button></div>
    <el-table v-loading="loading" :data="result.items"><el-table-column prop="real_name" label="姓名" min-width="110" /><el-table-column prop="username" label="账号" min-width="120" /><el-table-column prop="identifier" label="学号 / 工号" min-width="130"><template #default="{ row }">{{ row.identifier || '—' }}</template></el-table-column><el-table-column label="角色" width="100"><template #default="{ row }"><el-tag :type="row.role === 'ADMIN' ? 'danger' : 'info'">{{ row.role === 'ADMIN' ? '管理员' : '用户' }}</el-tag></template></el-table-column><el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag></template></el-table-column><el-table-column label="创建时间" min-width="165"><template #default="{ row }">{{ formatDateTime(row.created_at) }}</template></el-table-column><el-table-column label="操作" min-width="225" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-button link @click="resetPassword(row)">重置密码</el-button><el-button link :type="row.is_active ? 'danger' : 'success'" @click="toggle(row)">{{ row.is_active ? '停用' : '启用' }}</el-button></template></el-table-column></el-table>
    <el-pagination v-if="result.total > 20" v-model:current-page="page" :page-size="20" :total="result.total" layout="prev, pager, next, total" class="pagination" @current-change="load" />
  </div></section>
  <el-dialog v-model="dialog" :title="editing ? '编辑用户' : '创建用户'" width="min(520px, 92vw)"><el-form label-position="top"><el-form-item label="账号"><el-input v-model="form.username" :disabled="!!editing" /></el-form-item><el-form-item label="真实姓名"><el-input v-model="form.real_name" /></el-form-item><el-form-item label="学号 / 工号"><el-input v-model="form.identifier" /></el-form-item><el-form-item v-if="!editing" label="初始密码"><el-input v-model="form.password" type="password" show-password /></el-form-item><el-form-item label="角色"><el-radio-group v-model="form.role"><el-radio-button value="USER">普通用户</el-radio-button><el-radio-button value="ADMIN">管理员</el-radio-button></el-radio-group></el-form-item><el-form-item v-if="editing" label="账号状态"><el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" /></el-form-item></el-form><template #footer><el-button @click="dialog = false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template></el-dialog>
</template>

<style scoped>.pagination { justify-content: flex-end; margin-top: 20px; }</style>

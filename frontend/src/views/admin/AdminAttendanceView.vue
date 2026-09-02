<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { http, errorMessage } from '@/api/http'
import type { AttendanceSession, AttendanceStatus, Page, User } from '@/types'
import { formatDateTime, formatDuration } from '@/utils/format'

const loading = ref(false)
const status = ref<AttendanceStatus | ''>('')
const dates = ref<[Date, Date] | null>(null)
const page = ref(1)
const result = ref<Page<AttendanceSession>>({ items: [], total: 0, page: 1, page_size: 20 })
const correctionDialog = ref(false)
const current = ref<AttendanceSession | null>(null)
const correction = reactive({ check_out_at: '', reason: '' })
const manualDialog = ref(false)
const manualSaving = ref(false)
const users = ref<User[]>([])
const manual = reactive({ user_id: '', check_in_at: '', check_out_at: '', reason: '' })

async function load() {
  loading.value = true
  try { result.value = (await http.get('/admin/attendance-sessions', { params: { status: status.value || undefined, start_at: dates.value?.[0]?.toISOString(), end_at: dates.value?.[1]?.toISOString(), page: page.value, page_size: 20 } })).data }
  catch (err) { ElMessage.error(errorMessage(err)) }
  finally { loading.value = false }
}
async function loadUsers() {
  try { users.value = (await http.get('/admin/users', { params: { page_size: 200 } })).data.items }
  catch (err) { ElMessage.error(errorMessage(err, '用户列表加载失败')) }
}
function openManual() {
  const end = dayjs()
  Object.assign(manual, { user_id: '', check_in_at: end.subtract(1, 'hour').format('YYYY-MM-DDTHH:mm'), check_out_at: end.format('YYYY-MM-DDTHH:mm'), reason: '' })
  manualDialog.value = true
}
async function saveManual() {
  if (!manual.user_id || !manual.check_in_at || manual.reason.trim().length < 2) {
    ElMessage.warning('请选择用户、填写签到时间和补签原因')
    return
  }
  manualSaving.value = true
  try {
    await http.post('/admin/attendance-sessions/manual', {
      user_id: manual.user_id,
      check_in_at: new Date(manual.check_in_at).toISOString(),
      check_out_at: manual.check_out_at ? new Date(manual.check_out_at).toISOString() : null,
      reason: manual.reason.trim(),
    })
    ElMessage.success(manual.check_out_at ? '补签签到和签退已保存' : '补签签到已保存')
    manualDialog.value = false
    await load()
  } catch (err) { ElMessage.error(errorMessage(err, '补签失败')) }
  finally { manualSaving.value = false }
}
function openCorrection(row: AttendanceSession) { current.value = row; correction.check_out_at = dayjs().format('YYYY-MM-DDTHH:mm'); correction.reason = ''; correctionDialog.value = true }
async function saveCorrection() {
  if (!current.value) return
  try { await http.post(`/admin/attendance-sessions/${current.value.id}/correct`, { check_out_at: new Date(correction.check_out_at).toISOString(), reason: correction.reason }); ElMessage.success('记录已修正并重新计算时长'); correctionDialog.value = false; await load() }
  catch (err) { ElMessage.error(errorMessage(err)) }
}
async function invalidate(row: AttendanceSession) {
  try { const { value } = await ElMessageBox.prompt('请输入作废原因', '作废考勤记录', { inputPattern: /^.{2,500}$/, inputErrorMessage: '原因至少 2 个字符', type: 'warning' }); await http.post(`/admin/attendance-sessions/${row.id}/invalidate`, { reason: value }); ElMessage.success('记录已作废'); await load() }
  catch (err) { if (err !== 'cancel' && err !== 'close') ElMessage.error(errorMessage(err)) }
}
onMounted(() => { load(); loadUsers() })
</script>

<template>
  <PageHeader title="考勤与异常" description="处理漏签退、错误记录；所有修正都会写入审计日志。"><el-button type="primary" @click="openManual">补签打卡</el-button></PageHeader>
  <section class="panel"><div class="panel__body">
    <div class="toolbar"><el-select v-model="status" clearable placeholder="全部状态" style="width:170px"><el-option label="在实验室" value="OPEN" /><el-option label="已完成" value="CLOSED" /><el-option label="漏签退" value="MISSING_CHECKOUT" /><el-option label="已作废" value="INVALID" /></el-select><el-date-picker v-model="dates" type="datetimerange" start-placeholder="开始时间" end-placeholder="结束时间" /><el-button type="primary" @click="page = 1; load()">查询</el-button></div>
    <el-table v-loading="loading" :data="result.items"><el-table-column prop="user_name" label="姓名" min-width="100" /><el-table-column prop="username" label="账号" min-width="110" /><el-table-column label="签到时间" min-width="170"><template #default="{ row }">{{ formatDateTime(row.check_in_at) }}</template></el-table-column><el-table-column label="签退时间" min-width="170"><template #default="{ row }">{{ formatDateTime(row.check_out_at) }}</template></el-table-column><el-table-column label="有效时长" min-width="115"><template #default="{ row }">{{ row.duration_seconds == null ? '—' : formatDuration(row.duration_seconds) }}</template></el-table-column><el-table-column label="状态" width="110"><template #default="{ row }"><StatusTag :status="row.status" /></template></el-table-column><el-table-column label="操作" min-width="165" fixed="right"><template #default="{ row }"><el-button v-if="row.status !== 'INVALID'" link type="primary" @click="openCorrection(row)">补充签退</el-button><el-button v-if="row.status !== 'INVALID'" link type="danger" @click="invalidate(row)">作废</el-button><span v-else class="muted">已处理</span></template></el-table-column></el-table>
    <el-pagination v-if="result.total > 20" v-model:current-page="page" :page-size="20" :total="result.total" layout="prev, pager, next, total" class="pagination" @current-change="load" />
  </div></section>
  <el-dialog v-model="correctionDialog" title="补充真实签退时间" width="min(480px, 92vw)"><el-alert title="请依据真实情况填写。修正后记录将计入正式时长。" type="warning" :closable="false" class="form-alert" /><el-form label-position="top"><el-form-item label="原签到时间"><el-input :model-value="formatDateTime(current?.check_in_at)" disabled /></el-form-item><el-form-item label="实际签退时间"><el-input v-model="correction.check_out_at" type="datetime-local" /></el-form-item><el-form-item label="修正原因"><el-input v-model="correction.reason" type="textarea" :rows="3" placeholder="必填，至少 2 个字符" /></el-form-item></el-form><template #footer><el-button @click="correctionDialog = false">取消</el-button><el-button type="primary" @click="saveCorrection">确认修正</el-button></template></el-dialog>
  <el-dialog v-model="manualDialog" title="管理员补签打卡" width="min(520px, 92vw)">
    <el-alert title="补签记录会标记为管理员修正，并记录操作原因。时间按服务器时间校验。" type="warning" :closable="false" class="form-alert" />
    <el-form label-position="top">
      <el-form-item label="用户">
        <el-select v-model="manual.user_id" filterable placeholder="选择需要补签的用户" style="width: 100%">
          <el-option v-for="user in users" :key="user.id" :label="`${user.real_name} · ${user.username}`" :value="user.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="实际签到时间"><el-input v-model="manual.check_in_at" type="datetime-local" /></el-form-item>
      <el-form-item label="实际签退时间（可留空，表示仍在实验室）"><el-input v-model="manual.check_out_at" type="datetime-local" /></el-form-item>
      <el-form-item label="补签原因"><el-input v-model="manual.reason" type="textarea" :rows="3" placeholder="例如：摄像头故障，核对门禁记录后补签" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="manualDialog = false">取消</el-button><el-button type="primary" :loading="manualSaving" @click="saveManual">确认补签</el-button></template>
  </el-dialog>
</template>

<style scoped>.pagination { justify-content: flex-end; margin-top: 20px; }.muted { color: #98a49f; }.form-alert { margin-bottom: 18px; }</style>

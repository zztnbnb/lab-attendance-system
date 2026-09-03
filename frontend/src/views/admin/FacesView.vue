<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Camera, CircleCheck, Plus } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { http, errorMessage } from '@/api/http'
import { useCamera } from '@/composables/useCamera'
import type { FaceProfile, FaceProfileStatus, Page, User } from '@/types'
import { formatDateTime } from '@/utils/format'

const loading = ref(false)
const statusFilter = ref<FaceProfileStatus | ''>('')
const result = ref<Page<FaceProfile>>({ items: [], total: 0, page: 1, page_size: 20 })
const users = ref<User[]>([])
const captureDialog = ref(false)
const captureMode = ref<'enroll' | 'verify'>('enroll')
const selectedUser = ref('')
const selectedProfile = ref<FaceProfile | null>(null)
const video = ref<HTMLVideoElement | null>(null)
const { start, stop, captureSequence } = useCamera(video)
const enrollmentId = ref<string | null>(null)
const templateCount = ref(0)
const busy = ref(false)
const verified = ref(false)

async function load() {
  loading.value = true
  try { result.value = (await http.get('/admin/face-profiles', { params: { status: statusFilter.value || undefined, page_size: 100 } })).data }
  catch (err) { ElMessage.error(errorMessage(err)) }
  finally { loading.value = false }
}
async function loadUsers() { users.value = (await http.get('/admin/users', { params: { page_size: 200 } })).data.items.filter((item: User) => item.is_active) }
async function openEnroll() { captureMode.value = 'enroll'; selectedUser.value = ''; selectedProfile.value = null; enrollmentId.value = null; templateCount.value = 0; captureDialog.value = true; await nextTick(); await enableCamera() }
async function openVerify(profile: FaceProfile) { captureMode.value = 'verify'; selectedProfile.value = profile; verified.value = false; captureDialog.value = true; await nextTick(); await enableCamera() }
async function enableCamera() { try { await start() } catch (err) { ElMessage.error(errorMessage(err, '无法访问摄像头')) } }
function closeCapture() { stop(); captureDialog.value = false; enrollmentId.value = null }
async function createEnrollment() {
  if (!selectedUser.value) return ElMessage.warning('请先选择用户')
  busy.value = true
  try { const { data } = await http.post('/face/enrollment-sessions', { target_user_id: selectedUser.value, mode: 'ADMIN' }); enrollmentId.value = data.id; ElMessage.success('录入会话已创建') }
  catch (err) { ElMessage.error(errorMessage(err)) }
  finally { busy.value = false }
}
async function collectFrames() {
  if (!enrollmentId.value) return
  busy.value = true
  try {
    const frames = await captureSequence(5, 420); const form = new FormData(); frames.forEach((frame, i) => form.append('files', frame, `frame-${i}.jpg`))
    const { data } = await http.post(`/face/enrollment-sessions/${enrollmentId.value}/frames`, form); templateCount.value = data.template_count; ElMessage.success(`成功采集 ${data.accepted} 帧`)
  } catch (err) { ElMessage.error(errorMessage(err)) }
  finally { busy.value = false }
}
async function activateEnrollment() {
  if (!enrollmentId.value) return
  busy.value = true
  try { await http.post(`/face/enrollment-sessions/${enrollmentId.value}/submit`); ElMessage.success('人脸档案已直接激活'); closeCapture(); await load() }
  catch (err) { ElMessage.error(errorMessage(err)) }
  finally { busy.value = false }
}
async function liveVerify() {
  if (!selectedProfile.value) return
  busy.value = true
  try {
    const frames = await captureSequence(5, 420); const form = new FormData(); frames.forEach((frame, i) => form.append('files', frame, `verify-${i}.jpg`))
    const { data } = await http.post(`/admin/face-profiles/${selectedProfile.value.id}/live-verify`, form); verified.value = data.verified
    data.verified ? ElMessage.success(`现场复验通过，相似度 ${data.score.toFixed(3)}`) : ElMessage.error(`复验未通过，相似度 ${data.score.toFixed(3)}`)
  } catch (err) { ElMessage.error(errorMessage(err)) }
  finally { busy.value = false }
}
async function approve() {
  if (!selectedProfile.value) return
  busy.value = true
  try { await http.post(`/admin/face-profiles/${selectedProfile.value.id}/approve`); ElMessage.success('档案已批准并激活'); closeCapture(); await load() }
  catch (err) { ElMessage.error(errorMessage(err)) }
  finally { busy.value = false }
}
async function reject(profile: FaceProfile) {
  try { const { value } = await ElMessageBox.prompt('请输入拒绝原因', `拒绝 ${profile.user_name} 的档案`, { inputPattern: /^.{2,500}$/, inputErrorMessage: '原因至少 2 个字符' }); await http.post(`/admin/face-profiles/${profile.id}/reject`, { reason: value }); ElMessage.success('档案已拒绝'); await load() }
  catch (err) { if (err !== 'cancel' && err !== 'close') ElMessage.error(errorMessage(err)) }
}
async function revoke(profile: FaceProfile) {
  try { await ElMessageBox.confirm(`撤销 ${profile.user_name} 当前的人脸档案后将无法打卡，是否继续？`, '撤销确认', { type: 'warning' }); await http.post(`/admin/face-profiles/${profile.id}/revoke`); ElMessage.success('档案已撤销'); await load() }
  catch (err) { if (err !== 'cancel' && err !== 'close') ElMessage.error(errorMessage(err)) }
}
onMounted(async () => { await Promise.all([load(), loadUsers()]) })
</script>

<template>
  <PageHeader title="人脸档案" description="用户提交采集后自动激活；管理员仍可监督录入，并处理历史待审批档案。"><el-button type="primary" :icon="Plus" @click="openEnroll">监督录入</el-button></PageHeader>
  <section class="panel"><div class="panel__body">
    <div class="toolbar"><el-select v-model="statusFilter" clearable placeholder="全部状态" style="width:180px" @change="load"><el-option label="待审批" value="PENDING" /><el-option label="已激活" value="ACTIVE" /><el-option label="已拒绝" value="REJECTED" /><el-option label="已替换" value="REPLACED" /><el-option label="已撤销" value="REVOKED" /></el-select><el-button @click="load">刷新</el-button></div>
    <el-table v-loading="loading" :data="result.items"><el-table-column prop="user_name" label="姓名" min-width="110" /><el-table-column prop="username" label="账号" min-width="120" /><el-table-column label="状态" width="105"><template #default="{ row }"><StatusTag :status="row.status" /></template></el-table-column><el-table-column label="来源" width="100"><template #default="{ row }">{{ row.mode === 'ADMIN' ? '监督录入' : '用户自助' }}</template></el-table-column><el-table-column prop="template_count" label="模板" width="75" /><el-table-column label="质量 / 活体" min-width="130"><template #default="{ row }">{{ row.quality_score?.toFixed(2) ?? '—' }} / {{ row.liveness_score?.toFixed(2) ?? '—' }}</template></el-table-column><el-table-column label="提交时间" min-width="165"><template #default="{ row }">{{ formatDateTime(row.submitted_at || row.created_at) }}</template></el-table-column><el-table-column label="操作" min-width="180" fixed="right"><template #default="{ row }"><el-button v-if="row.status === 'PENDING'" link type="primary" @click="openVerify(row)">现场复验</el-button><el-button v-if="row.status === 'PENDING'" link type="danger" @click="reject(row)">拒绝</el-button><el-button v-if="row.status === 'ACTIVE'" link type="danger" @click="revoke(row)">撤销</el-button><span v-if="!['PENDING','ACTIVE'].includes(row.status)" class="muted">无需操作</span></template></el-table-column></el-table>
  </div></section>
  <el-dialog v-model="captureDialog" :title="captureMode === 'enroll' ? '管理员监督录入' : `现场复验 · ${selectedProfile?.user_name}`" width="min(720px, 94vw)" :close-on-click-modal="false" @closed="stop">
    <el-alert v-if="captureMode === 'verify'" title="请确认镜头前是本人。复验通过后，批准按钮在 15 分钟内有效。" type="warning" :closable="false" show-icon class="dialog-alert" />
    <el-form-item v-if="captureMode === 'enroll' && !enrollmentId" label="选择用户"><el-select v-model="selectedUser" filterable placeholder="按姓名或账号选择" style="width:100%"><el-option v-for="user in users" :key="user.id" :value="user.id" :label="`${user.real_name} · ${user.username}`" /></el-select></el-form-item>
    <div class="camera-stage"><video ref="video" muted playsinline /><div class="camera-guide" /><div class="camera-tip">正对镜头，保持静止并确保只有本人入镜</div></div>
    <el-progress v-if="captureMode === 'enroll' && enrollmentId" :percentage="Math.min(100, templateCount * 20)" :stroke-width="8" class="capture-progress" />
    <el-alert v-if="verified" title="实时人脸与待审批模板匹配，允许批准" type="success" :closable="false" show-icon class="dialog-alert" />
    <template #footer><el-button @click="closeCapture">取消</el-button><template v-if="captureMode === 'enroll'"><el-button v-if="!enrollmentId" type="primary" :loading="busy" @click="createEnrollment">创建会话</el-button><el-button v-else type="primary" :icon="Camera" :loading="busy" @click="collectFrames">采集 5 帧</el-button><el-button v-if="enrollmentId" :icon="CircleCheck" :disabled="templateCount < 3" @click="activateEnrollment">提交并激活</el-button></template><template v-else><el-button type="primary" :icon="Camera" :loading="busy" @click="liveVerify">采集并复验</el-button><el-button type="success" :disabled="!verified" @click="approve">批准激活</el-button></template></template>
  </el-dialog>
</template>

<style scoped>.muted { color: #94a19c; font-size: 12px; }.dialog-alert, .capture-progress { margin: 14px 0; }</style>

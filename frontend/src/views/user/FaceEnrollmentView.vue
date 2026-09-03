<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Camera, CircleCheck } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { http, errorMessage } from '@/api/http'
import { useCamera } from '@/composables/useCamera'
import type { FaceProfile } from '@/types'
import { formatDateTime } from '@/utils/format'

const video = ref<HTMLVideoElement | null>(null)
const { start, stop, captureSequence } = useCamera(video)
const profiles = ref<FaceProfile[]>([])
const enrollmentId = ref<string | null>(null)
const templateCount = ref(0)
const cameraReady = ref(false)
const busy = ref(false)

async function load() { profiles.value = (await http.get('/me/face-profile')).data }
async function enableCamera() {
  try { await start(); cameraReady.value = true }
  catch (err) { ElMessage.error(errorMessage(err, '无法访问摄像头，请检查浏览器权限与 HTTPS')) }
}
async function begin() {
  busy.value = true
  try {
    if (!cameraReady.value) await enableCamera()
    const { data } = await http.post('/face/enrollment-sessions', { mode: 'SELF' })
    enrollmentId.value = data.id
    templateCount.value = 0
    ElMessage.success('录入会话已创建，请保持画面中只有本人')
  } catch (err) { ElMessage.error(errorMessage(err)) }
  finally { busy.value = false }
}
async function capture() {
  if (!enrollmentId.value) return
  busy.value = true
  try {
    const frames = await captureSequence(5, 420)
    const form = new FormData()
    frames.forEach((frame, i) => form.append('files', frame, `frame-${i}.jpg`))
    const { data } = await http.post(`/face/enrollment-sessions/${enrollmentId.value}/frames`, form)
    templateCount.value = data.template_count
    ElMessage.success(`已接受 ${data.accepted} 帧，当前共有 ${data.template_count} 个模板`)
  } catch (err) { ElMessage.error(errorMessage(err, '采集失败')) }
  finally { busy.value = false }
}
async function submit() {
  if (!enrollmentId.value) return
  busy.value = true
  try {
    await http.post(`/face/enrollment-sessions/${enrollmentId.value}/submit`)
    enrollmentId.value = null; templateCount.value = 0; stop(); cameraReady.value = false
    ElMessage.success('已提交，管理员现场复验后生效')
    await load()
  } catch (err) { ElMessage.error(errorMessage(err, '提交失败')) }
  finally { busy.value = false }
}
onMounted(load)
</script>

<template>
  <PageHeader title="人脸录入" description="自助录入会生成待审批档案；激活前需由管理员现场复验。静态保持正面即可完成采集。" />
  <div class="enrollment-grid">
    <section class="panel">
      <div class="panel__header"><h2>现场采集</h2><span class="secure-label">画面不保存</span></div>
      <div class="panel__body">
        <div class="camera-stage">
          <video ref="video" muted playsinline />
          <div class="camera-guide" />
          <div class="camera-tip">{{ cameraReady ? '请正对镜头，保持静止并确保只有本人入镜' : '启用摄像头开始录入' }}</div>
        </div>
        <el-progress v-if="enrollmentId" :percentage="Math.min(100, templateCount * 20)" :stroke-width="8" class="capture-progress" />
        <div class="capture-actions">
          <el-button v-if="!enrollmentId" type="primary" :loading="busy" :icon="Camera" @click="begin">开始新录入</el-button>
          <template v-else>
            <el-button type="primary" :loading="busy" :icon="Camera" @click="capture">采集 5 帧</el-button>
            <el-button :disabled="templateCount < 3" :icon="CircleCheck" @click="submit">提交审批</el-button>
          </template>
        </div>
        <ul class="capture-rules"><li>光线均匀，摘下口罩、帽子和深色眼镜</li><li>画面中只能出现一张人脸</li><li>保持正面静止，脸部位于取景框中央</li><li>提交后请与管理员约定现场复验</li></ul>
      </div>
    </section>
    <section class="panel">
      <div class="panel__header"><h2>我的人脸档案</h2></div>
      <div class="profile-list">
        <div v-for="profile in profiles" :key="profile.id" class="profile-item">
          <div class="profile-item__top"><StatusTag :status="profile.status" /><small>{{ formatDateTime(profile.created_at) }}</small></div>
          <dl><dt>模板数量</dt><dd>{{ profile.template_count }}</dd><dt>平均质量</dt><dd>{{ profile.quality_score?.toFixed(2) ?? '—' }}</dd><dt>模型版本</dt><dd>{{ profile.model_version }}</dd></dl>
          <el-alert v-if="profile.rejection_reason" :title="profile.rejection_reason" type="error" :closable="false" />
        </div>
        <div v-if="!profiles.length" class="empty-hint">尚未录入人脸</div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.enrollment-grid { display: grid; grid-template-columns: minmax(420px, 1.3fr) minmax(310px, .7fr); gap: 18px; }
.secure-label { padding: 5px 10px; border-radius: 999px; color: #626cf0; background: linear-gradient(135deg, #eaf0ff, #ffeaf5); font-size: 11px; }
.capture-progress { margin-top: 18px; }
.capture-actions { display: flex; justify-content: center; gap: 10px; margin-top: 18px; }
.capture-rules { margin: 22px 0 0; padding: 17px 18px 17px 36px; border-radius: 10px; color: #6f7292; background: linear-gradient(135deg, #f5f7ff, #fff4fa); line-height: 1.9; font-size: 12px; }
.profile-list { padding: 4px 20px; }
.profile-item { padding: 18px 0; border-bottom: 1px solid #efedf8; }
.profile-item__top { display: flex; justify-content: space-between; align-items: center; }
.profile-item__top small { color: #85948e; }
.profile-item dl { display: grid; grid-template-columns: 1fr auto; gap: 9px; margin: 16px 0 0; font-size: 12px; }
.profile-item dt { color: #7a8c85; }.profile-item dd { margin: 0; max-width: 180px; overflow: hidden; text-overflow: ellipsis; }
@media (max-width: 900px) { .enrollment-grid { grid-template-columns: 1fr; } }
</style>

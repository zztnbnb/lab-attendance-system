<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Camera, Connection, Refresh, Setting, VideoCamera } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { http, errorMessage } from '@/api/http'
import { useCamera } from '@/composables/useCamera'
import KioskIdentitySignal from './components/KioskIdentitySignal.vue'
import KioskMetricGrid from './components/KioskMetricGrid.vue'
import type {
  AllowedAction,
  AttendanceSession,
  KioskDashboard,
  KioskDevice,
  KioskPresencePage,
  KioskRecordPage,
  RecognitionResult,
  RecognitionSession,
} from '@/types'

type Stage = 'ready' | 'capturing' | 'processing' | 'recognized' | 'success' | 'error'
type Tab = 'recognition' | 'presence' | 'records'

const router = useRouter()
const video = ref<HTMLVideoElement | null>(null)
const { start, stop, captureSequence, refreshDevices, devices, activeDeviceId } = useCamera(video)
const stage = ref<Stage>('ready')
const activeTab = ref<Tab>('recognition')
const session = ref<RecognitionSession | null>(null)
const result = ref<RecognitionResult | null>(null)
const savedAttendance = ref<AttendanceSession | null>(null)
const savedAction = ref<AllowedAction | null>(null)
const device = ref<KioskDevice | null>(null)
const dashboard = ref<KioskDashboard | null>(null)
const presence = ref<KioskPresencePage | null>(null)
const records = ref<KioskRecordPage | null>(null)
const message = ref('请站在取景框内，系统将自动扫描')
const submitting = ref(false)
const cameraBusy = ref(false)
const cameraReady = ref(false)
const loadingData = ref(false)
const mirrorPreview = ref(true)
const actionIdempotencyKey = ref('')
const successCountdown = ref(0)
const frameBytes = ref(0)
const clientRecognitionMs = ref<number | null>(null)
const errorKind = ref<'camera' | 'recognition' | undefined>()
const now = ref(new Date())
const serverOffsetMs = ref(0)
let clockTimer: number | undefined
let refreshTimer: number | undefined
let resetTimer: number | undefined
let autoScanTimer: number | undefined
let scanRunId = 0
const autoScanEnabled = ref(true)

const code = localStorage.getItem('lab_device_code') ?? ''
const secret = localStorage.getItem('lab_device_secret') ?? ''
const deviceHeaders = { 'X-Device-Code': code, 'X-Device-Key': secret }
const isScanning = computed(() => ['capturing', 'processing', 'recognized'].includes(stage.value))
const engineConnected = computed(() => dashboard.value?.engine_status.startsWith('ready') ?? false)
const clock = computed(() => dayjs(new Date(now.value.getTime() + serverOffsetMs.value)).format('HH:mm:ss'))
const date = computed(() => dayjs(new Date(now.value.getTime() + serverOffsetMs.value)).format('YYYY年MM月DD日 dddd')
  .replace('Monday', '星期一').replace('Tuesday', '星期二').replace('Wednesday', '星期三')
  .replace('Thursday', '星期四').replace('Friday', '星期五').replace('Saturday', '星期六').replace('Sunday', '星期日'))
const actionLabel = computed(() => result.value?.allowed_action === 'CHECK_OUT' ? '签退' : result.value?.allowed_action === 'CHECK_IN' ? '签到' : '打卡')
const savedTime = computed(() => {
  const value = savedAction.value === 'CHECK_OUT' ? savedAttendance.value?.check_out_at : savedAttendance.value?.check_in_at
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : ''
})
const uploadSize = computed(() => frameBytes.value ? `${Math.max(1, Math.round(frameBytes.value / 1024))} KB` : '—')
const processingTime = computed(() => result.value?.processing_ms ?? clientRecognitionMs.value)
const verifiedBoxStyle = computed(() => {
  const box = result.value?.face_box
  if (!box) return undefined
  const x = mirrorPreview.value ? 1 - box.x - box.width : box.x
  return { left: `${x * 100}%`, top: `${box.y * 100}%`, width: `${box.width * 100}%`, height: `${box.height * 100}%` }
})
const scanHint = computed(() => {
  if (stage.value === 'capturing') return '正在连续采集 4 帧，请保持正视摄像头'
  if (stage.value === 'processing' || stage.value === 'recognized') return '正在进行质量、活体和身份比对'
  if (stage.value === 'success') return '本次考勤记录已由服务器保存'
  return message.value
})

function resetResult() {
  window.clearInterval(resetTimer)
  successCountdown.value = 0
  stage.value = 'ready'
  result.value = null
  session.value = null
  savedAttendance.value = null
  savedAction.value = null
  actionIdempotencyKey.value = ''
  submitting.value = false
  frameBytes.value = 0
  clientRecognitionMs.value = null
  errorKind.value = undefined
  message.value = autoScanEnabled.value ? '请站在取景框内，系统将自动扫描' : '请站在取景框内，正对摄像头后开始扫描'
}

function scheduleReset() {
  window.clearInterval(resetTimer)
  successCountdown.value = 8
  resetTimer = window.setInterval(() => {
    successCountdown.value -= 1
    if (successCountdown.value <= 0) resetResult()
  }, 1000)
}

async function loadDashboard() {
  const { data } = await http.get<KioskDashboard>('/kiosk/dashboard', { headers: deviceHeaders })
  dashboard.value = data
  device.value = data.device
  serverOffsetMs.value = new Date(data.server_time).getTime() - Date.now()
}

async function loadPresence() {
  const { data } = await http.get<KioskPresencePage>('/kiosk/presence', { headers: deviceHeaders, params: { page_size: 100 } })
  presence.value = data
}

async function loadRecords() {
  const { data } = await http.get<KioskRecordPage>('/kiosk/records', { headers: deviceHeaders, params: { page_size: 30 } })
  records.value = data
}

async function refreshTerminalData(includeTab = true) {
  if (!code || !secret) return
  loadingData.value = true
  try {
    await loadDashboard()
    if (includeTab && activeTab.value === 'presence') await loadPresence()
    if (includeTab && activeTab.value === 'records') await loadRecords()
  } catch (err) {
    if (!device.value) throw err
  } finally {
    loadingData.value = false
  }
}

async function initialize() {
  if (!code || !secret) return router.replace('/kiosk/setup')
  try {
    const { data } = await http.get<KioskDevice>('/kiosk/device', { headers: deviceHeaders })
    device.value = data
    await refreshTerminalData(false)
  } catch {
    return router.replace('/kiosk/setup')
  }
  try {
    await nextTick()
    await refreshDevices()
    await start()
    cameraReady.value = true
    startAutoScan()
  } catch (err) {
    cameraReady.value = false
    stage.value = 'error'
    errorKind.value = 'camera'
    message.value = errorMessage(err, '无法访问摄像头，请检查权限或 HTTPS 配置')
  }
}

function startAutoScan() {
  window.clearInterval(autoScanTimer)
  if (!autoScanEnabled.value) return
  autoScanTimer = window.setInterval(() => {
    if (stage.value === 'ready' && cameraReady.value && !cameraBusy.value) recognize()
  }, 3000)
}

async function restartCamera() {
  if (isScanning.value) {
    ElMessage.warning('请先完成或取消当前扫描')
    return
  }
  cameraBusy.value = true
  try {
    await start(activeDeviceId.value)
    cameraReady.value = true
    message.value = autoScanEnabled.value ? '摄像头已就绪，请站在取景框内，系统将自动扫描' : '摄像头已就绪，可以开始静态扫描'
    startAutoScan()
    if (stage.value === 'error') stage.value = 'ready'
    errorKind.value = undefined
    ElMessage.success('摄像头检测成功')
  } catch (err) {
    cameraReady.value = false
    stage.value = 'error'
    errorKind.value = 'camera'
    message.value = errorMessage(err, '无法启动选中的摄像头')
  } finally {
    cameraBusy.value = false
  }
}

async function selectTab(tab: Tab) {
  activeTab.value = tab
  try {
    if (tab === 'presence') await loadPresence()
    if (tab === 'records') await loadRecords()
  } catch (err) {
    ElMessage.error(errorMessage(err, '终端数据加载失败'))
  }
}

function cancelScan() {
  scanRunId += 1
  if (isScanning.value) {
    stage.value = 'ready'
    session.value = null
    result.value = null
    message.value = '本次扫描已取消，可以重新开始'
  }
}

async function recognize() {
  if (isScanning.value || cameraBusy.value) return
  if (!cameraReady.value) {
    ElMessage.warning('请先检测并连接可用摄像头')
    return
  }
  const runId = ++scanRunId
  resetResult()
  stage.value = 'capturing'
  message.value = '请保持正视摄像头，正在采集画面'
  try {
    session.value = (await http.post<RecognitionSession>('/kiosk/recognition-sessions', {}, { headers: deviceHeaders })).data
    if (runId !== scanRunId) return
    await new Promise((resolve) => window.setTimeout(resolve, 400))
    const frames = await captureSequence(4, 220)
    if (runId !== scanRunId) return
    frameBytes.value = frames.reduce((total, frame) => total + frame.size, 0)
    stage.value = 'processing'
    message.value = '正在进行静态人脸核验与数据库比对'
    const form = new FormData()
    frames.forEach((frame, index) => form.append('files', frame, `recognition-${index}.jpg`))
    const verifyStartedAt = performance.now()
    result.value = (await http.post<RecognitionResult>(`/kiosk/recognition-sessions/${session.value.id}/verify`, form, { headers: deviceHeaders })).data
    clientRecognitionMs.value = Math.max(1, Math.round(performance.now() - verifyStartedAt))
    if (runId !== scanRunId) return
    if (!result.value.recognized) {
      stage.value = 'error'
      errorKind.value = 'recognition'
      message.value = result.value.message
      await refreshTerminalData()
      if (autoScanEnabled.value) window.setTimeout(resetResult, 2500)
      return
    }
    actionIdempotencyKey.value = crypto.randomUUID()
    if (result.value.allowed_action === 'BLOCKED' || !result.value.ticket) {
      stage.value = 'error'
      errorKind.value = 'recognition'
      message.value = result.value.message
      return
    }
    stage.value = 'recognized'
    message.value = `已识别 ${result.value.real_name}，正在自动${result.value.allowed_action === 'CHECK_IN' ? '签到' : '签退'}并保存记录`
    await attend(result.value.allowed_action, runId)
  } catch (err) {
    if (runId !== scanRunId) return
    stage.value = 'error'
    errorKind.value = 'recognition'
    message.value = errorMessage(err, '识别失败，请重新尝试')
    if (autoScanEnabled.value) window.setTimeout(resetResult, 2500)
  }
}

async function attend(action: AllowedAction, runId = scanRunId) {
  if (submitting.value || !result.value?.ticket) return
  submitting.value = true
  stage.value = 'processing'
  try {
    const { data } = await http.post<AttendanceSession>('/kiosk/attendance-actions', {
      ticket: result.value.ticket,
      action,
      idempotency_key: actionIdempotencyKey.value,
    }, { headers: deviceHeaders })
    if (runId !== scanRunId) return
    savedAttendance.value = data
    savedAction.value = action
    stage.value = 'success'
    message.value = `${action === 'CHECK_IN' ? '签到' : '签退'}成功，记录已保存`
    await refreshTerminalData()
    if (activeTab.value === 'presence') await loadPresence()
    if (activeTab.value === 'records') await loadRecords()
    scheduleReset()
  } catch (err) {
    if (runId !== scanRunId) return
    const reason = errorMessage(err, '打卡写入失败')
    const canRetry = !session.value || new Date(session.value.expires_at).getTime() > Date.now()
    stage.value = canRetry ? 'recognized' : 'error'
    if (!canRetry) errorKind.value = 'recognition'
    message.value = canRetry ? `记录尚未保存，可安全重试：${reason}` : reason
  } finally {
    submitting.value = false
  }
}

function openSettings() {
  stop()
  router.push('/kiosk/setup')
}

onMounted(() => {
  initialize()
  clockTimer = window.setInterval(() => { now.value = new Date() }, 1000)
  refreshTimer = window.setInterval(() => { refreshTerminalData().catch(() => undefined) }, 15_000)
})
onBeforeUnmount(() => {
  window.clearInterval(clockTimer)
  window.clearInterval(refreshTimer)
  window.clearInterval(resetTimer)
  window.clearInterval(autoScanTimer)
  stop()
})
</script>

<template>
  <main class="kiosk-page">
    <header class="kiosk-header">
      <div class="kiosk-brand"><span class="brand-mark">L</span><div><strong>LabTime</strong><small>实验室智能打卡终端</small></div></div>
      <nav class="kiosk-nav" aria-label="终端功能">
        <button :class="{ active: activeTab === 'recognition' }" @click="selectTab('recognition')">识别中心</button>
        <button :class="{ active: activeTab === 'presence' }" @click="selectTab('presence')">考勤状态</button>
        <button :class="{ active: activeTab === 'records' }" @click="selectTab('records')">今日记录</button>
      </nav>
      <div class="header-status">
        <span class="status-pill" :class="{ offline: !engineConnected }"><i />{{ engineConnected ? '实时推理已连接' : '识别引擎未连接' }}</span>
        <span class="model-pill">YuNet · SFace</span>
        <button class="settings-button" title="终端设置" @click="openSettings"><el-icon><Setting /></el-icon></button>
      </div>
    </header>

    <section class="kiosk-content">
      <section class="welcome-row">
        <div><p class="eyebrow">LABORATORY ATTENDANCE</p><h1>欢迎使用实验室打卡终端</h1><p>{{ date }} · 服务器时间 {{ clock }}</p></div>
        <KioskMetricGrid
          :current-count="dashboard?.current_count ?? 0"
          :today-checkins="dashboard?.today_checkins ?? 0"
          :today-checkouts="dashboard?.today_checkouts ?? 0"
          :exception-count="dashboard?.exception_count ?? 0"
        />
      </section>

      <section v-if="activeTab === 'recognition'" class="workspace-grid">
        <article class="live-panel">
          <div class="panel-head"><div><p>LIVE RECOGNITION</p><h2>实时识别</h2></div><div class="panel-badges"><span><i :class="{ active: engineConnected }" />{{ engineConnected ? '引擎已连接' : '引擎异常' }}</span><b>静态扫描</b></div></div>
          <div class="camera-shell" :class="`stage-${stage}`">
            <video ref="video" :class="{ mirrored: mirrorPreview }" muted playsinline />
            <div class="camera-vignette" />
            <div class="guide-frame" aria-hidden="true"><i class="corner top-left" /><i class="corner top-right" /><i class="corner bottom-left" /><i class="corner bottom-right" /></div>
            <div v-if="verifiedBoxStyle" class="verified-box" :class="{ failure: stage === 'error' }" :style="verifiedBoxStyle"><span>{{ result?.recognized ? '已匹配' : '未匹配' }}</span></div>
            <div v-if="stage === 'capturing' || stage === 'processing'" class="scan-line" />
            <div class="camera-label"><span>{{ !cameraReady ? 'CAMERA OFFLINE' : stage === 'ready' ? 'READY' : stage === 'capturing' ? 'CAPTURING' : stage === 'processing' ? 'SCANNING' : stage === 'success' ? 'SAVED' : 'RESULT' }}</span><small>{{ processingTime ? `${processingTime} ms` : cameraReady ? '等待扫描' : '等待连接' }}</small></div>
            <div class="camera-telemetry"><span>{{ frameBytes ? '4 帧已采集' : cameraReady ? '摄像头就绪' : '摄像头未连接' }}</span><span>{{ uploadSize }}</span></div>
          </div>
          <div class="scan-status" :class="stage"><span class="pulse" /><p>{{ scanHint }}</p></div>
          <div class="control-bar">
            <div class="camera-select"><el-icon><VideoCamera /></el-icon><el-select v-model="activeDeviceId" :disabled="isScanning || cameraBusy" placeholder="选择摄像头" @change="restartCamera"><el-option v-for="item in devices" :key="item.deviceId" :label="item.label || `摄像头 ${item.deviceId.slice(0, 6)}`" :value="item.deviceId" /></el-select></div>
            <el-button plain :icon="Connection" :loading="cameraBusy" :disabled="isScanning" @click="restartCamera">检测设备</el-button>
            <el-button v-if="!isScanning" class="scan-button" :icon="Camera" :disabled="stage === 'success' || !engineConnected || !cameraReady" @click="recognize">开始静态扫描</el-button>
            <el-button v-else class="cancel-button" :icon="Refresh" @click="cancelScan">取消扫描</el-button>
            <label class="mirror-switch"><span>镜像</span><el-switch v-model="mirrorPreview" /></label>
          </div>
        </article>
        <KioskIdentitySignal
          :state="stage"
          :real-name="result?.real_name"
          :message="message"
          :action-label="actionLabel"
          :saved-time="savedTime"
          :processing-ms="processingTime"
          :match-score="result?.match_score"
          :quality-hint="result?.quality_hint"
          :countdown="successCountdown"
          :error-kind="errorKind"
          @next="resetResult"
        />
      </section>

      <section v-else-if="activeTab === 'presence'" class="data-view" v-loading="loadingData">
        <header class="data-view-head"><div><p class="eyebrow">LIVE ATTENDANCE</p><h2>当前在实验室</h2><span>共 {{ presence?.total ?? 0 }} 人，名单每 15 秒自动刷新。</span></div><el-button plain :icon="Refresh" @click="loadPresence">刷新名单</el-button></header>
        <div v-if="presence?.items.length" class="presence-list"><article v-for="person in presence.items" :key="person.user_id" class="presence-item"><el-avatar>{{ person.real_name.slice(-2) }}</el-avatar><div><strong>{{ person.real_name }}</strong><span>{{ person.username }}</span></div><time>进入于 {{ dayjs(person.check_in_at).format('HH:mm') }}</time></article></div>
        <el-empty v-else description="当前没有人在实验室" />
      </section>

      <section v-else class="data-view" v-loading="loadingData">
        <header class="data-view-head"><div><p class="eyebrow">TODAY'S LOG</p><h2>今日终端记录</h2><span>显示签到、签退与未完成识别；详细修正请在管理员后台处理。</span></div><el-button plain :icon="Refresh" @click="loadRecords">刷新记录</el-button></header>
        <el-table v-if="records?.items.length" :data="records.items" class="records-table" height="400"><el-table-column label="时间" min-width="150"><template #default="scope">{{ dayjs(scope.row.occurred_at).format('HH:mm:ss') }}</template></el-table-column><el-table-column prop="real_name" label="人员" min-width="130"><template #default="scope">{{ scope.row.real_name ?? '未注册人员' }}</template></el-table-column><el-table-column label="操作" min-width="120"><template #default="scope"><el-tag :type="scope.row.action === 'CHECK_OUT' ? 'warning' : scope.row.action === 'CHECK_IN' ? 'success' : 'info'" effect="dark">{{ scope.row.action === 'CHECK_IN' ? '签到' : scope.row.action === 'CHECK_OUT' ? '签退' : '识别未完成' }}</el-tag></template></el-table-column><el-table-column label="结果" min-width="140"><template #default="scope"><span :class="['record-result', scope.row.result === 'SUCCESS' ? 'success' : 'failed']">{{ scope.row.result === 'SUCCESS' ? '已保存' : scope.row.result }}</span></template></el-table-column></el-table>
        <el-empty v-else description="今天还没有终端记录" />
      </section>
    </section>

    <footer class="kiosk-footer"><span>{{ device ? `${device.name} · ${device.location}` : '正在连接终端' }} · 原始人脸画面仅在本次请求内存中处理，不会保存。</span><button @click="openSettings">管理员终端设置</button></footer>
  </main>
</template>

<style scoped>
.kiosk-page { min-height: 100vh; overflow-x: hidden; color: #eff3ff; background: radial-gradient(circle at 8% 94%, rgba(83,117,255,.22), transparent 34%), radial-gradient(circle at 89% 10%, rgba(248,99,174,.21), transparent 31%), linear-gradient(145deg, #0b1132 0%, #151344 54%, #291341 100%); }.kiosk-header { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; min-height: 73px; padding: 0 clamp(20px, 4vw, 68px); border-bottom: 1px solid rgba(220,226,255,.14); background: rgba(11,16,49,.42); backdrop-filter: blur(18px); }.kiosk-brand { display: flex; align-items: center; gap: 11px; }.brand-mark { display: grid; width: 37px; height: 37px; place-items: center; border-radius: 12px; color: white; background: linear-gradient(135deg, #6da2ff, #f26ba9); box-shadow: 0 8px 23px rgba(144,91,220,.28); font-size: 18px; font-weight: 900; }.kiosk-brand div { display: grid; gap: 2px; }.kiosk-brand strong { letter-spacing: .3px; }.kiosk-brand small { color: #a1a9d1; font-size: 10px; }.kiosk-nav { display: flex; gap: 26px; }.kiosk-nav button { position: relative; padding: 26px 0 23px; border: 0; color: #a6acd4; background: transparent; cursor: pointer; font-size: 13px; font-weight: 600; }.kiosk-nav button::after { position: absolute; right: 0; bottom: 0; left: 0; height: 2px; border-radius: 3px; background: linear-gradient(90deg, #68a8ff, #fa82bd); content: ''; opacity: 0; transform: scaleX(.5); transition: .2s; }.kiosk-nav button.active { color: #f6f8ff; }.kiosk-nav button.active::after { opacity: 1; transform: scaleX(1); }.header-status { display: flex; align-items: center; justify-content: flex-end; gap: 9px; }.status-pill, .model-pill { display: inline-flex; align-items: center; gap: 7px; padding: 8px 11px; border: 1px solid rgba(135,157,255,.27); border-radius: 999px; color: #b8c4ef; background: rgba(41,53,113,.47); font-size: 10px; font-weight: 600; }.status-pill i { width: 7px; height: 7px; border-radius: 50%; background: #5be6ff; box-shadow: 0 0 0 4px rgba(91,230,255,.11); }.status-pill.offline i { background: #ff8aaf; box-shadow: 0 0 0 4px rgba(255,138,175,.11); }.model-pill { color: #f8aad0; }.settings-button { display: grid; width: 34px; height: 34px; place-items: center; border: 1px solid rgba(255,255,255,.12); border-radius: 11px; color: #b5bddf; background: rgba(255,255,255,.06); cursor: pointer; }
.kiosk-content { width: min(1460px, 100%); margin: 0 auto; padding: clamp(24px, 3.7vw, 54px) clamp(18px, 4vw, 64px) 42px; }.welcome-row { display: grid; grid-template-columns: minmax(300px, 1fr) minmax(450px, .95fr); align-items: center; gap: 42px; margin-bottom: 28px; }.eyebrow { margin: 0 0 7px; color: #69dfff; font-size: 10px; font-weight: 700; letter-spacing: 2.1px; }.welcome-row h1 { margin: 0; color: #f3f5ff; font-size: clamp(26px, 3vw, 42px); letter-spacing: -1.1px; }.welcome-row > div > p:last-child { margin: 10px 0 0; color: #a7afd6; font-size: 13px; }.workspace-grid { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(330px, .68fr); gap: 27px; align-items: stretch; }.live-panel, .data-view { min-width: 0; padding: clamp(17px, 2.3vw, 29px); border: 1px solid rgba(168,183,255,.23); border-radius: 27px; background: rgba(17,25,71,.67); box-shadow: inset 0 1px rgba(255,255,255,.055), 0 24px 56px rgba(4,6,28,.25); backdrop-filter: blur(16px); }.panel-head, .data-view-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 19px; }.panel-head p { margin: 0; color: #67dcff; font-size: 10px; font-weight: 700; letter-spacing: 1.9px; }.panel-head h2, .data-view h2 { margin: 5px 0 0; color: #f6f8ff; font-size: 25px; }.panel-badges { display: flex; align-items: center; gap: 8px; }.panel-badges span, .panel-badges b { display: inline-flex; align-items: center; gap: 6px; padding: 7px 10px; border: 1px solid rgba(138,160,255,.24); border-radius: 999px; color: #b8c4e8; background: rgba(93,109,184,.13); font-size: 10px; font-weight: 500; }.panel-badges b { color: #f6acd1; }.panel-badges i { width: 6px; height: 6px; border-radius: 50%; background: #8d93ba; }.panel-badges i.active { background: #6fe6ff; box-shadow: 0 0 10px #6fe6ff; }
.camera-shell { position: relative; aspect-ratio: 16/9; overflow: hidden; border: 1px solid rgba(130,151,255,.39); border-radius: 20px; background: #06091e; box-shadow: 0 18px 45px rgba(0,0,0,.29); }.camera-shell video { width: 100%; height: 100%; object-fit: cover; }.camera-shell video.mirrored { transform: scaleX(-1); }.camera-vignette { position: absolute; inset: 0; box-shadow: inset 0 0 95px rgba(1,4,20,.57); pointer-events: none; }.guide-frame { position: absolute; top: 50%; left: 50%; width: 34%; min-width: 152px; aspect-ratio: .78; border: 1px solid rgba(181,201,255,.35); border-radius: 48%; transform: translate(-50%, -50%); }.guide-frame i { position: absolute; width: 26px; height: 26px; border-color: #ff91c5; border-style: solid; }.top-left { top: -3px; left: -3px; border-width: 3px 0 0 3px; border-radius: 14px 0 0; }.top-right { top: -3px; right: -3px; border-width: 3px 3px 0 0; border-radius: 0 14px 0 0; }.bottom-left { bottom: -3px; left: -3px; border-width: 0 0 3px 3px; border-radius: 0 0 0 14px; }.bottom-right { right: -3px; bottom: -3px; border-width: 0 3px 3px 0; border-radius: 0 0 14px 0; }.verified-box { position: absolute; z-index: 3; border: 2px solid #72eaff; border-radius: 6px; box-shadow: 0 0 0 1px rgba(1,7,33,.3), 0 0 18px rgba(114,234,255,.48); }.verified-box.failure { border-color: #ff778f; box-shadow: 0 0 18px rgba(255,93,127,.46); }.verified-box span { position: absolute; top: -27px; left: -2px; padding: 5px 8px; border-radius: 5px 5px 5px 0; color: #08122d; background: #72eaff; font-size: 10px; font-weight: 700; white-space: nowrap; }.verified-box.failure span { color: white; background: #ff607f; }.scan-line { position: absolute; z-index: 2; right: 22%; left: 22%; height: 2px; background: linear-gradient(90deg, transparent, #77b4ff, #ff84c0, transparent); box-shadow: 0 0 19px #b381ff; animation: scan 1.25s ease-in-out infinite alternate; }@keyframes scan { from { top: 26%; } to { top: 75%; } }.camera-label { position: absolute; top: 15px; left: 15px; z-index: 4; display: flex; align-items: center; gap: 10px; }.camera-label span { padding: 6px 8px; border: 1px solid rgba(255,255,255,.28); border-radius: 6px; color: #f6f8ff; background: rgba(8,13,39,.65); font: 700 10px monospace; letter-spacing: .5px; }.camera-label small { color: #d0d8ff; font: 10px monospace; }.camera-telemetry { position: absolute; right: 14px; bottom: 13px; left: 14px; z-index: 4; display: flex; justify-content: space-between; color: #d1d7fa; font: 10px monospace; text-shadow: 0 1px 3px #050615; }.scan-status { display: flex; align-items: center; gap: 9px; min-height: 48px; margin-top: 13px; padding: 0 14px; border: 1px solid rgba(157,175,255,.14); border-radius: 12px; color: #c0c8ed; background: rgba(255,255,255,.04); }.scan-status p { margin: 0; font-size: 12px; }.pulse { width: 7px; height: 7px; flex: 0 0 auto; border-radius: 50%; background: #8491c7; }.capturing .pulse, .processing .pulse { background: #ff93c8; box-shadow: 0 0 0 5px rgba(255,147,200,.1); animation: pulse 1.1s infinite; }.success .pulse { background: #6feaff; box-shadow: 0 0 0 5px rgba(111,234,255,.12); }.error .pulse { background: #ff889d; }.success { color: #d5eaff; }.error { color: #ffd0d8; }@keyframes pulse { 50% { transform: scale(.74); opacity: .55; } }.control-bar { display: grid; grid-template-columns: minmax(165px, 1fr) auto auto auto; align-items: center; gap: 10px; margin-top: 16px; }.camera-select { display: flex; align-items: center; min-width: 0; padding: 0 9px; border: 1px solid rgba(154,172,255,.2); border-radius: 11px; color: #aebae8; background: rgba(4,8,30,.24); }.camera-select :deep(.el-select) { min-width: 0; }.camera-select :deep(.el-select__wrapper) { box-shadow: none; background: transparent; }.camera-select :deep(.el-select__selected-item) { color: #dce2ff; font-size: 11px; }.control-bar :deep(.el-button) { height: 37px; margin: 0; border-color: rgba(154,172,255,.26); color: #c9d2f2; background: rgba(255,255,255,.045); }.control-bar .scan-button { border: 0; color: #fff; background: linear-gradient(135deg, #5b82ff, #8d69e8 49%, #ed69a6); box-shadow: 0 8px 20px rgba(102,89,213,.26); }.control-bar .cancel-button { color: #ffe3ee; border-color: rgba(248,129,188,.45); background: rgba(243,97,164,.13); }.mirror-switch { display: flex; align-items: center; gap: 7px; color: #aab3d7; font-size: 11px; white-space: nowrap; }.mirror-switch :deep(.el-switch) { --el-switch-on-color: #737ffa; }
.data-view { min-height: 510px; }.data-view-head > div > span { display: block; margin-top: 9px; color: #abb4d8; font-size: 12px; }.data-view-head :deep(.el-button) { border-color: rgba(154,172,255,.28); color: #c7d0f1; background: rgba(255,255,255,.04); }.presence-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; }.presence-item { display: grid; grid-template-columns: 43px 1fr auto; align-items: center; gap: 10px; padding: 15px; border: 1px solid rgba(164,180,255,.18); border-radius: 15px; background: rgba(255,255,255,.035); }.presence-item :deep(.el-avatar) { color: white; background: linear-gradient(135deg, #7698ff, #e979b1); font-size: 13px; }.presence-item div { display: grid; gap: 4px; min-width: 0; }.presence-item strong { overflow: hidden; color: #eff2ff; text-overflow: ellipsis; white-space: nowrap; }.presence-item span, .presence-item time { color: #9ba5ca; font-size: 10px; }.presence-item time { text-align: right; }.records-table { width: 100%; overflow: hidden; border: 1px solid rgba(164,180,255,.15); border-radius: 13px; --el-table-bg-color: rgba(255,255,255,.025); --el-table-tr-bg-color: transparent; --el-table-header-bg-color: rgba(113,129,210,.1); --el-table-border-color: rgba(164,180,255,.11); --el-table-text-color: #dce3fc; --el-table-header-text-color: #abb6df; }.record-result { font-size: 12px; font-weight: 600; }.record-result.success { color: #73e8ff; }.record-result.failed { color: #ff9caf; }
.kiosk-footer { display: flex; justify-content: space-between; gap: 18px; min-height: 53px; padding: 0 clamp(18px, 4vw, 68px); border-top: 1px solid rgba(222,229,255,.1); color: #858eb9; font-size: 10px; }.kiosk-footer span, .kiosk-footer button { display: flex; align-items: center; }.kiosk-footer button { border: 0; color: #b4bce3; background: transparent; cursor: pointer; font-size: 10px; }
@media (max-width: 1160px) { .kiosk-header { grid-template-columns: 1fr auto; }.kiosk-nav { order: 3; grid-column: 1 / -1; justify-content: center; }.kiosk-nav button { padding: 12px 0; }.header-status { justify-self: end; }.welcome-row, .workspace-grid { grid-template-columns: 1fr; }.workspace-grid :deep(.identity-panel) { min-height: 410px; }.welcome-row { gap: 22px; }.control-bar { grid-template-columns: minmax(160px, 1fr) auto auto; }.mirror-switch { grid-column: 1 / -1; justify-content: flex-end; } }
@media (max-width: 680px) { .kiosk-header { padding: 0 17px; }.header-status .model-pill { display: none; }.status-pill { font-size: 9px; }.kiosk-nav { gap: 20px; }.kiosk-content { padding: 23px 14px 30px; }.panel-head { align-items: flex-start; }.panel-badges { flex-direction: column; align-items: flex-end; }.control-bar { grid-template-columns: 1fr 1fr; }.camera-select { grid-column: 1 / -1; }.control-bar .scan-button, .control-bar .cancel-button { grid-column: 1 / -1; }.mirror-switch { grid-column: 1 / -1; justify-content: flex-start; }.kiosk-footer { flex-direction: column; justify-content: center; padding-top: 10px; padding-bottom: 10px; }.kiosk-footer button { padding: 0; } }
</style>

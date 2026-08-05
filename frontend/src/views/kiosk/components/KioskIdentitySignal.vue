<script setup lang="ts">
import { computed } from 'vue'
import { CircleCheck, CircleClose, Loading, UserFilled } from '@element-plus/icons-vue'

type SignalState = 'ready' | 'capturing' | 'processing' | 'recognized' | 'success' | 'error'

const props = defineProps<{
  state: SignalState
  realName?: string | null
  message: string
  actionLabel?: string
  savedTime?: string
  processingMs?: number | null
  matchScore?: number | null
  qualityHint?: string | null
  countdown: number
  errorKind?: 'camera' | 'recognition'
}>()

const emit = defineEmits<{ next: [] }>()

const stateCopy = computed(() => {
  const states: Record<SignalState, { eyebrow: string; title: string; description: string }> = {
    ready: { eyebrow: 'IDENTITY SIGNAL', title: '等待扫描', description: '请站在取景框内，点击开始静态扫描。' },
    capturing: { eyebrow: 'STATIC SCAN', title: '正在采集', description: '请正视摄像头并保持画面稳定。' },
    processing: { eyebrow: 'VERIFYING', title: '正在核验', description: '正在检查画面质量、活体和人脸特征。' },
    recognized: { eyebrow: 'IDENTITY FOUND', title: '身份已识别', description: '正在按当前考勤状态自动保存记录。' },
    success: { eyebrow: 'ATTENDANCE SAVED', title: props.actionLabel ?? '打卡成功', description: '记录已经由服务器写入考勤系统。' },
    error: props.errorKind === 'camera'
      ? { eyebrow: 'CAMERA OFFLINE', title: '摄像头不可用', description: '请检查设备连接、权限或选择其他摄像头。' }
      : { eyebrow: 'NO MATCH', title: '本次未完成', description: '请调整位置后再次静态扫描。' },
  }
  return states[props.state]
})

const icon = computed(() => props.state === 'success' ? CircleCheck : props.state === 'error' ? CircleClose : props.state === 'ready' ? UserFilled : Loading)
const initials = computed(() => props.realName?.slice(-2) ?? '？')
</script>

<template>
  <section class="identity-panel" :class="state">
    <div class="identity-head"><span>{{ stateCopy.eyebrow }}</span><small>{{ state === 'processing' || state === 'capturing' ? 'SCANNING' : 'READY' }}</small></div>
    <div class="signal-orbit orbit-one" /><div class="signal-orbit orbit-two" />
    <div class="identity-avatar"><el-icon v-if="state !== 'ready' && !realName"><component :is="icon" /></el-icon><span v-else>{{ initials }}</span></div>
    <p class="signal-state">{{ stateCopy.title }}</p>
    <h2 v-if="realName">{{ realName }}</h2>
    <p class="signal-description">{{ message || stateCopy.description }}</p>
    <dl v-if="state === 'success' || state === 'recognized'" class="identity-details">
      <div v-if="savedTime"><dt>服务器时间</dt><dd>{{ savedTime }}</dd></div>
      <div v-if="processingMs"><dt>核验耗时</dt><dd>{{ processingMs }} ms</dd></div>
      <div v-if="matchScore != null"><dt>匹配分数</dt><dd>{{ (matchScore * 100).toFixed(1) }}%</dd></div>
    </dl>
    <p v-else-if="qualityHint" class="quality-hint">{{ qualityHint }}</p>
    <el-button v-if="state === 'success'" class="next-button" @click="emit('next')">下一位 <span v-if="countdown">({{ countdown }} 秒)</span></el-button>
  </section>
</template>

<style scoped>
.identity-panel { position: relative; display: flex; min-height: 482px; flex-direction: column; align-items: center; justify-content: center; overflow: hidden; padding: 38px 30px; border: 1px solid rgba(168,180,255,.25); border-radius: 27px; background: radial-gradient(circle at 50% 44%, rgba(103,116,255,.18), transparent 34%), linear-gradient(155deg, rgba(24,32,84,.9), rgba(22,20,59,.88)); box-shadow: inset 0 1px rgba(255,255,255,.08), 0 22px 50px rgba(5,6,34,.3); text-align: center; }
.identity-head { position: absolute; top: 21px; right: 23px; left: 23px; display: flex; justify-content: space-between; color: #67ddff; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; }.identity-head small { color: #aab2dc; font-size: 9px; letter-spacing: .7px; }
.signal-orbit { position: absolute; width: 290px; height: 290px; border: 1px solid rgba(123,149,255,.17); border-radius: 48%; transform: rotate(-38deg); }.orbit-two { width: 206px; height: 330px; border-color: rgba(248,122,184,.15); transform: rotate(41deg); }
.identity-avatar { position: relative; z-index: 1; display: grid; width: 116px; height: 116px; place-items: center; overflow: hidden; border: 1px solid rgba(255,255,255,.58); border-radius: 36px; color: #f9fbff; background: linear-gradient(145deg, rgba(131,160,255,.85), rgba(241,111,180,.8)); box-shadow: 0 12px 35px rgba(63,75,201,.32); font-size: 44px; font-weight: 700; }.ready .identity-avatar { color: #b9c4ee; background: linear-gradient(145deg, rgba(92,111,174,.65), rgba(115,72,132,.65)); }.error .identity-avatar { color: #ffd2d2; background: linear-gradient(145deg, rgba(184,75,99,.85), rgba(137,59,103,.85)); }.processing .identity-avatar, .capturing .identity-avatar { animation: breathe 1.4s ease-in-out infinite alternate; }
.signal-state { position: relative; z-index: 1; margin: 26px 0 0; color: #9ea9dd; font-size: 12px; }.identity-panel h2 { position: relative; z-index: 1; margin: 9px 0 0; color: #f8f9ff; font-size: 30px; }.signal-description { position: relative; z-index: 1; max-width: 275px; margin: 10px 0 0; color: #c0c6e9; line-height: 1.7; font-size: 13px; }.identity-details { position: relative; z-index: 1; display: grid; width: 100%; grid-template-columns: repeat(3, 1fr); gap: 7px; margin: 23px 0 0; }.identity-details div { padding: 9px 4px; border-radius: 10px; background: rgba(255,255,255,.055); }.identity-details dt { color: #939cc5; font-size: 9px; }.identity-details dd { margin: 5px 0 0; color: #f6f7ff; font-size: 11px; }.quality-hint { position: relative; z-index: 1; margin: 20px 0 0; color: #aeb7dc; font-size: 11px; }.next-button { position: relative; z-index: 1; height: 38px; margin-top: 24px; border-color: transparent; color: #fff; background: linear-gradient(135deg, #6184ff, #e66cab); }.next-button span { opacity: .75; font-size: 11px; }
@keyframes breathe { to { transform: scale(1.04); box-shadow: 0 0 0 11px rgba(116,136,255,.1), 0 12px 35px rgba(63,75,201,.32); } }
@media (max-width: 1100px) { .identity-panel { min-height: 395px; }.identity-details { width: min(380px, 100%); } }
</style>

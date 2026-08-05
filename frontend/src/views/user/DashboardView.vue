<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import MetricCard from '@/components/MetricCard.vue'
import DurationChart from '@/components/DurationChart.vue'
import StatusTag from '@/components/StatusTag.vue'
import { http, errorMessage } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import type { UserStatistics } from '@/types'
import { formatDateTime, formatDuration } from '@/utils/format'
import { ElMessage } from 'element-plus'

const auth = useAuthStore()
const loading = ref(true)
const stats = ref<UserStatistics | null>(null)
const tick = ref(Date.now())
let timer: number | undefined
const ongoing = computed(() => stats.value?.ongoing_since ? Math.max(0, Math.floor((tick.value - new Date(stats.value.ongoing_since).getTime()) / 1000)) : 0)

async function load() {
  loading.value = true
  try { stats.value = (await http.get<UserStatistics>('/me/statistics')).data }
  catch (err) { ElMessage.error(errorMessage(err, '统计加载失败')) }
  finally { loading.value = false }
}
onMounted(() => { load(); timer = window.setInterval(() => { tick.value = Date.now() }, 1000) })
onBeforeUnmount(() => window.clearInterval(timer))
</script>

<template>
  <PageHeader :title="`${auth.user?.real_name ?? ''}，你好`" description="这里是你的实验室出勤概览，正式累计只包含已完成的有效记录。">
    <el-button type="primary" tag="router-link" to="/kiosk">前往打卡</el-button>
  </PageHeader>
  <div v-loading="loading">
    <div class="presence-card" :class="{ active: stats?.ongoing_since }">
      <div><span class="presence-pulse" /><div><strong>{{ stats?.ongoing_since ? '当前在实验室' : '当前不在实验室' }}</strong><small>{{ stats?.ongoing_since ? `签到于 ${formatDateTime(stats.ongoing_since)}` : '识别成功后可在终端签到' }}</small></div></div>
      <b>{{ stats?.ongoing_since ? formatDuration(ongoing) : '未开始计时' }}</b>
    </div>
    <div class="metric-grid dashboard-metrics">
      <MetricCard label="今日有效时长" :value="formatDuration(stats?.today_seconds)" note="按上海自然日统计" />
      <MetricCard label="本周累计" :value="formatDuration(stats?.week_seconds)" note="周一至今日" tone="blue" />
      <MetricCard label="本月累计" :value="formatDuration(stats?.month_seconds)" note="仅包含已签退记录" tone="purple" />
      <MetricCard label="近期记录" :value="stats?.recent_sessions.length ?? 0" note="最近完成与异常记录" tone="amber" />
    </div>
    <div class="content-grid">
      <section class="panel">
        <div class="panel__header"><h2>近 30 天时长趋势</h2><small>单位：小时</small></div>
        <div class="panel__body"><DurationChart :data="stats?.daily ?? []" kind="line" /></div>
      </section>
      <section class="panel">
        <div class="panel__header"><h2>最近打卡</h2><router-link to="/attendance" class="more-link">全部记录 →</router-link></div>
        <div class="recent-list">
          <div v-for="item in stats?.recent_sessions.slice(0, 5)" :key="item.id" class="recent-item">
            <span class="recent-item__line" />
            <div><strong>{{ formatDateTime(item.check_in_at) }}</strong><small>{{ item.check_out_at ? `签退 ${formatDateTime(item.check_out_at)}` : '尚未签退' }}</small></div>
            <div class="recent-item__right"><StatusTag :status="item.status" /><small>{{ formatDuration(item.duration_seconds) }}</small></div>
          </div>
          <div v-if="!stats?.recent_sessions.length" class="empty-hint">暂无打卡记录</div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.presence-card { display: flex; align-items: center; justify-content: space-between; min-height: 86px; margin-bottom: 16px; padding: 18px 22px; border: 1px solid #e7e5f4; border-radius: 16px; background: white; box-shadow: 0 10px 28px rgba(86,72,180,.06); }
.presence-card.active { color: #515bd6; border-color: #cbd0ff; background: linear-gradient(100deg, #edf2ff, #fff0f8 82%); }
.presence-card > div { display: flex; align-items: center; gap: 14px; }
.presence-card > div > div { display: flex; flex-direction: column; gap: 5px; }
.presence-card small { color: #7c7f9c; }
.presence-card b { font-size: 20px; }
.presence-pulse { width: 12px; height: 12px; border-radius: 50%; background: #a5a7ba; box-shadow: 0 0 0 7px #f0eff6; }
.active .presence-pulse { background: #f15ca8; box-shadow: 0 0 0 7px #ffe4f1; }
.dashboard-metrics { margin-top: 0; }
.more-link { color: #626cf0; font-size: 12px; }
.panel__header small { color: #8588a5; }
.recent-list { padding: 5px 20px; }
.recent-item { min-height: 72px; display: grid; grid-template-columns: 4px 1fr auto; align-items: center; gap: 13px; border-bottom: 1px solid #efedf8; }
.recent-item:last-child { border: 0; }
.recent-item__line { width: 3px; height: 34px; border-radius: 4px; background: linear-gradient(#6f8cff, #f178b5); }
.recent-item > div { min-width: 0; display: flex; flex-direction: column; gap: 5px; }
.recent-item strong { font-size: 12px; }
.recent-item small { color: #8588a5; font-size: 11px; }
.recent-item__right { align-items: flex-end; }
@media (max-width: 720px) { .presence-card { align-items: flex-start; } .presence-card b { font-size: 15px; } }
</style>

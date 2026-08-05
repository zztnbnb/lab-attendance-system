<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import MetricCard from '@/components/MetricCard.vue'
import DurationChart from '@/components/DurationChart.vue'
import { http, errorMessage } from '@/api/http'
import type { AdminStatistics } from '@/types'
import { formatDateTime, formatDuration } from '@/utils/format'

const loading = ref(false)
const stats = ref<AdminStatistics | null>(null)
let refreshTimer: number | undefined
async function load() {
  loading.value = true
  try { stats.value = (await http.get('/admin/statistics')).data }
  catch (err) { ElMessage.error(errorMessage(err)) }
  finally { loading.value = false }
}
onMounted(() => {
  load()
  refreshTimer = window.setInterval(load, 10_000)
})
onBeforeUnmount(() => window.clearInterval(refreshTimer))
</script>

<template>
  <PageHeader title="数据总览" description="实验室当前状态、今日打卡与近期有效时长。"><el-button @click="load">刷新数据</el-button></PageHeader>
  <div v-loading="loading">
    <div class="metric-grid">
      <MetricCard label="当前在实验室" :value="`${stats?.current_count ?? 0} 人`" note="实时开放会话" />
      <MetricCard label="今日签到" :value="`${stats?.today_checkins ?? 0} 人次`" note="按自然日统计" tone="blue" />
      <MetricCard label="今日完成签退" :value="`${stats?.today_checkouts ?? 0} 人次`" note="已生成有效时长" tone="purple" />
      <MetricCard label="待处理异常" :value="`${stats?.exception_count ?? 0} 条`" note="漏签退记录" tone="amber" />
    </div>
    <div class="content-grid">
      <section class="panel"><div class="panel__header"><h2>近 14 天实验室时长</h2><router-link to="/admin/statistics" class="more">详细统计 →</router-link></div><div class="panel__body"><DurationChart :data="stats?.daily ?? []" kind="bar" /></div></section>
      <section class="panel"><div class="panel__header"><h2>当前在实验室</h2><span class="live"><i /> 实时</span></div><div class="occupants"><div v-for="item in stats?.current_users" :key="item.user_id"><el-avatar :size="34">{{ item.real_name.slice(-2) }}</el-avatar><span><b>{{ item.real_name }}</b><small>{{ item.username }} · {{ formatDateTime(item.check_in_at) }}</small></span></div><div v-if="!stats?.current_users.length" class="empty-hint">当前无人签到</div></div></section>
    </div>
    <section class="panel ranking-panel"><div class="panel__header"><h2>近期时长排行</h2><span class="subtle">只统计有效已签退记录</span></div><el-table :data="stats?.ranking.slice(0, 8)"><el-table-column type="index" label="#" width="70" /><el-table-column prop="real_name" label="姓名" /><el-table-column prop="username" label="账号" /><el-table-column label="累计时长"><template #default="{ row }"><strong class="duration">{{ formatDuration(row.duration_seconds) }}</strong></template></el-table-column></el-table></section>
  </div>
</template>

<style scoped>
.more { color: #626cf0; font-size: 12px; }.live { color: #df5ca2; font-size: 11px; }.live i { display: inline-block; width: 7px; height: 7px; margin-right: 4px; border-radius: 50%; background: #f15ca8; box-shadow: 0 0 0 4px #ffe4f1; }.occupants { padding: 5px 20px; max-height: 350px; overflow: auto; }.occupants > div:not(.empty-hint) { min-height: 65px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #efedf8; }.occupants .el-avatar { color: white; background: linear-gradient(135deg, #6b88ff, #ee75b2); }.occupants span { display: flex; flex-direction: column; gap: 4px; }.occupants b { font-size: 13px; }.occupants small, .subtle { color: #8588a5; font-size: 11px; }.ranking-panel { margin-top: 18px; }.duration { color: #626cf0; }
</style>

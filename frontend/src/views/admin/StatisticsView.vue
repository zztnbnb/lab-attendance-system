<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import MetricCard from '@/components/MetricCard.vue'
import DurationChart from '@/components/DurationChart.vue'
import HourlyChart from '@/components/HourlyChart.vue'
import { http, errorMessage } from '@/api/http'
import type { AdminStatistics } from '@/types'
import { formatDuration } from '@/utils/format'

const stats = ref<AdminStatistics | null>(null)
const days = ref(30)
const loading = ref(false)
const totalDuration = computed(() => stats.value?.daily.reduce((sum, item) => sum + item.duration_seconds, 0) ?? 0)
const average = computed(() => stats.value?.daily.length ? Math.floor(totalDuration.value / stats.value.daily.length) : 0)
async function load() {
  loading.value = true
  try { stats.value = (await http.get('/admin/statistics', { params: { days: days.value } })).data }
  catch (err) { ElMessage.error(errorMessage(err)) }
  finally { loading.value = false }
}
async function exportCsv() {
  try { const { data } = await http.get('/admin/attendance-export.csv', { responseType: 'blob' }); const url = URL.createObjectURL(data); const link = document.createElement('a'); link.href = url; link.download = `attendance-${new Date().toISOString().slice(0, 10)}.csv`; link.click(); URL.revokeObjectURL(url) }
  catch (err) { ElMessage.error(errorMessage(err, '导出失败')) }
}
onMounted(load)
</script>

<template>
  <PageHeader title="时长统计" description="有效时长按 Asia/Shanghai 自然日切分；进行中和异常会话不进入正式累计。"><el-select v-model="days" style="width:130px" @change="load"><el-option label="近 14 天" :value="14" /><el-option label="近 30 天" :value="30" /><el-option label="近 60 天" :value="60" /><el-option label="近 90 天" :value="90" /></el-select><el-button :icon="Download" @click="exportCsv">导出 CSV</el-button></PageHeader>
  <div v-loading="loading">
    <div class="metric-grid"><MetricCard label="区间有效总时长" :value="formatDuration(totalDuration)" /><MetricCard label="日均有效时长" :value="formatDuration(average)" tone="blue" /><MetricCard label="当前在实验室" :value="`${stats?.current_count ?? 0} 人`" tone="purple" /><MetricCard label="异常记录" :value="`${stats?.exception_count ?? 0} 条`" tone="amber" /></div>
    <div class="content-grid"><section class="panel"><div class="panel__header"><h2>每日有效时长趋势</h2></div><div class="panel__body"><DurationChart :data="stats?.daily ?? []" kind="line" /></div></section><section class="panel"><div class="panel__header"><h2>签到时段分布</h2></div><div class="panel__body"><HourlyChart :data="stats?.hourly ?? []" /></div></section></div>
    <section class="panel ranking"><div class="panel__header"><h2>所有用户打卡汇总</h2><span>当前统计区间 · 包含无打卡记录用户</span></div><el-table :data="stats?.ranking" stripe><el-table-column type="index" label="序号" width="70" /><el-table-column prop="real_name" label="姓名" min-width="110" /><el-table-column prop="username" label="学号 / 账号" min-width="135" /><el-table-column label="累计有效时长" min-width="135"><template #default="{ row }"><b class="accent">{{ formatDuration(row.duration_seconds) }}</b></template></el-table-column><el-table-column label="签到次数" width="95"><template #default="{ row }">{{ row.checkin_count ?? 0 }}</template></el-table-column><el-table-column label="签退次数" width="95"><template #default="{ row }">{{ row.checkout_count ?? 0 }}</template></el-table-column><el-table-column label="账号状态" width="100"><template #default="{ row }"><el-tag :type="row.is_active === false ? 'info' : 'success'">{{ row.is_active === false ? '已停用' : '正常' }}</el-tag></template></el-table-column></el-table></section>
  </div>
</template>

<style scoped>.ranking { margin-top: 18px; }.ranking .panel__header span { color: #8588a5; font-size: 11px; }.accent { color: #626cf0; }</style>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  currentCount: number
  todayCheckins: number
  todayCheckouts: number
  exceptionCount: number
}>()

const metrics = computed(() => [
  { label: '当前在实验室', value: props.currentCount, tone: 'cyan', suffix: '人' },
  { label: '今日签到', value: props.todayCheckins, tone: 'blue', suffix: '次' },
  { label: '今日签退', value: props.todayCheckouts, tone: 'pink', suffix: '次' },
  { label: '待处理异常', value: props.exceptionCount, tone: props.exceptionCount ? 'warning' : 'muted', suffix: '条' },
])
</script>

<template>
  <section class="metric-grid" aria-label="终端考勤概览">
    <article v-for="metric in metrics" :key="metric.label" class="kiosk-metric-card" :class="metric.tone">
      <span>{{ metric.label }}</span>
      <strong>{{ metric.value }}</strong>
      <small>{{ metric.suffix }}</small>
    </article>
  </section>
</template>

<style scoped>
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(100px, 1fr)); overflow: hidden; border: 1px solid rgba(163,180,255,.2); border-radius: 17px; background: rgba(20,26,72,.62); box-shadow: inset 0 1px rgba(255,255,255,.05); }
.kiosk-metric-card { position: relative; min-height: 82px; padding: 15px 17px; border-right: 1px solid rgba(255,255,255,.08); background: rgba(20,26,72,.62); }
.kiosk-metric-card:last-child { border-right: 0; }
.kiosk-metric-card span { display: block; color: #9ea6cf; font-size: 11px; }
.kiosk-metric-card strong { display: inline-block; margin-top: 7px; color: #eff3ff; font-size: 27px; line-height: 1; letter-spacing: -.7px; }
.kiosk-metric-card small { margin-left: 5px; color: #8992c6; font-size: 11px; }
.kiosk-metric-card::before { position: absolute; top: 14px; right: 14px; width: 7px; height: 7px; border-radius: 50%; background: currentColor; box-shadow: 0 0 14px currentColor; content: ''; }
.cyan { color: #64e7ff; }.blue { color: #82a5ff; }.pink { color: #ff8fc5; }.warning { color: #ffbd78; }.muted { color: #747da8; }
@media (max-width: 760px) { .metric-grid { grid-template-columns: repeat(2, 1fr); }.kiosk-metric-card:nth-child(2) { border-right: 0; }.kiosk-metric-card:nth-child(-n+2) { border-bottom: 1px solid rgba(255,255,255,.08); } }
</style>

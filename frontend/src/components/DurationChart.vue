<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import type { DailyDuration } from '@/types'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent])
const props = withDefaults(defineProps<{ data: DailyDuration[]; kind?: 'bar' | 'line'; color?: string }>(), { kind: 'bar', color: '#7a70ee' })
const option = computed(() => ({
  animationDuration: 500,
  grid: { left: 14, right: 12, top: 16, bottom: 8, containLabel: true },
  tooltip: { trigger: 'axis', valueFormatter: (value: number) => `${value.toFixed(1)} 小时` },
  xAxis: { type: 'category', data: props.data.map((item) => item.date.slice(5)), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#7a7d9d' } },
  yAxis: { type: 'value', axisLabel: { formatter: '{value}h', color: '#7a7d9d' }, splitLine: { lineStyle: { color: '#efedf8' } } },
  series: [{ type: props.kind, data: props.data.map((item) => +(item.duration_seconds / 3600).toFixed(2)), smooth: true, symbol: 'none', barMaxWidth: 24, itemStyle: { color: props.color, borderRadius: [6, 6, 0, 0] }, lineStyle: { width: 3 }, areaStyle: props.kind === 'line' ? { opacity: 0.08 } : undefined }],
}))
</script>

<template><VChart class="duration-chart" :option="option" autoresize /></template>

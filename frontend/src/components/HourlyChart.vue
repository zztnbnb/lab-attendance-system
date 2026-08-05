<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import type { HourlyCount } from '@/types'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])
const props = defineProps<{ data: HourlyCount[] }>()
const option = computed(() => ({
  grid: { left: 12, right: 12, top: 16, bottom: 5, containLabel: true },
  tooltip: { trigger: 'axis', valueFormatter: (value: number) => `${value} 次签到` },
  xAxis: { type: 'category', data: props.data.map((item) => `${String(item.hour).padStart(2, '0')}:00`), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#7a7d9d', interval: 2 } },
  yAxis: { type: 'value', minInterval: 1, axisLabel: { color: '#7a7d9d' }, splitLine: { lineStyle: { color: '#efedf8' } } },
  series: [{ type: 'bar', data: props.data.map((item) => item.count), barMaxWidth: 20, itemStyle: { color: '#ef6eae', borderRadius: [5, 5, 0, 0] } }],
}))
</script>

<template><VChart class="duration-chart" :option="option" autoresize /></template>

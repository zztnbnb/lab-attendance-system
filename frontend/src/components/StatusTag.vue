<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ status: string }>()
const labels: Record<string, string> = {
  OPEN: '在实验室', CLOSED: '已完成', MISSING_CHECKOUT: '漏签退', INVALID: '已作废',
  DRAFT: '采集中', PENDING: '待审批', ACTIVE: '已激活', REJECTED: '已拒绝', REPLACED: '已替换', REVOKED: '已撤销',
}
const types: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'primary'> = {
  OPEN: 'success', CLOSED: 'primary', MISSING_CHECKOUT: 'warning', INVALID: 'info',
  DRAFT: 'info', PENDING: 'warning', ACTIVE: 'success', REJECTED: 'danger', REPLACED: 'info', REVOKED: 'danger',
}
const label = computed(() => labels[props.status] ?? props.status)
const type = computed(() => types[props.status] ?? 'info')
</script>

<template><el-tag :type="type" effect="light" round>{{ label }}</el-tag></template>

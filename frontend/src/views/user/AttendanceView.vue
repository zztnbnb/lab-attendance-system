<script setup lang="ts">
import { onMounted, ref } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { http, errorMessage } from '@/api/http'
import type { AttendanceSession, AttendanceStatus, Page } from '@/types'
import { formatDateTime, formatDuration } from '@/utils/format'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const status = ref<AttendanceStatus | ''>('')
const page = ref(1)
const result = ref<Page<AttendanceSession>>({ items: [], total: 0, page: 1, page_size: 20 })
async function load() {
  loading.value = true
  try { result.value = (await http.get('/me/attendance-sessions', { params: { page: page.value, page_size: 20, status: status.value || undefined } })).data }
  catch (err) { ElMessage.error(errorMessage(err)) }
  finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <PageHeader title="我的打卡记录" description="查看签到、签退、有效时长与异常状态。" />
  <section class="panel">
    <div class="panel__body">
      <div class="toolbar">
        <el-select v-model="status" placeholder="全部状态" clearable style="width: 180px" @change="page = 1; load()">
          <el-option label="在实验室" value="OPEN" /><el-option label="已完成" value="CLOSED" /><el-option label="漏签退" value="MISSING_CHECKOUT" /><el-option label="已作废" value="INVALID" />
        </el-select>
        <el-button @click="load">刷新</el-button>
      </div>
      <el-table v-loading="loading" :data="result.items" class="data-table">
        <el-table-column label="签到时间" min-width="170"><template #default="{ row }">{{ formatDateTime(row.check_in_at) }}</template></el-table-column>
        <el-table-column label="签退时间" min-width="170"><template #default="{ row }">{{ formatDateTime(row.check_out_at) }}</template></el-table-column>
        <el-table-column label="有效时长" min-width="120"><template #default="{ row }">{{ row.status === 'CLOSED' ? formatDuration(row.duration_seconds) : '—' }}</template></el-table-column>
        <el-table-column label="状态" width="120"><template #default="{ row }"><StatusTag :status="row.status" /></template></el-table-column>
        <el-table-column prop="correction_reason" label="备注" min-width="180" show-overflow-tooltip />
      </el-table>
      <el-pagination v-if="result.total > 20" v-model:current-page="page" :page-size="20" :total="result.total" layout="prev, pager, next, total" class="table-pagination" @current-change="load" />
    </div>
  </section>
</template>

<style scoped>.table-pagination { justify-content: flex-end; margin-top: 20px; }</style>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import { http, errorMessage } from '@/api/http'
import type { AuditLog, Page } from '@/types'
import { formatDateTime } from '@/utils/format'

const action = ref('')
const page = ref(1)
const loading = ref(false)
const result = ref<Page<AuditLog>>({ items: [], total: 0, page: 1, page_size: 20 })
const detail = ref<AuditLog | null>(null)
async function load() { loading.value = true; try { result.value = (await http.get('/admin/audit-logs', { params: { action: action.value || undefined, page: page.value, page_size: 20 } })).data } catch (err) { ElMessage.error(errorMessage(err)) } finally { loading.value = false } }
onMounted(load)
</script>

<template>
  <PageHeader title="审计日志" description="记录身份、权限、人脸档案、考勤修正和终端管理等敏感操作。" />
  <section class="panel"><div class="panel__body"><div class="toolbar"><el-input v-model="action" placeholder="按动作精确筛选，例如 USER_UPDATED" clearable @keyup.enter="page = 1; load()" /><el-button @click="page = 1; load()">查询</el-button></div><el-table v-loading="loading" :data="result.items"><el-table-column label="时间" min-width="170"><template #default="{ row }">{{ formatDateTime(row.created_at) }}</template></el-table-column><el-table-column prop="action" label="动作" min-width="210"><template #default="{ row }"><code>{{ row.action }}</code></template></el-table-column><el-table-column prop="target_type" label="对象类型" min-width="145" /><el-table-column prop="target_id" label="对象 ID" min-width="205" show-overflow-tooltip /><el-table-column prop="reason" label="原因" min-width="170" show-overflow-tooltip /><el-table-column label="详情" width="80"><template #default="{ row }"><el-button link type="primary" @click="detail = row">查看</el-button></template></el-table-column></el-table><el-pagination v-if="result.total > 20" v-model:current-page="page" :page-size="20" :total="result.total" layout="prev, pager, next, total" class="pagination" @current-change="load" /></div></section>
  <el-dialog v-model="detail" title="审计详情" width="min(660px, 94vw)"><template v-if="detail"><el-descriptions :column="1" border><el-descriptions-item label="动作">{{ detail.action }}</el-descriptions-item><el-descriptions-item label="对象">{{ detail.target_type }} / {{ detail.target_id }}</el-descriptions-item><el-descriptions-item label="操作用户">{{ detail.actor_user_id || '设备或系统任务' }}</el-descriptions-item><el-descriptions-item label="原因">{{ detail.reason || '—' }}</el-descriptions-item></el-descriptions><div class="json-grid"><div><b>修改前</b><pre>{{ JSON.stringify(detail.before_data, null, 2) }}</pre></div><div><b>修改后</b><pre>{{ JSON.stringify(detail.after_data, null, 2) }}</pre></div></div></template></el-dialog>
</template>

<style scoped>.pagination { justify-content: flex-end; margin-top: 20px; }.json-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 18px; }.json-grid pre { min-height: 120px; max-height: 260px; overflow: auto; padding: 12px; border-radius: 8px; color: #e1e4ff; background: linear-gradient(145deg, #151943, #321c4b); font-size: 11px; white-space: pre-wrap; }@media(max-width:640px){.json-grid{grid-template-columns:1fr}}</style>

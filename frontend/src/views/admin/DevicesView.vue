<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CopyDocument, Monitor, Plus } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import { http, errorMessage } from '@/api/http'
import type { KioskDevice } from '@/types'
import { formatDateTime } from '@/utils/format'

const devices = ref<KioskDevice[]>([])
const loading = ref(false)
const dialog = ref(false)
const created = ref<KioskDevice | null>(null)
const form = reactive({ code: '', name: '', location: '' })
async function load() { loading.value = true; try { devices.value = (await http.get('/admin/devices')).data } catch (err) { ElMessage.error(errorMessage(err)) } finally { loading.value = false } }
function openCreate() { Object.assign(form, { code: '', name: '', location: '' }); created.value = null; dialog.value = true }
function openLocalSetup() { window.open('/kiosk/setup', '_blank', 'noopener') }
async function create() { try { created.value = (await http.post('/admin/devices', { ...form, code: form.code.toUpperCase() })).data; ElMessage.success('终端已创建，请立即保存密钥'); await load() } catch (err) { ElMessage.error(errorMessage(err)) } }
async function copyPairing() { if (!created.value?.secret) return; await navigator.clipboard.writeText(JSON.stringify({ code: created.value.code, secret: created.value.secret })); ElMessage.success('配对信息已复制') }
async function toggle(device: KioskDevice) { try { await http.patch(`/admin/devices/${device.id}`, { is_active: !device.is_active }); ElMessage.success(device.is_active ? '终端已停用' : '终端已启用'); await load() } catch (err) { ElMessage.error(errorMessage(err)) } }
async function edit(device: KioskDevice) { try { const { value } = await ElMessageBox.prompt('输入新的终端位置', `编辑 ${device.name}`, { inputValue: device.location }); await http.patch(`/admin/devices/${device.id}`, { location: value }); ElMessage.success('终端已更新'); await load() } catch (err) { if (err !== 'cancel' && err !== 'close') ElMessage.error(errorMessage(err)) } }
onMounted(load)
</script>

<template>
  <PageHeader title="终端管理" description="管理用于人脸打卡的固定电脑。当前电脑可以一键启用，无需手动复制编号和密钥。"><el-button type="primary" :icon="Monitor" @click="openLocalSetup">启用这台电脑</el-button><el-button :icon="Plus" @click="openCreate">添加其他终端</el-button></PageHeader>
  <el-alert title="只有在配置另一台电脑时，才需要使用“添加其他终端”并复制配对信息。局域网摄像头访问仍需使用 HTTPS。" type="info" :closable="false" show-icon class="device-alert" />
  <section class="panel"><div class="panel__body"><el-table v-loading="loading" :data="devices"><el-table-column prop="code" label="终端编号" min-width="125" /><el-table-column prop="name" label="名称" min-width="130" /><el-table-column prop="location" label="位置" min-width="170" /><el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '在线可用' : '已停用' }}</el-tag></template></el-table-column><el-table-column label="最后活动" min-width="170"><template #default="{ row }">{{ formatDateTime(row.last_seen_at) }}</template></el-table-column><el-table-column label="创建时间" min-width="170"><template #default="{ row }">{{ formatDateTime(row.created_at) }}</template></el-table-column><el-table-column label="操作" width="150" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="edit(row)">编辑位置</el-button><el-button link :type="row.is_active ? 'danger' : 'success'" @click="toggle(row)">{{ row.is_active ? '停用' : '启用' }}</el-button></template></el-table-column></el-table></div></section>
  <el-dialog v-model="dialog" title="创建 USB 摄像头终端" width="min(520px, 92vw)" :close-on-click-modal="!created"><template v-if="!created"><el-form label-position="top"><el-form-item label="终端编号"><el-input v-model="form.code" placeholder="例如 LAB-A-01" /></el-form-item><el-form-item label="显示名称"><el-input v-model="form.name" placeholder="例如 东门打卡机" /></el-form-item><el-form-item label="安装位置"><el-input v-model="form.location" placeholder="例如 生物实验室 A201" /></el-form-item></el-form></template><template v-else><el-alert title="密钥关闭后无法再次查看，请现在复制并到目标终端完成配对。" type="warning" :closable="false" show-icon /><div class="secret-box"><span>编号</span><code>{{ created.code }}</code><span>设备密钥</span><code>{{ created.secret }}</code></div></template><template #footer><el-button v-if="!created" @click="dialog = false">取消</el-button><el-button v-if="!created" type="primary" @click="create">创建</el-button><el-button v-else :icon="CopyDocument" type="primary" @click="copyPairing">复制配对信息</el-button><el-button v-if="created" @click="dialog = false">我已保存</el-button></template></el-dialog>
</template>

<style scoped>.device-alert { margin-bottom: 18px; }.secret-box { display: grid; grid-template-columns: 80px 1fr; gap: 12px; margin-top: 20px; padding: 18px; border-radius: 10px; background: linear-gradient(135deg, #f1f4ff, #fff0f8); }.secret-box span { color: #7a7d9d; }.secret-box code { overflow-wrap: anywhere; color: #5b63d8; }</style>

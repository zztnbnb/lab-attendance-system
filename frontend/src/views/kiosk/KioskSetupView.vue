<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowRight, Connection, Lock, Monitor, Setting, User } from '@element-plus/icons-vue'
import { http, errorMessage } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import type { KioskDevice } from '@/types'

const router = useRouter()
const auth = useAuthStore()
const form = reactive({
  code: localStorage.getItem('lab_device_code') ?? '',
  secret: localStorage.getItem('lab_device_secret') ?? '',
})
const busy = ref(false)
const authReady = ref(false)
const deviceValid = ref<boolean | null>(null)
const advancedOpen = ref<string[]>([])
const hasSavedDevice = computed(() => Boolean(form.code.trim() && form.secret.trim()))

function installationId() {
  const stored = localStorage.getItem('lab_installation_id')
  if (stored && /^[0-9a-f-]{36}$/i.test(stored)) return stored
  const created = crypto.randomUUID()
  localStorage.setItem('lab_installation_id', created)
  return created
}

function saveCredentials(device: KioskDevice) {
  if (!device.secret) throw new Error('服务器没有返回终端密钥')
  form.code = device.code
  form.secret = device.secret
  localStorage.setItem('lab_device_code', device.code)
  localStorage.setItem('lab_device_secret', device.secret)
}

async function enableThisComputer() {
  if (!auth.isAdmin) return adminLogin()
  busy.value = true
  try {
    const { data } = await http.post<KioskDevice>('/admin/devices/bootstrap-local', {
      installation_id: installationId(),
      name: '本机打卡终端',
      location: '当前电脑',
    })
    saveCredentials(data)
    deviceValid.value = true
    ElMessage.success('本机已启用，正在进入打卡页面')
    await router.replace('/kiosk')
  } catch (err) {
    ElMessage.error(errorMessage(err, '启用本机终端失败'))
  } finally {
    busy.value = false
  }
}

async function pair() {
  if (!form.code.trim() || !form.secret.trim()) {
    ElMessage.warning('请填写终端编号和设备密钥')
    return
  }
  busy.value = true
  try {
    const code = form.code.trim().toUpperCase()
    const secret = form.secret.trim()
    await http.get('/kiosk/device', {
      headers: { 'X-Device-Code': code, 'X-Device-Key': secret },
    })
    localStorage.setItem('lab_device_code', code)
    localStorage.setItem('lab_device_secret', secret)
    ElMessage.success('终端连接成功')
    await router.replace('/kiosk')
  } catch (err) {
    ElMessage.error(errorMessage(err, '编号或密钥不正确，请让管理员重新提供'))
  } finally {
    busy.value = false
  }
}

async function adminLogin() {
  if (auth.user && !auth.isAdmin) await auth.logout()
  await router.push({ name: 'login', query: { redirect: '/kiosk/setup' } })
}

onMounted(async () => {
  await auth.initialize()
  if (hasSavedDevice.value) {
    try {
      await http.get('/kiosk/device', {
        headers: { 'X-Device-Code': form.code.trim().toUpperCase(), 'X-Device-Key': form.secret.trim() },
      })
      deviceValid.value = true
    } catch {
      deviceValid.value = false
    }
  }
  authReady.value = true
})
</script>

<template>
  <main class="setup-page">
    <section class="setup-card">
      <div class="setup-head">
        <div class="setup-icon"><el-icon><Monitor /></el-icon></div>
        <div><p class="eyebrow">LABTIME KIOSK</p><h1>本机终端设置</h1></div>
      </div>

      <div v-if="!authReady" class="setup-loading"><el-skeleton :rows="3" animated /></div>

      <template v-else-if="hasSavedDevice && deviceValid !== false">
        <div class="ready-state">
          <span class="ready-dot" />
          <div><strong>这台电脑已经可以打卡</strong><small>终端 {{ form.code }}</small></div>
        </div>
        <el-button type="primary" size="large" :icon="ArrowRight" @click="router.replace('/kiosk')">返回打卡页面</el-button>
        <button v-if="auth.isAdmin" class="repair-link" :disabled="busy" @click="enableThisComputer">连接异常？重新启用本机</button>
      </template>

      <template v-else>
        <div class="not-ready">
          <h2>{{ hasSavedDevice ? '本机终端当前无法连接' : '这台电脑还不能打卡' }}</h2>
          <p>{{ hasSavedDevice ? '保存的终端配置可能已停用或失效，请由管理员重新启用。' : '首次只需由管理员启用一次。以后打开系统会直接进入人脸打卡，不再要求输入编号或密钥。' }}</p>
        </div>
        <el-button
          v-if="auth.isAdmin"
          type="primary"
          size="large"
          :icon="Monitor"
          :loading="busy"
          @click="enableThisComputer"
        >{{ hasSavedDevice ? '重新启用本机终端' : '一键启用本机终端' }}</el-button>
        <el-button v-else type="primary" size="large" :icon="User" @click="adminLogin">管理员登录并启用</el-button>
        <p v-if="auth.user && !auth.isAdmin" class="account-hint">当前登录的是普通用户账号，需要切换为管理员完成首次启用。</p>
      </template>

      <el-collapse v-model="advancedOpen" class="advanced">
        <el-collapse-item name="manual">
          <template #title><span class="advanced-title"><el-icon><Setting /></el-icon>高级配对（更换电脑或已有密钥时使用）</span></template>
          <el-form label-position="top" size="large" @submit.prevent="pair">
            <el-form-item label="终端编号"><el-input v-model="form.code" :prefix-icon="Connection" placeholder="例如 LAB-A-01" /></el-form-item>
            <el-form-item label="设备密钥"><el-input v-model="form.secret" :prefix-icon="Lock" type="password" show-password placeholder="粘贴管理员提供的设备密钥" /></el-form-item>
            <el-button native-type="submit" :loading="busy">使用编号和密钥连接</el-button>
          </el-form>
        </el-collapse-item>
      </el-collapse>

      <div class="setup-foot">
        <span>摄像头仅在打卡时启用，人脸原始画面不会保存。</span>
        <router-link :to="auth.isAdmin ? '/admin/devices' : '/login'">{{ auth.isAdmin ? '终端管理' : '返回登录' }}</router-link>
      </div>
    </section>
  </main>
</template>

<style scoped>
.setup-page { min-height: 100vh; display: grid; place-items: center; padding: 24px; background: radial-gradient(circle at 18% 10%, rgba(91,124,255,.52), transparent 34%), radial-gradient(circle at 90% 90%, rgba(241,92,168,.45), transparent 38%), linear-gradient(145deg, #111642, #2b194d); }
.setup-card { width: min(520px, 100%); padding: 38px 40px 30px; border: 1px solid rgba(255,255,255,.22); border-radius: 24px; background: rgba(255,255,255,.98); box-shadow: 0 30px 90px rgba(12,9,47,.55); }
.setup-head { display: flex; align-items: center; gap: 16px; margin-bottom: 30px; }
.setup-icon { flex: 0 0 54px; width: 54px; height: 54px; display: grid; place-items: center; border-radius: 15px; color: white; background: linear-gradient(135deg, #5b7cff, #f15ca8); box-shadow: 0 9px 24px rgba(109,99,225,.25); font-size: 26px; }
.eyebrow { margin: 0 0 5px; color: #df5da3; font-size: 10px; letter-spacing: 1.8px; }
.setup-card h1 { margin: 0; color: #282950; font-size: 25px; }
.setup-loading { padding: 10px 0 26px; }
.ready-state { display: flex; align-items: center; gap: 13px; margin-bottom: 24px; padding: 18px; border: 1px solid #dfe3ff; border-radius: 14px; background: linear-gradient(135deg, #f1f4ff, #fff2f8); }
.ready-state div { display: flex; flex-direction: column; gap: 5px; }
.ready-state strong { color: #34365d; font-size: 15px; }
.ready-state small { color: #888bab; font: 11px monospace; }
.ready-dot { width: 10px; height: 10px; border-radius: 50%; background: #6c83ff; box-shadow: 0 0 0 6px rgba(108,131,255,.13); }
.not-ready { margin-bottom: 23px; }
.not-ready h2 { margin: 0; color: #31335b; font-size: 20px; }
.not-ready p { margin: 10px 0 0; color: #7e809e; line-height: 1.75; font-size: 13px; }
.setup-card > .el-button { width: 100%; height: 50px; border-color: transparent; border-radius: 11px; background: linear-gradient(135deg, #5b7cff, #8c68ee 50%, #f15ca8); box-shadow: 0 10px 26px rgba(101,91,219,.22); font-weight: 700; }
.repair-link { display: block; margin: 15px auto 0; border: 0; color: #7376a0; background: transparent; cursor: pointer; font-size: 12px; }
.account-hint { margin: 12px 0 0; color: #8e7192; text-align: center; font-size: 11px; }
.advanced { margin-top: 28px; border-color: #ebeaf5; }
.advanced-title { display: inline-flex; align-items: center; gap: 7px; color: #777a9d; font-size: 12px; }
.advanced :deep(.el-collapse-item__header) { border-color: #ebeaf5; }
.advanced :deep(.el-collapse-item__wrap) { border: 0; }
.advanced :deep(.el-collapse-item__content) { padding: 20px 2px 4px; }
.advanced :deep(.el-form-item__label) { color: #555879; font-weight: 600; }
.advanced :deep(.el-button) { width: 100%; }
.setup-foot { display: flex; justify-content: space-between; gap: 20px; margin-top: 24px; color: #999bb4; font-size: 10px; }
.setup-foot a { flex: 0 0 auto; color: #626be5; }
@media (max-width: 560px) { .setup-card { padding: 30px 24px 24px; }.setup-foot { flex-direction: column; gap: 8px; } }
</style>

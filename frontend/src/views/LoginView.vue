<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { errorMessage } from '@/api/http'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const form = reactive({ username: '', realName: '', password: '', confirm: '' })
const error = ref('')
const mode = ref<'login' | 'register'>('login')

async function submit() {
  error.value = ''
  try {
    if (mode.value === 'register') {
      if (!/^\d{5,20}$/.test(form.username.trim())) throw new Error('学号必须为 5–20 位数字')
      if (!form.realName.trim()) throw new Error('请输入真实姓名')
      if (form.password.length < 10) throw new Error('密码至少需要 10 位')
      if (form.password !== form.confirm) throw new Error('两次输入的密码不一致')
      await auth.register(form.username.trim(), form.realName.trim(), form.password)
    } else {
      await auth.login(form.username.trim(), form.password)
    }
    ElMessage.success(mode.value === 'register' ? '注册成功，请先录入人脸' : `欢迎回来，${auth.user?.real_name}`)
    const fallback = mode.value === 'register' ? '/face' : (auth.isAdmin ? '/admin/dashboard' : '/dashboard')
    await router.replace(typeof route.query.redirect === 'string' ? route.query.redirect : fallback)
  } catch (err) { error.value = errorMessage(err, '无法连接后端，请确认“一键启动”窗口保持开启') }
}
</script>

<template>
  <main class="login-page">
    <section class="login-story">
      <div class="login-brand"><span>L</span><strong>LabTime</strong></div>
      <div class="login-story__content">
        <p class="eyebrow">SMART LAB ATTENDANCE</p>
        <h1>让实验室里的每一分钟<br>都清晰、可信。</h1>
        <p>通过现场人脸识别完成签到与签退，自动汇总有效时长，让成员专注实验，让管理更简单。</p>
        <div class="story-points">
          <div><b>01</b><span>加密存储人脸特征<br><small>原始画面不落盘</small></span></div>
          <div><b>02</b><span>签到签退状态机<br><small>防重复与重放</small></span></div>
          <div><b>03</b><span>可追溯的时长统计<br><small>跨日精准聚合</small></span></div>
        </div>
      </div>
      <small class="login-story__foot">仅用于已授权的实验室成员 · 武汉时间（UTC+8）</small>
    </section>
    <section class="login-form-wrap">
      <el-form class="login-form" size="large" @submit.prevent="submit">
        <div class="login-form__head"><h2>{{ mode === 'login' ? '登录系统' : '注册实验室账号' }}</h2><p>{{ mode === 'login' ? '使用学号或管理员分配的账号继续' : '使用学号作为账号，并设置自己的密码' }}</p></div>
        <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
        <el-form-item :label="mode === 'login' ? '账号 / 学号' : '学号'">
          <el-input v-model="form.username" :prefix-icon="User" autocomplete="username" placeholder="请输入学号" />
        </el-form-item>
        <el-form-item v-if="mode === 'register'" label="真实姓名"><el-input v-model="form.realName" autocomplete="name" placeholder="请输入真实姓名" /></el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" :prefix-icon="Lock" type="password" show-password autocomplete="current-password" placeholder="登录密码" @keyup.enter="submit" />
        </el-form-item>
        <el-form-item v-if="mode === 'register'" label="确认密码"><el-input v-model="form.confirm" :prefix-icon="Lock" type="password" show-password autocomplete="new-password" placeholder="再次输入密码" @keyup.enter="submit" /></el-form-item>
        <el-button native-type="submit" type="primary" :loading="auth.loading" class="login-button">{{ mode === 'login' ? '登录' : '注册并继续' }}</el-button>
        <button type="button" class="mode-switch" @click="mode = mode === 'login' ? 'register' : 'login'; error = ''">{{ mode === 'login' ? '首次使用？用学号注册' : '已有账号？返回登录' }}</button>
        <router-link to="/kiosk" class="login-kiosk-link">这是打卡电脑？进入人脸识别终端 →</router-link>
        <p class="privacy-note">注册后请进入“人脸录入”完成采集；提交成功后即可在终端打卡。</p>
      </el-form>
    </section>
  </main>
</template>

<style scoped>
.login-page { min-height: 100vh; display: grid; grid-template-columns: minmax(480px, 1.12fr) minmax(420px, .88fr); background: #fbfaff; }
.login-story { min-height: 100vh; position: relative; display: flex; flex-direction: column; padding: 42px 6vw; overflow: hidden; color: white; background: radial-gradient(circle at 82% 16%, rgba(241, 92, 168, .72) 0, transparent 29%), radial-gradient(circle at 0 100%, rgba(91, 124, 255, .76) 0, transparent 34%), linear-gradient(145deg, #141947 0%, #292057 52%, #431f57 100%); }
.login-story::after { content: ''; position: absolute; width: 430px; height: 430px; right: -155px; bottom: -180px; border: 1px solid #ff9bcb66; border-radius: 50%; box-shadow: 0 0 0 70px #7b79ff10, 0 0 0 140px #f15ca80c; }
.login-brand { display: flex; align-items: center; gap: 11px; font-size: 19px; }
.login-brand span { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 11px; background: linear-gradient(135deg, #63a2ff, #f15ca8); box-shadow: 0 8px 22px #18124455; font-weight: 900; }
.login-story__content { position: relative; z-index: 1; max-width: 680px; margin: auto 0; }
.eyebrow { margin: 0 0 24px !important; color: #ff9dcc !important; font-size: 12px !important; letter-spacing: 2.4px; }
.login-story h1 { margin: 0; font-size: clamp(38px, 4vw, 62px); line-height: 1.18; letter-spacing: -2px; }
.login-story__content > p { max-width: 570px; margin: 28px 0 0; color: #c9cbed; line-height: 1.8; font-size: 15px; }
.story-points { display: grid; grid-template-columns: repeat(3, 1fr); gap: 22px; margin-top: 60px; }
.story-points div { display: flex; gap: 12px; }
.story-points b { color: #8fafff; font: 600 12px monospace; }
.story-points span { color: #fff7fc; line-height: 1.4; font-size: 13px; }
.story-points small { color: #a7a8cf; }
.login-story__foot { position: relative; z-index: 1; color: #999bc5; }
.login-form-wrap { display: grid; place-items: center; padding: 40px; background: radial-gradient(circle at 100% 0, rgba(241,92,168,.09), transparent 34%), radial-gradient(circle at 0 100%, rgba(91,124,255,.09), transparent 38%); }
.login-form { width: min(390px, 100%); }
.login-form__head { margin-bottom: 34px; }
.login-form__head h2 { margin: 0; color: #25264f; font-size: 28px; }
.login-form__head p { margin: 9px 0 0; color: #8587a6; }
.login-form :deep(.el-form-item) { display: block; margin-top: 24px; }
.login-form :deep(.el-form-item__label) { display: block; margin-bottom: 7px; color: #555879; font-weight: 600; }
.login-form :deep(.el-input__wrapper) { height: 48px; border-radius: 10px; box-shadow: 0 0 0 1px #e2e1f1 inset; }
.login-button { width: 100%; height: 48px; margin-top: 10px; border-color: transparent; border-radius: 10px; background: linear-gradient(135deg, #5b7cff, #8b68ee 52%, #f15ca8); box-shadow: 0 10px 24px rgba(102, 94, 220, .22); font-weight: 700; }
.login-kiosk-link { display: block; margin-top: 24px; color: #616cf1; text-align: center; font-size: 13px; }
.mode-switch { display: block; width: 100%; margin-top: 16px; border: 0; color: #626cf0; background: transparent; cursor: pointer; font-size: 13px; }
.privacy-note { margin-top: 34px; color: #9a9bb2; text-align: center; font-size: 11px; }
@media (max-width: 860px) { .login-page { display: block; } .login-story { min-height: 250px; padding: 28px; } .login-story__content { margin: 42px 0; } .login-story h1 { font-size: 34px; } .login-story__content > p, .story-points, .login-story__foot { display: none; } .login-form-wrap { min-height: calc(100vh - 250px); padding: 34px 22px; } }
</style>

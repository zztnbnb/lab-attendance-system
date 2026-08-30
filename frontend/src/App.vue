<template>
  <div v-if="desktop" class="desktop-bar">
    <span class="desktop-title">LabTime 实验室打卡系统</span>
    <div class="desktop-actions">
      <button title="最小化" @click="desktop?.minimize()">−</button>
      <button title="最大化" @click="desktop?.toggleMaximize()">□</button>
      <button title="全屏" @click="desktop?.toggleFullscreen()">⛶</button>
      <button class="close" title="关闭" @click="desktop?.close()">×</button>
    </div>
  </div>
  <div v-if="desktop && update" class="update-banner" role="status">
    <span>发现新版本 {{ update.version }}</span>
    <button type="button" @click="downloadUpdate">查看并下载</button>
    <button class="dismiss" type="button" title="关闭提醒" @click="update = null">×</button>
  </div>
  <router-view />
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

const desktop = typeof window !== 'undefined' ? window.labtime : undefined
const update = ref<{ version: string; url: string; name?: string } | null>(null)
let removeUpdateListener: (() => void) | undefined

function downloadUpdate() {
  if (update.value) desktop?.openUpdate(update.value.url)
}

onMounted(async () => {
  if (!desktop) return
  removeUpdateListener = desktop.onUpdateAvailable((value) => { update.value = value })
  const result = await desktop.checkForUpdates()
  if (result.available && result.version && result.url) update.value = { version: result.version, url: result.url }
})

onBeforeUnmount(() => removeUpdateListener?.())
</script>

<style scoped>
.desktop-bar { position: fixed; z-index: 3000; inset: 0 0 auto; height: 34px; display: flex; align-items: center; justify-content: space-between; padding-left: 14px; color: #dce8ff; background: rgba(8, 17, 45, .94); -webkit-app-region: drag; }
.desktop-title { font-size: 12px; opacity: .85; }
.desktop-actions { height: 100%; display: flex; -webkit-app-region: no-drag; }
.desktop-actions button { width: 44px; border: 0; color: #dce8ff; background: transparent; font-size: 17px; cursor: pointer; }
.desktop-actions button:hover { background: rgba(255,255,255,.1); }
.desktop-actions .close:hover { background: #e6537a; color: #fff; }
.update-banner { position: fixed; z-index: 2999; top: 42px; right: 18px; display: flex; align-items: center; gap: 12px; padding: 10px 12px 10px 16px; color: #fff; background: linear-gradient(110deg, #2d5bce, #d64d9b); border: 1px solid rgba(255,255,255,.3); border-radius: 10px; box-shadow: 0 12px 32px rgba(3, 8, 28, .35); font-size: 13px; }
.update-banner button { border: 0; border-radius: 6px; padding: 6px 10px; color: #25123e; background: #fff; cursor: pointer; font-weight: 600; }
.update-banner .dismiss { padding: 2px 6px; color: #fff; background: transparent; font-size: 18px; font-weight: 400; }
</style>

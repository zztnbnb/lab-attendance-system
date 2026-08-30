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
  <router-view />
</template>

<script setup lang="ts">
const desktop = typeof window !== 'undefined' ? window.labtime : undefined
</script>

<style scoped>
.desktop-bar { position: fixed; z-index: 3000; inset: 0 0 auto; height: 34px; display: flex; align-items: center; justify-content: space-between; padding-left: 14px; color: #dce8ff; background: rgba(8, 17, 45, .94); -webkit-app-region: drag; }
.desktop-title { font-size: 12px; opacity: .85; }
.desktop-actions { height: 100%; display: flex; -webkit-app-region: no-drag; }
.desktop-actions button { width: 44px; border: 0; color: #dce8ff; background: transparent; font-size: 17px; cursor: pointer; }
.desktop-actions button:hover { background: rgba(255,255,255,.1); }
.desktop-actions .close:hover { background: #e6537a; color: #fff; }
</style>

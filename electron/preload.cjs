const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('labtime', {
  apiBase: process.env.LABTIME_DESKTOP_API_BASE || '',
  minimize: () => ipcRenderer.send('window:minimize'),
  toggleMaximize: () => ipcRenderer.send('window:toggle-maximize'),
  toggleFullscreen: () => ipcRenderer.send('window:toggle-fullscreen'),
  close: () => ipcRenderer.send('window:close'),
  isMaximized: () => ipcRenderer.invoke('window:is-maximized'),
  isFullscreen: () => ipcRenderer.invoke('window:is-fullscreen'),
})

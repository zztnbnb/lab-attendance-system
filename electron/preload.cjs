const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('labtime', {
  apiBase: process.env.LABTIME_DESKTOP_API_BASE || '',
  minimize: () => ipcRenderer.send('window:minimize'),
  toggleMaximize: () => ipcRenderer.send('window:toggle-maximize'),
  toggleFullscreen: () => ipcRenderer.send('window:toggle-fullscreen'),
  close: () => ipcRenderer.send('window:close'),
  isMaximized: () => ipcRenderer.invoke('window:is-maximized'),
  isFullscreen: () => ipcRenderer.invoke('window:is-fullscreen'),
  checkForUpdates: () => ipcRenderer.invoke('app:check-for-updates'),
  openUpdate: (url) => ipcRenderer.invoke('app:open-update', url),
  onUpdateAvailable: (callback) => {
    const listener = (_event, update) => callback(update)
    ipcRenderer.on('app:update-available', listener)
    return () => ipcRenderer.removeListener('app:update-available', listener)
  },
})

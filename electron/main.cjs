const { app, BrowserWindow, ipcMain, protocol, session, net, shell } = require('electron')
const path = require('node:path')
const fs = require('node:fs')
const { startBackend } = require('./process-manager.cjs')

let mainWindow
let backend
const isDev = process.argv.includes('--dev')
const RELEASES_URL = 'https://api.github.com/repos/zztnbnb/lab-attendance-system/releases/latest'
const RELEASE_PAGE_URL = 'https://github.com/zztnbnb/lab-attendance-system/releases/latest'

protocol.registerSchemesAsPrivileged([{ scheme: 'app', privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true } }])

function registerAppProtocol() {
  protocol.handle('app', (request) => {
    const url = new URL(request.url)
    let relative = decodeURIComponent(url.pathname).replace(/^\/+/, '')
    if (!relative) relative = 'index.html'
    const filePath = path.join(app.getAppPath(), 'frontend', 'dist', relative)
    return net.fetch(`file://${filePath}`)
  })
}

function normalizeVersion(value) {
  return String(value || '').trim().replace(/^v/i, '').split('-')[0].split('.').map((part) => Number.parseInt(part, 10) || 0)
}

function isNewerVersion(candidate, current) {
  const next = normalizeVersion(candidate)
  const installed = normalizeVersion(current)
  for (let index = 0; index < Math.max(next.length, installed.length); index += 1) {
    if ((next[index] || 0) !== (installed[index] || 0)) return (next[index] || 0) > (installed[index] || 0)
  }
  return false
}

async function checkForUpdates() {
  if (isDev) return { available: false, currentVersion: app.getVersion() }
  try {
    const response = await net.fetch(RELEASES_URL, {
      headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'LabTime-Desktop' },
    })
    if (!response.ok) throw new Error(`GitHub 返回 ${response.status}`)
    const release = await response.json()
    if (!release || release.draft || release.prerelease || !release.tag_name) {
      return { available: false, currentVersion: app.getVersion() }
    }
    const version = String(release.tag_name).replace(/^v/i, '')
    const result = {
      available: isNewerVersion(version, app.getVersion()),
      currentVersion: app.getVersion(),
      version,
      name: release.name || `LabTime v${version}`,
      url: release.html_url || RELEASE_PAGE_URL,
    }
    if (result.available) mainWindow?.webContents.send('app:update-available', result)
    return result
  } catch (error) {
    return { available: false, currentVersion: app.getVersion(), error: error instanceof Error ? error.message : String(error) }
  }
}

async function createWindow() {
  const projectRoot = isDev ? path.resolve(__dirname, '..') : process.resourcesPath
  backend = await startBackend({ appRoot: projectRoot, resourcesPath: process.resourcesPath, userData: app.getPath('userData') })
  process.env.LABTIME_DESKTOP_API_BASE = `http://127.0.0.1:${backend.port}/api/v1`
  mainWindow = new BrowserWindow({
    width: 1440, height: 900, minWidth: 1100, minHeight: 700,
    frame: false, backgroundColor: '#08112d', show: false,
    webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true },
  })
  mainWindow.once('ready-to-show', () => mainWindow.show())
  if (isDev) await mainWindow.loadURL('http://127.0.0.1:5173')
  else await mainWindow.loadURL('app://labtime/index.html')
  mainWindow.on('closed', () => { mainWindow = null })
}

app.whenReady().then(async () => {
  if (!isDev) registerAppProtocol()
  session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => callback(permission === 'media'))
  ipcMain.on('window:minimize', () => mainWindow?.minimize())
  ipcMain.on('window:toggle-maximize', () => mainWindow?.isMaximized() ? mainWindow.unmaximize() : mainWindow?.maximize())
  ipcMain.on('window:toggle-fullscreen', () => { if (mainWindow) mainWindow.setFullScreen(!mainWindow.isFullScreen()) })
  ipcMain.on('window:close', () => mainWindow?.close())
  ipcMain.handle('window:is-maximized', () => mainWindow?.isMaximized() ?? false)
  ipcMain.handle('window:is-fullscreen', () => mainWindow?.isFullScreen() ?? false)
  ipcMain.handle('app:check-for-updates', () => checkForUpdates())
  ipcMain.handle('app:open-update', async (_event, url) => {
    const target = typeof url === 'string' && /^https:\/\/github\.com\/zztnbnb\/lab-attendance-system\/releases\//.test(url)
      ? url
      : RELEASE_PAGE_URL
    await shell.openExternal(target)
  })
  try { await createWindow() } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    const errorWindow = new BrowserWindow({ width: 700, height: 420, autoHideMenuBar: true })
    await errorWindow.loadURL(`data:text/html;charset=utf-8,<body style="font-family:sans-serif;padding:32px;background:%2308112d;color:white"><h2>LabTime 启动失败</h2><pre style="white-space:pre-wrap">${encodeURIComponent(message)}</pre><p>请检查日志和模型文件后重试。</p></body>`)
  }
  if (!isDev) {
    setTimeout(() => checkForUpdates(), 2500)
    setInterval(() => checkForUpdates(), 6 * 60 * 60 * 1000)
  }
})

app.on('before-quit', () => { if (backend?.child && !backend.child.killed) backend.child.kill() })
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })

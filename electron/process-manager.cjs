const { spawn } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')
const http = require('node:http')

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = http.createServer()
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port
      server.close(() => resolve(port))
    })
    server.on('error', reject)
  })
}

function waitForHealth(url, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs
  return new Promise((resolve, reject) => {
    const check = () => {
      const request = http.get(url, (response) => {
        response.resume()
        if (response.statusCode >= 200 && response.statusCode < 500) return resolve()
        retry()
      })
      request.on('error', retry)
      request.setTimeout(1500, () => { request.destroy(); retry() })
    }
    const retry = () => {
      if (Date.now() >= deadline) return reject(new Error('后端服务启动超时，请查看日志'))
      setTimeout(check, 350)
    }
    check()
  })
}

async function startBackend({ appRoot, resourcesPath, userData }) {
  const port = await findFreePort()
  const dataDir = path.join(userData, 'data')
  fs.mkdirSync(dataDir, { recursive: true })
  const modelsDir = path.join(resourcesPath, 'models')
  const packaged = path.join(resourcesPath, 'backend', 'labtime-api.exe')
  const env = {
    ...process.env,
    PORT: String(port),
    DATABASE_URL: `sqlite+aiosqlite:///${path.join(dataDir, 'lab_attendance.db').replaceAll('\\', '/')}`,
    YUNET_MODEL_PATH: path.join(modelsDir, 'face_detection_yunet_2023mar.onnx'),
    SFACE_MODEL_PATH: path.join(modelsDir, 'face_recognition_sface_2021dec.onnx'),
    ALLOWED_ORIGINS: 'app://labtime',
    AUTO_CREATE_TABLES: 'true',
  }
  let command
  let args
  let cwd = appRoot
  if (fs.existsSync(packaged)) {
    command = packaged
    args = ['--host', '127.0.0.1', '--port', String(port)]
    cwd = path.dirname(packaged)
  } else {
    const python = process.env.LABTIME_PYTHON || path.join(appRoot, '.venv', 'Scripts', 'python.exe')
    command = python
    args = ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(port)]
    cwd = path.join(appRoot, 'backend')
  }
  const child = spawn(command, args, { cwd, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  const logs = []
  child.stdout.on('data', (data) => logs.push(data.toString()))
  child.stderr.on('data', (data) => logs.push(data.toString()))
  try {
    await waitForHealth(`http://127.0.0.1:${port}/api/health`)
  } catch (error) {
    child.kill()
    error.message += `\n${logs.join('').slice(-2000)}`
    throw error
  }
  return { child, port, logs }
}

module.exports = { startBackend }

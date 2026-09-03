import { onBeforeUnmount, ref, type Ref } from 'vue'

export function useCamera(video: Ref<HTMLVideoElement | null>) {
  let stream: MediaStream | null = null
  const devices = ref<MediaDeviceInfo[]>([])
  const activeDeviceId = ref('')

  async function refreshDevices() {
    if (!navigator.mediaDevices?.enumerateDevices) return []
    devices.value = (await navigator.mediaDevices.enumerateDevices()).filter((item) => item.kind === 'videoinput')
    if (!activeDeviceId.value && devices.value[0]) activeDeviceId.value = devices.value[0].deviceId
    return devices.value
  }

  async function start(deviceId = activeDeviceId.value) {
    stop()
    const videoConstraints: MediaTrackConstraints = {
      width: { ideal: 1280 },
      height: { ideal: 720 },
      facingMode: 'user',
    }
    if (deviceId) videoConstraints.deviceId = { exact: deviceId }
    stream = await navigator.mediaDevices.getUserMedia({ video: videoConstraints, audio: false })
    const track = stream.getVideoTracks()[0]
    activeDeviceId.value = track?.getSettings().deviceId ?? deviceId
    if (video.value) {
      video.value.srcObject = stream
      await video.value.play()
    }
    // Browsers expose camera labels only after permission is granted.
    await refreshDevices()
  }

  function stop() {
    stream?.getTracks().forEach((track) => track.stop())
    stream = null
    if (video.value) video.value.srcObject = null
  }

  async function captureFrame(): Promise<Blob> {
    const source = video.value
    if (!source) throw new Error('摄像头尚未准备好')
    const deadline = Date.now() + 2500
    while ((!source.videoWidth || !source.videoHeight) && Date.now() < deadline) {
      await new Promise((resolve) => window.setTimeout(resolve, 80))
    }
    if (!source.videoWidth || !source.videoHeight) throw new Error('摄像头画面尚未准备好，请稍候再试')
    const videoWithFrameCallback = source as HTMLVideoElement & {
      requestVideoFrameCallback?: (callback: () => void) => number
    }
    if (videoWithFrameCallback.requestVideoFrameCallback) {
      await new Promise<void>((resolve) => {
        videoWithFrameCallback.requestVideoFrameCallback?.(() => resolve())
      })
    } else {
      await new Promise((resolve) => window.setTimeout(resolve, 80))
    }
    const canvas = document.createElement('canvas')
    canvas.width = Math.min(source.videoWidth, 960)
    canvas.height = Math.round((canvas.width * source.videoHeight) / source.videoWidth)
    const context = canvas.getContext('2d')
    if (!context) throw new Error('浏览器不支持画面采集')
    context.drawImage(source, 0, 0, canvas.width, canvas.height)
    return await new Promise((resolve, reject) => canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('画面编码失败'))),
      'image/jpeg',
      0.86,
    ))
  }

  async function captureSequence(count = 5, intervalMs = 350): Promise<Blob[]> {
    const frames: Blob[] = []
    for (let i = 0; i < count; i += 1) {
      frames.push(await captureFrame())
      if (i < count - 1) await new Promise((resolve) => window.setTimeout(resolve, intervalMs))
    }
    return frames
  }

  onBeforeUnmount(stop)
  return { start, stop, captureSequence, refreshDevices, devices, activeDeviceId }
}

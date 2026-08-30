/// <reference types="vite/client" />
interface Window {
  labtime?: {
    apiBase: string
    minimize(): void
    toggleMaximize(): void
    toggleFullscreen(): void
    close(): void
    isMaximized(): Promise<boolean>
    isFullscreen(): Promise<boolean>
  }
}

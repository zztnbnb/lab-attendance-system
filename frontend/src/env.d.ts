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
    checkForUpdates(): Promise<{ available: boolean; version?: string; url?: string; error?: string }>
    openUpdate(url: string): Promise<void>
    onUpdateAvailable(callback: (update: { version: string; url: string; name?: string }) => void): () => void
  }
}

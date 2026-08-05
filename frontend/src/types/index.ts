import type { components } from '@/api/schema'

type Schemas = components['schemas']

export type Role = Schemas['Role']
export type FaceProfileStatus = Schemas['FaceProfileStatus']
export type AttendanceStatus = Schemas['AttendanceStatus']
export type AllowedAction = Schemas['AllowedAction']

export type User = Schemas['UserPublic']
export type AttendanceSession = Schemas['AttendancePublic']
export type DailyDuration = Schemas['DailyDuration']
export type UserStatistics = Schemas['UserStatistics']
export type CurrentUser = Schemas['CurrentUserItem']
export type RankingItem = Schemas['RankingItem']
export type HourlyCount = Schemas['HourlyCount']
export type AdminStatistics = Schemas['AdminStatistics']
export type FaceProfile = Schemas['FaceProfilePublic']
export type RecognitionSession = Schemas['RecognitionSessionPublic']
export type RecognitionResult = Schemas['RecognitionVerifyResponse']
export type AuditLog = Schemas['AuditLogPublic']
export type KioskDevice = Schemas['DevicePublic'] & Partial<Pick<Schemas['DeviceCreated'], 'secret'>>
export type KioskDashboard = Schemas['KioskDashboard']
export type KioskPresencePage = Schemas['KioskPresencePage']
export type KioskRecordPage = Schemas['KioskRecordPage']

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

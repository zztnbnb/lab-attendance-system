import { describe, expect, it } from 'vitest'
import { compactDuration, formatDuration } from '@/utils/format'

describe('时长格式化', () => {
  it('将秒转换为小时和分钟', () => {
    expect(formatDuration(7260)).toBe('2 小时 1 分钟')
    expect(formatDuration(1800)).toBe('30 分钟')
  })

  it('对空值和负值按零处理', () => {
    expect(formatDuration(null)).toBe('0 分钟')
    expect(formatDuration(-1)).toBe('0 分钟')
    expect(compactDuration(5400)).toBe('1.5h')
  })
})

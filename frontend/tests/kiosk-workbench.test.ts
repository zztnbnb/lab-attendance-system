import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import KioskIdentitySignal from '@/views/kiosk/components/KioskIdentitySignal.vue'
import KioskMetricGrid from '@/views/kiosk/components/KioskMetricGrid.vue'

describe('终端实时工作台组件', () => {
  it('展示四项实时终端指标', () => {
    const wrapper = mount(KioskMetricGrid, {
      props: { currentCount: 3, todayCheckins: 8, todayCheckouts: 5, exceptionCount: 1 },
    })
    expect(wrapper.text()).toContain('当前在实验室')
    expect(wrapper.text()).toContain('今日签到')
    expect(wrapper.text()).toContain('待处理异常')
    expect(wrapper.text()).toContain('8')
  })

  it('在保存成功后展示姓名、服务器时间并允许下一位', async () => {
    const wrapper = mount(KioskIdentitySignal, {
      props: {
        state: 'success',
        realName: '张哲天',
        message: '签到成功，记录已保存',
        actionLabel: '签到成功',
        savedTime: '2026-08-04 15:30:00',
        processingMs: 124,
        matchScore: 0.93,
        qualityHint: null,
        countdown: 8,
      },
      global: { plugins: [ElementPlus] },
    })
    expect(wrapper.text()).toContain('张哲天')
    expect(wrapper.text()).toContain('服务器时间')
    expect(wrapper.text()).toContain('124 ms')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('next')).toHaveLength(1)
  })

  it('未匹配状态不显示身份姓名', () => {
    const wrapper = mount(KioskIdentitySignal, {
      props: {
        state: 'error',
        message: '未找到匹配的人脸档案',
        countdown: 0,
      },
      global: { plugins: [ElementPlus] },
    })
    expect(wrapper.text()).toContain('本次未完成')
    expect(wrapper.text()).toContain('未找到匹配的人脸档案')
    expect(wrapper.find('button').exists()).toBe(false)
  })
})

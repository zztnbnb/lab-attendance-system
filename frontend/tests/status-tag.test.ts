import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import StatusTag from '@/components/StatusTag.vue'

describe('考勤状态标签', () => {
  it('展示中文漏签退状态', () => {
    const wrapper = mount(StatusTag, { props: { status: 'MISSING_CHECKOUT' }, global: { plugins: [ElementPlus] } })
    expect(wrapper.text()).toContain('漏签退')
  })

  it('未知状态保留原始值', () => {
    const wrapper = mount(StatusTag, { props: { status: 'CUSTOM' }, global: { plugins: [ElementPlus] } })
    expect(wrapper.text()).toContain('CUSTOM')
  })
})

import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('frappe-ui', () => ({
  FeatherIcon: { props: ['name'], template: '<i class="feather" :data-name="name" />' },
  LoadingIndicator: { template: '<i class="spinner" />' },
  call: vi.fn(),
}))

import AppBadge from '@/components/ui/AppBadge.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
import AppSwitch from '@/components/ui/AppSwitch.vue'
import AppTabs from '@/components/ui/AppTabs.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppAvailabilityPicker from '@/components/ui/AppAvailabilityPicker.vue'

describe('AppBadge', () => {
  it('renders label with theme tone and falls back to gray', () => {
    const w = mount(AppBadge, { props: { label: 'Done', theme: 'green' } })
    expect(w.text()).toBe('Done')
    expect(w.classes().join(' ')).not.toContain('bg-app-panel-2')
    expect(mount(AppBadge, { props: { label: 'x', theme: 'nope' } }).classes().join(' ')).toContain('bg-app-panel-2')
  })
  it('slot beats label; size md is larger', () => {
    const w = mount(AppBadge, { props: { label: 'a', size: 'md' }, slots: { default: 'slotted' } })
    expect(w.text()).toBe('slotted')
    expect(w.classes()).toContain('px-2.5')
  })
})

describe('AppButton', () => {
  it('emits click', async () => {
    const w = mount(AppButton, { props: { label: 'Go' } })
    await w.trigger('click')
    expect(w.emitted('click')).toHaveLength(1)
  })
  it('does not emit when disabled or loading, and shows spinner', async () => {
    const d = mount(AppButton, { props: { label: 'Go', disabled: true } })
    await d.trigger('click')
    expect(d.emitted('click')).toBeUndefined()
    expect(d.attributes('disabled')).toBeDefined()
    const l = mount(AppButton, { props: { label: 'Go', loading: true } })
    await l.trigger('click')
    expect(l.emitted('click')).toBeUndefined()
    expect(l.find('.spinner').exists()).toBe(true)
  })
  it('icon-only buttons are square; red theme turns primary into danger', () => {
    const icon = mount(AppButton, { props: { icon: 'plus' } })
    expect(icon.classes()).toContain('w-8')
    expect(icon.find('span').exists()).toBe(false)
    expect(mount(AppButton, { props: { label: 'x', theme: 'red' } }).classes().join(' ')).toContain('bg-red-600')
  })
  it('tooltip becomes title', () => {
    expect(mount(AppButton, { props: { label: 'x', tooltip: 'Hint' } }).attributes('title')).toBe('Hint')
  })
})

describe('AppCheckbox / AppSwitch', () => {
  it('checkbox emits boolean', async () => {
    const w = mount(AppCheckbox, { props: { modelValue: false, label: 'L' } })
    await w.find('input').setValue(true)
    expect(w.emitted('update:modelValue')[0]).toEqual([true])
    expect(w.text()).toBe('L')
  })
  it('checkbox disabled', () => {
    expect(mount(AppCheckbox, { props: { disabled: true } }).find('input').attributes('disabled')).toBeDefined()
  })
  it('switch emits 1/0', async () => {
    const w = mount(AppSwitch, { props: { modelValue: 0, label: 'S', description: 'd' } })
    await w.find('input').setValue(true)
    expect(w.emitted('update:modelValue')[0]).toEqual([1])
    await w.find('input').setValue(false)
    expect(w.emitted('update:modelValue')[1]).toEqual([0])
    expect(w.text()).toContain('d')
  })
})

describe('AppTabs', () => {
  it('accepts strings or objects and emits the value', async () => {
    const w = mount(AppTabs, { props: { modelValue: 'a', tabs: ['a', { label: 'Bee', value: 'b' }] } })
    const buttons = w.findAll('button')
    expect(buttons.map((b) => b.text())).toEqual(['a', 'Bee'])
    expect(buttons[0].classes()).toContain('border-app-primary')
    await buttons[1].trigger('click')
    expect(w.emitted('update:modelValue')[0]).toEqual(['b'])
  })
})

describe('AppInput', () => {
  it('text input emits value and shows required star / hint / error', async () => {
    const w = mount(AppInput, { props: { modelValue: 'x', label: 'Name', required: true, hint: 'help' } })
    expect(w.text()).toContain('Name *')
    expect(w.text()).toContain('help')
    await w.find('input').setValue('new')
    expect(w.emitted('update:modelValue')[0]).toEqual(['new'])
    await w.setProps({ error: 'bad' })
    expect(w.text()).toContain('bad')
    expect(w.text()).not.toContain('help')
    expect(w.find('input').classes()).toContain('border-red-500')
  })
  it('null model renders empty', () => {
    expect(mount(AppInput, { props: { modelValue: null } }).find('input').element.value).toBe('')
  })
  it('password toggles visibility', async () => {
    const w = mount(AppInput, { props: { modelValue: 's', type: 'password' } })
    expect(w.find('input').attributes('type')).toBe('password')
    await w.find('button').trigger('click')
    expect(w.find('input').attributes('type')).toBe('text')
  })
  it('prefix pads the input', () => {
    const w = mount(AppInput, { props: { modelValue: '1', prefix: '$' } })
    expect(w.text()).toContain('$')
    expect(w.find('input').classes()).toContain('pl-7')
  })
})

describe('AppAvailabilityPicker', () => {
  it('parses the model into days and times', () => {
    const w = mount(AppAvailabilityPicker, { props: { modelValue: 'Mon - Wed, 9:30 AM - 5:00 PM' } })
    const active = w.findAll('button').filter((b) => b.classes().includes('text-app-primary')).map((b) => b.text())
    expect(active).toEqual(['Mon', 'Tue', 'Wed'])
    const [start, end] = w.findAll('input')
    expect(start.element.value).toBe('09:30')
    expect(end.element.value).toBe('17:00')
  })
  it('emits the formatted string as chips and times change', async () => {
    const w = mount(AppAvailabilityPicker, { props: { modelValue: '' } })
    const day = (d) => w.findAll('button').find((b) => b.text() === d)
    await day('Fri').trigger('click')
    await day('Thu').trigger('click')
    const [start, end] = w.findAll('input')
    await start.setValue('09:00')
    await end.setValue('18:00')
    const events = w.emitted('update:modelValue')
    expect(events.at(-1)).toEqual(['Thu - Fri, 9:00 AM - 6:00 PM'])
  })
  it('disabled ignores clicks', async () => {
    const w = mount(AppAvailabilityPicker, { props: { modelValue: '', disabled: true } })
    await w.findAll('button')[0].trigger('click')
    expect(w.emitted('update:modelValue')).toBeUndefined()
  })
})

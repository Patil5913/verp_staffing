import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

vi.mock('frappe-ui', () => ({
  call: vi.fn(), debounce: (f) => f,
  FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' },
  Popover: { template: '<div />' },
  Combobox: { props: ['modelValue', 'options'], template: '<div class="combo" />' },
}))

import AppDurationInput from '@/components/ui/AppDurationInput.vue'
import AppChipInput from '@/components/ui/AppChipInput.vue'
import AppTimeInput from '@/components/ui/AppTimeInput.vue'
import AppSearchInput from '@/components/ui/AppSearchInput.vue'
import AppTextarea from '@/components/ui/AppTextarea.vue'
import TruncatedText from '@/components/ui/TruncatedText.vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'

const state = (w) => ({ amount: w.find('input').element.value, unit: w.findComponent(AppCombobox).props('modelValue') })

describe('AppDurationInput (hh:mm storage)', () => {
  const mk = (props = {}) => mount(AppDurationInput, { props: { storage: 'hhmm', modelValue: '', ...props } })
  it('shows a stored value in the largest unit that divides it evenly', () => {
    expect(state(mk({ modelValue: '48:00' }))).toEqual({ amount: '48', unit: 'Hours' })
    expect(state(mk({ modelValue: '01:30' }))).toEqual({ amount: '90', unit: 'Minutes' })
    expect(state(mk({ modelValue: '00:45' }))).toEqual({ amount: '45', unit: 'Minutes' })
  })
  it('an offered Days unit is used for whole days', () => {
    expect(state(mk({ modelValue: '48:00', units: ['Minutes', 'Hours', 'Days'] }))).toEqual({ amount: '2', unit: 'Days' })
  })
  it('an empty value shows an empty amount and the first unit', () => {
    expect(state(mk())).toEqual({ amount: '', unit: 'Minutes' })
    expect(state(mk({ modelValue: '00:00' }))).toEqual({ amount: '0', unit: 'Minutes' })
  })
  it('the unit the record was saved with wins over the one worked out', () => {
    expect(state(mk({ modelValue: '48:00', unit: 'Minutes' }))).toEqual({ amount: '2880', unit: 'Minutes' })
    expect(state(mk({ modelValue: '48:00', unit: 'Weeks' })).unit).toBe('Hours') // not an offered unit
  })
  it('typing converts back to hh:mm', async () => {
    const w = mk({ modelValue: '01:00' })
    await w.find('input').setValue('3')
    expect(w.emitted('update:modelValue').at(-1)).toEqual(['03:00'])
    await w.find('input').setValue('1.5')
    expect(w.emitted('update:modelValue').at(-1)).toEqual(['01:30'])
  })
  it('changing the unit keeps the typed amount and says so', async () => {
    const w = mk({ modelValue: '02:00' })
    w.findComponent(AppCombobox).vm.$emit('update:modelValue', 'Minutes')
    await nextTick()
    expect(w.emitted('update:unit')).toEqual([['Minutes']])
    expect(w.emitted('update:modelValue').at(-1)).toEqual(['00:02'])
  })
  it('clearing the amount clears the value; negatives are floored at zero', async () => {
    const w = mk({ modelValue: '01:00' })
    await w.find('input').setValue('')
    expect(w.emitted('update:modelValue').at(-1)).toEqual([''])
    await w.find('input').setValue('-5')
    expect(w.emitted('update:modelValue').at(-1)).toEqual(['00:00'])
  })
  it('follows the model from outside, but not its own echo', async () => {
    const w = mk({ modelValue: '01:00' })
    await w.find('input').setValue('3')
    await w.setProps({ modelValue: '03:00' })
    expect(state(w).amount).toBe('3')
    await w.setProps({ modelValue: '10:00' })
    expect(state(w)).toEqual({ amount: '10', unit: 'Hours' })
  })
  it('label, error (beats hint), hint, muted and disabled', () => {
    const w = mk({ label: 'Expiry', hint: 'h', error: 'bad', muted: true, disabled: true })
    expect(w.text()).toContain('Expiry')
    expect(w.text()).toContain('bad')
    expect(w.text()).not.toContain('h')
    expect(w.find('.opacity-50').exists()).toBe(true)
    expect(w.find('input').attributes('disabled')).toBeDefined()
    expect(mk({ hint: 'only hint' }).text()).toContain('only hint')
  })
})

describe('AppDurationInput (seconds storage)', () => {
  const mk = (props = {}) => mount(AppDurationInput, { props: { storage: 'seconds', modelValue: '', ...props } })
  it('reads and writes whole seconds', async () => {
    expect(state(mk({ modelValue: 7200 }))).toEqual({ amount: '2', unit: 'Hours' })
    expect(state(mk({ modelValue: '1800' }))).toEqual({ amount: '30', unit: 'Minutes' })
    const w = mk({ modelValue: 3600 })
    await w.find('input').setValue('90')
    expect(w.emitted('update:modelValue').at(-1)).toEqual(['324000']) // 90 hours, in seconds
  })
})

describe('AppChipInput', () => {
  it('shows chips and removes the clicked one', async () => {
    const w = mount(AppChipInput, { props: { modelValue: ['a', 'b'] } })
    expect(w.findAll('span.rounded-lg').map((s) => s.text())).toEqual(['a', 'b'])
    await w.findAll('span.rounded-lg')[0].find('button').trigger('click')
    expect(w.emitted('update:modelValue')).toEqual([[['b']]])
  })
  it('with options it offers only the ones not yet chosen, and adds a pick once', () => {
    const w = mount(AppChipInput, { props: { modelValue: ['a'], options: ['a', 'b', { value: 'c', label: 'C' }] } })
    expect(w.findComponent(AppCombobox).props('options')).toEqual(['b', { value: 'c', label: 'C' }])
    w.findComponent(AppCombobox).vm.$emit('update:modelValue', 'b')
    w.findComponent(AppCombobox).vm.$emit('update:modelValue', 'a')
    w.findComponent(AppCombobox).vm.$emit('update:modelValue', '')
    expect(w.emitted('update:modelValue')).toEqual([[['a', 'b']]])
  })
  it('without options it takes typed values on Enter or comma', async () => {
    const w = mount(AppChipInput, { props: { modelValue: [] } })
    const input = w.find('input')
    await input.setValue('  x  ')
    await input.trigger('keydown', { key: 'Enter' })
    expect(w.emitted('update:modelValue')).toEqual([[['x']]])
    expect(input.element.value).toBe('')
    await input.setValue('y')
    await input.trigger('keydown', { key: ',' })
    expect(w.emitted('update:modelValue')).toHaveLength(2)
  })
  it('blur also commits; blank input does nothing', async () => {
    const w = mount(AppChipInput, { props: { modelValue: [] } })
    await w.find('input').setValue('z')
    await w.find('input').trigger('blur')
    expect(w.emitted('update:modelValue')).toEqual([[['z']]])
    await w.find('input').setValue('   ')
    await w.find('input').trigger('blur')
    expect(w.emitted('update:modelValue')).toHaveLength(1)
  })
  it('duplicates and invalid values are refused with a message', async () => {
    const validate = (v) => (v.includes('@') ? '' : 'Not an email')
    const w = mount(AppChipInput, { props: { modelValue: ['a@x.com'], validate } })
    const input = w.find('input')
    await input.setValue('a@x.com')
    await input.trigger('keydown', { key: 'Enter' })
    expect(w.text()).toContain('"a@x.com" is already added')
    await input.setValue('nope')
    await input.trigger('keydown', { key: 'Enter' })
    expect(w.text()).toContain('Not an email')
    expect(w.emitted('update:modelValue')).toBeUndefined()
    await input.setValue('b@x.com')
    await input.trigger('keydown', { key: 'Enter' })
    expect(w.emitted('update:modelValue')).toEqual([[['a@x.com', 'b@x.com']]])
    expect(w.text()).not.toContain('Not an email')
  })
  it('a custom normaliser (e.g. lowercasing) is applied', async () => {
    const w = mount(AppChipInput, { props: { modelValue: [], normalize: (v) => v.trim().toLowerCase() } })
    await w.find('input').setValue(' ANN ')
    await w.find('input').trigger('keydown', { key: 'Enter' })
    expect(w.emitted('update:modelValue')).toEqual([[['ann']]])
  })
  it('disabled: no remove buttons, no input', () => {
    const w = mount(AppChipInput, { props: { modelValue: ['a'], disabled: true } })
    expect(w.find('button').exists()).toBe(false)
    expect(w.find('input').exists()).toBe(false)
  })
})

describe('AppTimeInput', () => {
  const shown = (v) => mount(AppTimeInput, { props: { modelValue: v } }).find('input').element.value
  it('pads Frappe\'s unpadded hours and adds seconds', () => {
    expect(shown('1:01:01')).toBe('01:01:01')
    expect(shown('09:30')).toBe('09:30:00')
    expect(shown('23:59:59')).toBe('23:59:59')
    expect(shown('')).toBe('')
  })
  it('emits what the browser gives; a cleared box emits nothing', async () => {
    const w = mount(AppTimeInput, { props: { modelValue: '' } })
    await w.find('input').setValue('10:15:00')
    expect(w.emitted('update:modelValue')).toEqual([['10:15:00']])
    await w.find('input').setValue('')
    expect(w.emitted('update:modelValue')).toHaveLength(1)
  })
  it('label, required star, error, disabled', () => {
    const w = mount(AppTimeInput, { props: { label: 'From', required: true, error: 'bad', disabled: true } })
    expect(w.text()).toContain('From *')
    expect(w.text()).toContain('bad')
    expect(w.find('input').classes()).toContain('border-red-500')
    expect(w.find('input').attributes('disabled')).toBeDefined()
  })
})

describe('AppSearchInput', () => {
  it('v-model and placeholder', async () => {
    const w = mount(AppSearchInput, { props: { modelValue: 'x', placeholder: 'Find' } })
    expect(w.find('input').element.value).toBe('x')
    expect(w.find('input').attributes('placeholder')).toBe('Find')
    await w.find('input').setValue('y')
    expect(w.emitted('update:modelValue')).toEqual([['y']])
  })
  it('class goes on the wrapper, other attributes on the input', () => {
    const w = mount(AppSearchInput, { attrs: { class: 'w-72', 'data-x': '1', maxlength: '5' } })
    expect(w.classes()).toContain('w-72')
    expect(w.find('input').attributes('data-x')).toBe('1')
    expect(w.find('input').classes()).not.toContain('w-72')
  })
  it('the suffix slot makes room on the right', () => {
    const plain = mount(AppSearchInput)
    expect(plain.find('input').classes()).toContain('pr-3')
    const w = mount(AppSearchInput, { slots: { suffix: '<b id="s" />' } })
    expect(w.find('#s').exists()).toBe(true)
    expect(w.find('input').classes()).toContain('pr-9')
  })
  it('compact is shorter', () => {
    expect(mount(AppSearchInput, { props: { compact: true } }).find('input').classes()).toContain('h-7')
  })
})

describe('AppTextarea', () => {
  it('v-model, rows, placeholder, label star and error', async () => {
    const w = mount(AppTextarea, { props: { modelValue: 'hi', rows: 5, placeholder: 'p', label: 'Notes', required: true, error: 'bad' } })
    const ta = w.find('textarea')
    expect(ta.element.value).toBe('hi')
    expect(ta.attributes('rows')).toBe('5')
    expect(ta.classes()).toContain('border-red-500')
    expect(w.text()).toContain('Notes *')
    expect(w.text()).toContain('bad')
    await ta.setValue('new')
    expect(w.emitted('update:modelValue')).toEqual([['new']])
  })
  it('exposes the element and focus; bare drops the border', () => {
    const w = mount(AppTextarea, { props: { bare: true }, attachTo: document.body })
    expect(w.vm.el).toBe(w.find('textarea').element)
    w.vm.focus()
    expect(document.activeElement).toBe(w.find('textarea').element)
    expect(w.find('textarea').classes()).not.toContain('border-app-border')
    w.unmount()
  })
  it('disabled', () => {
    expect(mount(AppTextarea, { props: { disabled: true } }).find('textarea').attributes('disabled')).toBeDefined()
  })
})

describe('TruncatedText', () => {
  it('short text is a plain truncated span', () => {
    const w = mount(TruncatedText, { props: { text: 'short' } })
    expect(w.text()).toBe('short')
    expect(w.find('button').exists()).toBe(false)
  })
  it('long text can be expanded and collapsed', async () => {
    const w = mount(TruncatedText, { props: { text: 'x'.repeat(200), limit: 120 } })
    expect(w.find('button').text()).toBe('View more')
    expect(w.find('span.truncate').exists()).toBe(true)
    await w.find('button').trigger('click')
    expect(w.find('button').text()).toBe('View less')
    expect(w.find('span.truncate').exists()).toBe(false)
  })
  it('the limit is configurable and exact', () => {
    expect(mount(TruncatedText, { props: { text: 'abcde', limit: 5 } }).find('button').exists()).toBe(false)
    expect(mount(TruncatedText, { props: { text: 'abcdef', limit: 5 } }).find('button').exists()).toBe(true)
  })
  it('height mode offers View more only when the text really overflows', async () => {
    const orig = Object.getOwnPropertyDescriptors(HTMLElement.prototype)
    Object.defineProperty(HTMLElement.prototype, 'scrollHeight', { configurable: true, get: () => 200 })
    Object.defineProperty(HTMLElement.prototype, 'clientHeight', { configurable: true, get: () => 50 })
    const tall = mount(TruncatedText, { props: { text: 'long text', maxHeight: '4.5em' } })
    await nextTick(); await nextTick()
    expect(tall.find('button').text()).toBe('View more')
    expect(tall.find('p').attributes('style')).toContain('max-height')
    await tall.find('button').trigger('click')
    expect(tall.find('button').text()).toBe('View less')
    expect(tall.find('p').attributes('style') || '').not.toContain('max-height')
    Object.defineProperty(HTMLElement.prototype, 'scrollHeight', { configurable: true, get: () => 40 })
    const short = mount(TruncatedText, { props: { text: 'fits', maxHeight: '4.5em' } })
    await nextTick(); await nextTick()
    expect(short.find('button').exists()).toBe(false)
    if (orig.scrollHeight) Object.defineProperty(HTMLElement.prototype, 'scrollHeight', orig.scrollHeight)
    if (orig.clientHeight) Object.defineProperty(HTMLElement.prototype, 'clientHeight', orig.clientHeight)
  })
  it('new text collapses it again', async () => {
    const w = mount(TruncatedText, { props: { text: 'x'.repeat(200) } })
    await w.find('button').trigger('click')
    await w.setProps({ text: 'y'.repeat(200) })
    expect(w.find('button').text()).toBe('View more')
  })
})

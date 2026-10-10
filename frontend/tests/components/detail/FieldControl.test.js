import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { callMock } = vi.hoisted(() => ({ callMock: vi.fn() }))
vi.mock('frappe-ui', () => ({
  call: (...a) => callMock(...a),
  debounce: (fn) => fn,
  FeatherIcon: { template: '<i />' },
  LoadingIndicator: { template: '<i class="spinner" />' },
  Combobox: { props: ['modelValue', 'options'], template: '<div class="combobox" />' },
  Popover: { template: '<div class="popover"><slot name="target" :togglePopover="() => {}" :open="false" /></div>' },
  FileUploader: {
    emits: ['success'],
    template: '<div class="uploader"><slot :uploading="false" :progress="0" :openFileSelector="() => {}" /></div>',
  },
}))

import FieldControl from '@/components/detail/FieldControl.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import AppCheckbox from '@/components/ui/AppCheckbox.vue'

const stubs = { AppLinkField: { props: ['doctype', 'modelValue', 'disabled', 'query', 'filters'], emits: ['update:modelValue'], template: '<div class="link" :data-doctype="doctype" />' } }
const mk = (field, props = {}) => mount(FieldControl, { props: { field: { fieldname: 'f', label: 'Label', fieldtype: 'Data', ...field }, ...props }, global: { stubs } })

beforeEach(() => { callMock.mockReset() })

describe('FieldControl control types', () => {
  it.each([
    ['Data', 'text'], ['Int', 'number'], ['Float', 'number'], ['Currency', 'number'], ['Password', 'password'],
  ])('%s renders an input of type %s', (fieldtype, type) => {
    expect(mk({ fieldtype }).find('input').attributes('type')).toBe(type)
  })
  it('text areas for long text types', () => {
    for (const fieldtype of ['Small Text', 'Long Text', 'Text Editor', 'Code', 'JSON']) {
      expect(mk({ fieldtype }).find('textarea').exists(), fieldtype).toBe(true)
    }
  })
  it('read-only long text is shown as text, not an editor', () => {
    const w = mk({ fieldtype: 'Small Text' }, { modelValue: 'hello', disabled: true })
    expect(w.find('textarea').exists()).toBe(false)
    expect(w.text()).toContain('hello')
  })
  it('label with a required star and description', () => {
    const w = mk({ reqd: 1, description: 'Help text' })
    expect(w.text()).toContain('Label *')
    expect(w.text()).toContain('Help text')
  })
  it('a Link renders the link picker for its doctype', () => {
    const w = mk({ fieldtype: 'Link', options: 'Customer' }, { modelValue: 'C1' })
    expect(w.find('.link').attributes('data-doctype')).toBe('Customer')
  })
  it('a Dynamic Link waits for its type, then links to it', () => {
    const f = { fieldtype: 'Dynamic Link', options: 'link_type' }
    expect(mk(f).text()).toContain("Pick the linked record's type first")
    expect(mk(f, { dynamicDoctype: 'Lead' }).find('.link').attributes('data-doctype')).toBe('Lead')
  })
  it('a checkbox emits a boolean', async () => {
    const w = mk({ fieldtype: 'Check' }, { modelValue: 0 })
    await w.findComponent(AppCheckbox).find('input').setValue(true)
    expect(w.emitted('update:modelValue')[0]).toEqual([true])
  })
})

describe('FieldControl input masks', () => {
  it('SSN keeps digits only, capped at 4', async () => {
    const w = mk({ fieldname: 'ssn_digit', fieldtype: 'Data' })
    const input = w.find('input')
    expect(input.attributes('maxlength')).toBe('4')
    await input.setValue('12ab345')
    expect(w.emitted('update:modelValue').at(-1)).toEqual(['1234'])
  })
  it('SSN honours a declared field length', () => {
    expect(mk({ fieldname: 'ssn', fieldtype: 'Data', length: 9 }).find('input').attributes('maxlength')).toBe('9')
  })
  it('month-year inputs are masked as MM-YYYY', async () => {
    const w = mk({ fieldname: 'start_date', fieldtype: 'Data' })
    const input = w.find('input')
    expect(input.attributes('placeholder')).toBe('MM-YYYY')
    expect(input.attributes('maxlength')).toBe('7')
    await input.setValue('122026')
    expect(w.emitted('update:modelValue').at(-1)).toEqual(['12-2026'])
  })
  it('the same names on a real Date field are not masked', () => {
    const w = mk({ fieldname: 'start_date', fieldtype: 'Date' })
    expect(w.find('input').attributes('placeholder') || '').not.toBe('MM-YYYY')
  })
  it('phone fields hint the country code', () => {
    expect(mk({ fieldname: 'personal_phone_number', fieldtype: 'Data' }).find('input').attributes('placeholder')).toBe('Exp: +1xxxxxxxxxx')
  })
  it('email fields use an email input', () => {
    expect(mk({ fieldname: 'email_id', fieldtype: 'Data' }).find('input').attributes('type')).toBe('email')
  })
  it('plain text passes through unchanged', async () => {
    const w = mk({ fieldname: 'anything' })
    await w.find('input').setValue('hello')
    expect(w.emitted('update:modelValue')[0]).toEqual(['hello'])
  })
})

describe('FieldControl read-only links', () => {
  it('a read-only email is a mailto link', () => {
    const a = mk({ fieldname: 'email_id' }, { modelValue: 'a@b.com', disabled: true }).find('a')
    expect(a.attributes('href')).toBe('mailto:a@b.com')
  })
  it('a read-only LinkedIn url is a link, adding https when missing', () => {
    const a = mk({ fieldname: 'personal_linkedin' }, { modelValue: 'linkedin.com/in/x', disabled: true }).find('a')
    expect(a.attributes('href')).toBe('https://linkedin.com/in/x')
    expect(mk({ fieldname: 'personal_linkedin' }, { modelValue: 'https://linkedin.com/in/x', disabled: true }).find('a').attributes('href')).toBe('https://linkedin.com/in/x')
  })
  it('an editable email is an input, not a link', () => {
    expect(mk({ fieldname: 'email_id' }, { modelValue: 'a@b.com' }).find('a').exists()).toBe(false)
  })
})

describe('FieldControl select / date', () => {
  it('select validation only speaks up when asked', () => {
    expect(mk({ fieldtype: 'Select', options: 'A\nB' }, { modelValue: 'Z' }).text()).not.toContain('valid option')
    expect(mk({ fieldtype: 'Select', options: 'A\nB' }, { modelValue: 'Z', showErrors: true }).text()).toContain('valid option')
  })
  it('a Select with a leading blank line offers a clearing choice', () => {
    const w = mk({ fieldtype: 'Select', options: '\nA\nB' }, { modelValue: 'A' })
    expect(w.findComponent({ name: 'AppCombobox' }).props('options')).toEqual([{ label: '-', value: '' }, { label: 'A', value: 'A' }, { label: 'B', value: 'B' }])
    const strict = mk({ fieldtype: 'Select', options: 'A\nB' }, { modelValue: 'A' })
    expect(strict.findComponent({ name: 'AppCombobox' }).props('options')).toEqual([{ label: 'A', value: 'A' }, { label: 'B', value: 'B' }])
  })
  it('dates and datetimes use the date picker', () => {
    expect(mk({ fieldtype: 'Date' }, { modelValue: '2026-03-05' }).findComponent({ name: 'AppDatePicker' }).exists()).toBe(true)
    expect(mk({ fieldtype: 'Datetime' }).findComponent({ name: 'AppDatePicker' }).props('mode')).toBe('datetime')
  })
})

describe('FieldControl validation', () => {
  it('shows nothing until showErrors is set', () => {
    expect(mk({ reqd: 1 }, { modelValue: '' }).text()).not.toContain('is required')
  })
  it('shows the validation message once asked', () => {
    expect(mk({ reqd: 1 }, { modelValue: '', showErrors: true }).text()).toContain('Label is required')
  })
  it('never nags a read-only field', () => {
    expect(mk({ reqd: 1 }, { modelValue: '', showErrors: true, disabled: true }).text()).not.toContain('is required')
  })
  it('exposes error for the parent form', () => {
    const w = mk({ reqd: 1 }, { modelValue: '', showErrors: true })
    expect(w.vm.error).toBe('Label is required')
  })
  it('link fields show the error below the picker', () => {
    expect(mk({ fieldtype: 'Link', options: 'Customer', reqd: 1 }, { modelValue: '', showErrors: true }).text()).toContain('required')
  })
})

describe('FieldControl attach', () => {
  it('shows the file name as a link, or nothing attached', () => {
    const w = mk({ fieldtype: 'Attach' }, { modelValue: '/files/resume.pdf' })
    expect(w.find('a').text()).toBe('resume.pdf')
    expect(w.find('a').attributes('href')).toBe('/files/resume.pdf')
    expect(mk({ fieldtype: 'Attach' }).text()).toContain('No file attached')
  })
  it('attach images show a thumbnail', () => {
    expect(mk({ fieldtype: 'Attach Image' }, { modelValue: '/files/p.png' }).find('img').attributes('src')).toBe('/files/p.png')
  })
  it('no upload or clear buttons when read-only', () => {
    const w = mk({ fieldtype: 'Attach' }, { modelValue: '/files/a.pdf', disabled: true })
    expect(w.find('.uploader').exists()).toBe(false)
    expect(w.findAll('button')).toHaveLength(0)
  })
  it('clearing asks the server first when a remover is given, and keeps the file if refused', async () => {
    const removeFile = vi.fn().mockResolvedValueOnce(false).mockResolvedValueOnce(true)
    const w = mk({ fieldtype: 'Attach', fieldname: 'visa' }, { modelValue: '/files/a.pdf', removeFile })
    const clear = () => w.findAll('button').at(-1).trigger('click')
    await clear()
    await flushPromises()
    expect(w.emitted('update:modelValue')).toBeUndefined()
    await clear()
    await flushPromises()
    expect(removeFile).toHaveBeenCalledWith('visa')
    expect(w.emitted('update:modelValue')[0]).toEqual([''])
  })
  it('clearing without a remover just empties the value', async () => {
    const w = mk({ fieldtype: 'Attach' }, { modelValue: '/files/a.pdf' })
    await w.findAll('button').at(-1).trigger('click')
    await flushPromises()
    expect(w.emitted('update:modelValue')[0]).toEqual([''])
  })
})

describe('FieldControl link to File', () => {
  const field = { fieldtype: 'Link', options: 'File' }
  it('looks the file up and links to it', async () => {
    callMock.mockResolvedValue({ file_url: '/files/x.pdf', file_name: 'x.pdf' })
    const w = mk(field, { modelValue: 'FILE-1' })
    await flushPromises()
    expect(callMock).toHaveBeenCalledWith('frappe.client.get_value', expect.objectContaining({ doctype: 'File', filters: 'FILE-1' }))
    expect(w.find('a').attributes('href')).toBe('/files/x.pdf')
    expect(w.find('a').text()).toBe('x.pdf')
  })
  it('uses file info the caller already has instead of looking up', async () => {
    const w = mk(field, { modelValue: 'FILE-1', fileInfo: { name: 'FILE-1', file_url: '/f/y.pdf', file_name: 'y.pdf' } })
    await flushPromises()
    expect(callMock).not.toHaveBeenCalled()
    expect(w.find('a').attributes('href')).toBe('/f/y.pdf')
  })
  it('an unreadable file record still counts as uploaded', async () => {
    callMock.mockResolvedValue(null)
    const w = mk(field, { modelValue: 'FILE-9' })
    await flushPromises()
    expect(w.text()).toContain('File uploaded')
  })
  it('no value means no lookup', async () => {
    const w = mk(field)
    await flushPromises()
    expect(callMock).not.toHaveBeenCalled()
    expect(w.text()).toContain('No file attached')
  })
  it('is not rendered as a link picker', () => {
    expect(mk(field).find('.link').exists()).toBe(false)
  })
})

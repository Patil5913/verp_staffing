import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { reactive, ref, nextTick } from 'vue'

vi.mock('frappe-ui', () => ({ LoadingIndicator: { template: '<i />' } }))
vi.mock('@/composables/detail/usePdfPages', () => ({ PDF_PAGE_SCALE: 1.5, usePdfPages: () => ({ pages: ref([]), loading: ref(false), error: ref('') }) }))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/ui/AppCombobox.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/StateBanner.vue', () => ({ default: { template: '<i />' } }))

import Builder from '@/components/detail/esign/ESignBuilder.vue'

const row = (o = {}) => ({ name: 'F1', page_number: 1, x_percent: 10, y_percent: 10, width_percent: 20, height_percent: 5, signer_email: 'a@x.com', field_type: 'text', ...o })
const detail = (rows, hidden) => ({ canWrite: ref(true), values: reactive({ original_pdf: '/f.pdf', ...(rows ? { signature_fields: rows } : {}) }), hiddenTables: { signature_fields: hidden } })
const make = (d, props = {}) => shallowMount(Builder, { props: { detail: d, ...props } })
const page = { number: 1, width: 1000, height: 2000 }

describe('rows and recipients', () => {
  it('reads from the hidden table until edited', () => {
    const w = make(detail(undefined, [row()]))
    expect(w.vm.rows).toHaveLength(1)
    expect(make(detail(undefined, undefined)).vm.rows).toEqual([])
  })
  it('recipients are signers with a field plus those added here; the first becomes active', () => {
    const w = make(detail([row(), row({ name: 'F2', signer_email: 'b@x.com' }), row({ name: 'F3', signer_email: '' })]))
    expect(w.vm.recipients).toEqual(['a@x.com', 'b@x.com'])
    expect(w.vm.activeRecipient).toBe('a@x.com')
    expect(w.vm.countFor('a@x.com')).toBe(1)
  })
  it('an active recipient is chosen when the fields arrive later', async () => {
    const d = detail([])
    const w = make(d)
    expect(w.vm.activeRecipient).toBe('')
    d.values.signature_fields = [row()]
    await nextTick()
    expect(w.vm.activeRecipient).toBe('a@x.com')
  })
  it('adding a recipient normalises and validates the address', () => {
    const w = make(detail([]))
    w.vm.newEmail = 'nope'; w.vm.addRecipient()
    expect(w.vm.recipients).toEqual([])
    w.vm.newEmail = '  New@X.com '; w.vm.addRecipient()
    expect(w.vm.recipients).toEqual(['new@x.com'])
    expect(w.vm.activeRecipient).toBe('new@x.com')
    expect(w.vm.newEmail).toBe('')
    w.vm.newEmail = 'new@x.com'; w.vm.addRecipient()
    expect(w.vm.recipients).toEqual(['new@x.com'])
  })
  it('each recipient has its own colour, cycling the palette', () => {
    const rows = Array.from({ length: 9 }, (_, i) => row({ name: `F${i}`, signer_email: `u${i}@x.com` }))
    const w = make(detail(rows))
    expect(w.vm.colorFor('u0@x.com')).toBe(w.vm.colorFor('u8@x.com'))
    expect(w.vm.colorFor('u1@x.com')).not.toBe(w.vm.colorFor('u0@x.com'))
    expect(w.vm.colorFor('stranger@x.com')).toBe(w.vm.colorFor('u0@x.com'))
  })
  it('helpers', () => {
    const w = make(detail([]))
    expect(['1', 'Yes', 'checked', 'ON'].every(w.vm.isOn)).toBe(true)
    expect([0, '', null, 'no'].some(w.vm.isOn)).toBe(false)
    expect(w.vm.labelFor('date')).toBe('Date')
    expect(w.vm.labelFor('weird')).toBe('weird')
  })
  it('locked or read only builders are disabled', () => {
    expect(make(detail([])).vm.disabled).toBe(false)
    expect(make(detail([]), { locked: true }).vm.disabled).toBe(true)
  })
})

describe('placing fields', () => {
  const drop = (w, x, y) => w.vm.onDrop(page, { clientX: x, clientY: y, currentTarget: { getBoundingClientRect: () => ({ left: 0, top: 0, width: 1000, height: 2000 }) } })
  it('a drop creates a field centred on the pointer for the active signer', () => {
    const d = detail([row()]); const w = make(d)
    w.vm.dragging = 'signature'
    drop(w, 500, 1000)
    const added = d.values.signature_fields[1]
    expect(added).toMatchObject({ page_number: 1, field_type: 'signature', signer_email: 'a@x.com', width_percent: 24, height_percent: 6 })
    expect(added.x_percent).toBeCloseTo(38) // 50% minus half the width
    expect(added.y_percent).toBeCloseTo(47)
    expect(w.vm.selected).toBeTruthy()
  })
  it('drops near the edge are kept inside the page', () => {
    const d = detail([row()]); const w = make(d); w.vm.dragging = 'text'
    drop(w, 995, 1995)
    const f = d.values.signature_fields.at(-1)
    expect(f.x_percent + f.width_percent).toBeLessThanOrEqual(100)
    expect(f.y_percent + f.height_percent).toBeLessThanOrEqual(100)
    drop(w, -50, -50)
    expect(d.values.signature_fields.at(-1).x_percent).toBe(0)
  })
  it('checkboxes are small', () => {
    const d = detail([row()]); const w = make(d); w.vm.dragging = 'checkbox'
    drop(w, 500, 500)
    expect(d.values.signature_fields.at(-1)).toMatchObject({ width_percent: 3.5, height_percent: 2.6 })
  })
  it('nothing is placed when locked, without a tool, or without a signer', () => {
    const d = detail([row()])
    let w = make(d, { locked: true }); w.vm.dragging = 'text'; drop(w, 5, 5)
    w = make(d); drop(w, 5, 5)
    w = make(detail([])); w.vm.dragging = 'text'; drop(w, 5, 5)
    expect(d.values.signature_fields).toHaveLength(1)
    expect(w.vm.rows).toEqual([])
  })
  it('new rows get stable keys; saved rows use their name', () => {
    const w = make(detail([]))
    const a = {}, b = {}
    expect(w.vm.keyOf({ name: 'F1' })).toBe('F1')
    expect(w.vm.keyOf(a)).toBe(w.vm.keyOf(a))
    expect(w.vm.keyOf(a)).not.toBe(w.vm.keyOf(b))
  })
  it('rowsOnPage filters by page number', () => {
    const w = make(detail([row(), row({ name: 'F2', page_number: '2' })]))
    expect(w.vm.rowsOnPage(1)).toHaveLength(1)
    expect(w.vm.rowsOnPage(2)).toHaveLength(1)
  })
})

describe('keyboard', () => {
  const press = (w, r, key, extra = {}) => { const e = { key, target: 'el', currentTarget: 'el', preventDefault: vi.fn(), ...extra }; w.vm.onRowKey(r, page, e); return e }
  it('arrows nudge by 0.1, shift by 1, never leaving the page', () => {
    const d = detail([row({ x_percent: 0.05 })]); const w = make(d)
    press(w, d.values.signature_fields[0], 'ArrowLeft')
    expect(d.values.signature_fields[0].x_percent).toBe(0)
    press(w, d.values.signature_fields[0], 'ArrowRight', { shiftKey: true })
    expect(d.values.signature_fields[0].x_percent).toBe(1)
    press(w, d.values.signature_fields[0], 'ArrowDown')
    expect(d.values.signature_fields[0].y_percent).toBeCloseTo(10.1)
  })
  it('the bottom right limit is respected', () => {
    const d = detail([row({ x_percent: 79.95, width_percent: 20 })]); const w = make(d)
    press(w, d.values.signature_fields[0], 'ArrowRight', { shiftKey: true })
    expect(d.values.signature_fields[0].x_percent).toBe(80)
  })
  it('Delete removes the field', () => {
    const d = detail([row(), row({ name: 'F2' })]); const w = make(d)
    const e = press(w, d.values.signature_fields[0], 'Delete')
    expect(d.values.signature_fields.map((r) => r.name)).toEqual(['F2'])
    expect(e.preventDefault).toHaveBeenCalled()
  })
  it('keys typed inside a child input are ignored', () => {
    const d = detail([row()]); const w = make(d)
    press(w, d.values.signature_fields[0], 'Delete', { target: 'input' })
    expect(d.values.signature_fields).toHaveLength(1)
  })
})

describe('dragging and resizing', () => {
  const ptr = (type, x, y, button = 0) => ({ clientX: x, clientY: y, button, preventDefault: vi.fn() })
  const move = (x, y) => window.dispatchEvent(Object.assign(new Event('pointermove'), { clientX: x, clientY: y }))
  it('moving converts pixels to page percentages and clamps', () => {
    const d = detail([row({ x_percent: 10, y_percent: 10, width_percent: 20, height_percent: 5 })]); const w = make(d)
    w.vm.startMove(d.values.signature_fields[0], page, ptr('down', 100, 100))
    move(200, 300) // +100px of 1000 = +10%, +200px of 2000 = +10%
    expect(d.values.signature_fields[0]).toMatchObject({ x_percent: 20, y_percent: 20 })
    move(5000, 9000)
    expect(d.values.signature_fields[0]).toMatchObject({ x_percent: 80, y_percent: 95 })
    move(-5000, -9000)
    expect(d.values.signature_fields[0]).toMatchObject({ x_percent: 0, y_percent: 0 })
    window.dispatchEvent(new Event('pointerup'))
    move(500, 500)
    expect(d.values.signature_fields[0].x_percent).toBe(0) // released: no more tracking
  })
  it('resizing has minimum and maximum sizes', () => {
    const d = detail([row({ x_percent: 10, y_percent: 10, width_percent: 20, height_percent: 5 })]); const w = make(d)
    w.vm.startResize(d.values.signature_fields[0], page, ptr('down', 0, 0))
    move(-9999, -9999)
    expect(d.values.signature_fields[0]).toMatchObject({ width_percent: 4, height_percent: 2 })
    move(9999, 9999)
    expect(d.values.signature_fields[0]).toMatchObject({ width_percent: 90, height_percent: 90 })
    window.dispatchEvent(new Event('pointerup'))
  })
  it('only the primary button starts a drag, and never when disabled', () => {
    const d = detail([row()]); const w = make(d)
    const e = ptr('down', 0, 0, 2)
    w.vm.startMove(d.values.signature_fields[0], page, e)
    expect(e.preventDefault).not.toHaveBeenCalled()
    const locked = make(d, { locked: true }); const e2 = ptr('down', 0, 0)
    locked.vm.startMove(d.values.signature_fields[0], page, e2)
    expect(e2.preventDefault).not.toHaveBeenCalled()
  })
})

describe('styling', () => {
  it('box position in percent and text size scaled to the render', () => {
    const w = make(detail([]))
    expect(w.vm.boxStyle({ x_percent: 1, y_percent: 2, width_percent: 3, height_percent: 4, font_size: 10 })).toEqual({ left: '1%', top: '2%', width: '3%', height: '4%', fontSize: '15px' })
    expect(w.vm.boxStyle({ font_size: '' }).fontSize).toBe('18px')
  })
})

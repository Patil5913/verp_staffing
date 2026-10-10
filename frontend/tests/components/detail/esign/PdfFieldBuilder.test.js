import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { ref, nextTick } from 'vue'

const h = vi.hoisted(() => ({ notify: { error: vi.fn() } }))
vi.mock('frappe-ui', () => ({ Dialog: { template: '<div />' }, FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/detail/usePdfPages', () => ({ usePdfPages: () => ({ pages: ref([{ number: 1, width: 600, height: 800 }]), loading: ref(false), error: ref('') }) }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/common/StateBanner.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/FieldControl.vue', () => ({ default: { template: '<i />' } }))

import Builder from '@/components/detail/esign/PdfFieldBuilder.vue'

const f = (o = {}) => ({ field_id: 'a', name: 'A', type: 'Text', page: 1, x: 100, y: 100, width: 150, height: 30, font_size: 12, line_height: 1.2, ...o })
const make = (fields = [], props = {}) => shallowMount(Builder, { props: { pdfUrl: '/f.pdf', modelValue: fields, ...props } })
const last = (w) => w.emitted('update:modelValue').at(-1)[0]
beforeEach(() => vi.clearAllMocks())

describe('zoom', () => {
  it('steps within 50%–200% without float drift', () => {
    const w = make()
    for (let i = 0; i < 30; i++) w.vm.stepZoom(0.1)
    expect(w.vm.zoom).toBe(2)
    for (let i = 0; i < 30; i++) w.vm.stepZoom(-0.1)
    expect(w.vm.zoom).toBe(0.5)
    w.vm.stepZoom(0.1); w.vm.stepZoom(0.1); w.vm.stepZoom(0.1)
    expect(w.vm.zoom).toBe(0.8)
  })
})

describe('working copy', () => {
  it('edits never touch the prop objects', () => {
    const src = [f()]
    const w = make(src)
    w.vm.selectedFieldId = 'a'
    w.vm.updateSelectedField('name', 'Changed')
    expect(src[0].name).toBe('A')
    expect(last(w)[0].name).toBe('Changed')
  })
  it('follows the parent when the value is replaced', async () => {
    const w = make([f()])
    await w.setProps({ modelValue: [f({ field_id: 'b' }), f({ field_id: 'c' })] })
    expect(w.vm.localFields.map((x) => x.field_id)).toEqual(['b', 'c'])
  })
  it('remove and clear emit and drop the selection', () => {
    const w = make([f(), f({ field_id: 'b' })])
    w.vm.selectedFieldId = 'a'
    w.vm.removeField('a')
    expect(last(w).map((x) => x.field_id)).toEqual(['b'])
    expect(w.vm.selectedFieldId).toBeNull()
    w.vm.clearAll()
    expect(last(w)).toEqual([])
  })
  it('counts staff fields and customer fields', () => {
    const w = make([f(), f({ field_id: 'b', type: 'Signature' }), f({ field_id: 'c', type: 'Customer_Date' })])
    expect([w.vm.standardCount, w.vm.customerCount]).toEqual([1, 2])
  })
  it('the badge shows position while stepping through fields', async () => {
    const w = make([f(), f({ field_id: 'b', type: 'Signature' }), f({ field_id: 'c', type: 'Customer_Date' })])
    expect(w.vm.badgeLabel('customer', 2)).toBe(2)
    w.vm.jumpTo('customer'); await nextTick()
    expect(w.vm.selectedFieldId).toBe('b')
    expect(w.vm.badgeLabel('customer', 2)).toBe('1/2')
    w.vm.jumpTo('customer'); expect(w.vm.selectedFieldId).toBe('c')
    w.vm.jumpTo('customer'); expect(w.vm.selectedFieldId).toBe('b') // wraps
    w.vm.jumpTo('company'); expect(w.vm.selectedFieldId).toBe('a')
  })
  it('jumping with no fields of that kind does nothing', () => {
    const w = make([f()])
    w.vm.jumpTo('customer')
    expect(w.vm.selectedFieldId).toBeNull()
  })
})

describe('snapping', () => {
  it('free placement is untouched; otherwise the 5px grid', () => {
    const w = make([f()])
    const probe = { field_id: 'z', page: 1 }
    expect(w.vm.snap(237, 0, 'x', probe, true)).toBe(237)
    expect(w.vm.snap(237, 0, 'x', { ...probe, page: 2 }, false)).toBe(235)
  })
  it('sticks to another field\'s edges within 6px, either leading or trailing', () => {
    const w = make([f({ x: 100, width: 150 })]) // edges at 100 and 250
    const probe = { field_id: 'z', page: 1 }
    expect(w.vm.snap(104, 50, 'x', probe, false)).toBe(100)
    expect(w.vm.snap(247, 50, 'x', probe, false)).toBe(250)
    expect(w.vm.snap(203, 50, 'x', probe, false)).toBe(200) // trailing edge of ours meets 250
    expect(w.vm.snap(120, 50, 'x', probe, false)).toBe(120) // too far: grid
  })
  it('ignores itself and fields on other pages', () => {
    const w = make([f({ page: 2, x: 100 }), f({ field_id: 'me', x: 103 })])
    expect(w.vm.snap(103, 0, 'x', { field_id: 'me', page: 1 }, false)).toBe(105)
  })
})

describe('exact geometry', () => {
  it('values are rounded and kept inside the page', () => {
    const w = make([f({ x: 100, y: 100 })]); w.vm.selectedFieldId = 'a'
    w.vm.setGeometry('x', '9999'); expect(w.vm.selectedField.x).toBe(450)
    w.vm.setGeometry('x', -5); expect(w.vm.selectedField.x).toBe(0)
    w.vm.setGeometry('y', 9999); expect(w.vm.selectedField.y).toBe(770)
    w.vm.setGeometry('width', 3); expect(w.vm.selectedField.width).toBe(20)
    w.vm.setGeometry('height', 1); expect(w.vm.selectedField.height).toBe(10)
    w.vm.setGeometry('width', 'abc'); expect(w.vm.selectedField.width).toBe(20)
  })
  it('nothing selected, nothing happens', () => {
    const w = make([f()]); w.vm.setGeometry('x', 5)
    expect(w.emitted('update:modelValue')).toBeUndefined()
  })
  it('line height warning appears only when wrapped lines would not fit', () => {
    const w = make([f({ font_size: 20, line_height: 2, height: 30 })]); w.vm.selectedFieldId = 'a'
    expect(w.vm.lineHeightWarning).toMatch(/~40px needed vs 30px/)
    w.vm.updateSelectedField('height', 40)
    expect(w.vm.lineHeightWarning).toBe('')
    w.vm.selectedFieldId = null
    expect(w.vm.lineHeightWarning).toBe('')
  })
  it('styles', () => {
    const w = make()
    expect(w.vm.fieldStyle({ x: 1, y: 2 })).toEqual({ top: '2px', left: '1px', width: '150px', height: '30px' })
    expect(w.vm.previewStyle({ font_size: 10, line_height: 1.5 })).toEqual({ fontSize: '15px', lineHeight: 1.5 })
    expect(w.vm.previewStyle({}).lineHeight).toBe(1.2)
  })
})

describe('creating a field', () => {
  const rect = { left: 0, top: 0, width: 600, height: 800 }
  const drop = (w, x, y, extra = {}) => w.vm.onDrop(1, { clientX: x, clientY: y, altKey: false, currentTarget: { getBoundingClientRect: () => rect }, ...extra })
  it('dropping a tool opens the dialog at the pointer, centred and on the grid', () => {
    const w = make(); w.vm.draggingTool = 'Text'
    drop(w, 300, 400)
    expect(w.vm.showCreateDialog).toBe(true)
    expect(w.vm.newFieldType).toBe('Text')
    expect(w.vm.newFieldDropPos).toEqual({ page: 1, x: 225, y: 385 })
  })
  it('stays inside the page and respects zoom', () => {
    const w = make(); w.vm.draggingTool = 'Text'
    drop(w, 9999, 9999); expect(w.vm.newFieldDropPos).toMatchObject({ x: 450, y: 770 })
    drop(w, -10, -10); expect(w.vm.newFieldDropPos).toMatchObject({ x: 0, y: 0 })
    w.vm.stepZoom(1) // 2x: 600px on screen is 300 units
    drop(w, 300, 400)
    expect(w.vm.newFieldDropPos.x).toBeLessThanOrEqual(150)
  })
  it('does nothing when disabled or with no tool', () => {
    const w = make([], { disabled: true }); w.vm.draggingTool = 'Text'; drop(w, 1, 1)
    expect(w.vm.showCreateDialog).toBe(false)
    const w2 = make(); drop(w2, 1, 1)
    expect(w2.vm.showCreateDialog).toBe(false)
  })
  it('a name is required', () => {
    const w = make(); w.vm.draggingTool = 'Date'; drop(w, 300, 400)
    w.vm.confirmCreateField()
    expect(h.notify.error).toHaveBeenCalledWith('Field Name is required.')
    expect(w.emitted('update:modelValue')).toBeUndefined()
  })
  it('creates the field with defaults and the page size recorded', () => {
    const w = make(); w.vm.draggingTool = 'Signature'; drop(w, 300, 400)
    w.vm.draft.name = '  Client sign '
    w.vm.confirmCreateField()
    const created = last(w)[0]
    expect(created).toMatchObject({ name: 'Client sign', type: 'Signature', page: 1, x: 225, y: 385, width: 150, height: 30, font_size: 12, line_height: 1.2, wrap: true, page_width: 600, page_height: 800 })
    expect(created.field_id).toMatch(/^fld_[a-z0-9]+$/)
    expect(w.vm.selectedFieldId).toBe(created.field_id)
    expect(w.vm.showCreateDialog).toBe(false)
  })
  it('field ids are unique', () => {
    const w = make(); w.vm.draggingTool = 'Text'
    for (let i = 0; i < 2; i++) { drop(w, 100, 100); w.vm.draft.name = 'n'; w.vm.confirmCreateField() }
    const ids = last(w).map((x) => x.field_id)
    expect(new Set(ids).size).toBe(2)
  })
})

describe('keyboard and pointer', () => {
  const key = (w, field, k, extra = {}) => { const e = { key: k, target: 'x', currentTarget: 'x', preventDefault: vi.fn(), ...extra }; w.vm.onFieldKey(field, e); return e }
  it('arrows nudge 1px (10 with shift) within the page', () => {
    const w = make([f({ x: 0, y: 0 })]); const field = w.vm.localFields[0]
    key(w, field, 'ArrowLeft'); expect(field.x).toBe(0)
    key(w, field, 'ArrowRight', { shiftKey: true }); expect(field.x).toBe(10)
    key(w, field, 'ArrowDown'); expect(field.y).toBe(1)
    field.x = 449; key(w, field, 'ArrowRight', { shiftKey: true }); expect(field.x).toBe(450)
    expect(last(w)).toBeTruthy()
  })
  it('Delete removes; typing in a child input is ignored; disabled ignores all', () => {
    const w = make([f()])
    key(w, w.vm.localFields[0], 'Delete', { target: 'input' })
    expect(w.vm.localFields).toHaveLength(1)
    const d = make([f()], { disabled: true }); key(d, d.vm.localFields[0], 'Delete')
    expect(d.vm.localFields).toHaveLength(1)
    key(w, w.vm.localFields[0], 'Delete')
    expect(w.vm.localFields).toHaveLength(0)
  })
  const mv = (x, y, extra = {}) => window.dispatchEvent(Object.assign(new Event('pointermove'), { clientX: x, clientY: y, ...extra }))
  it('dragging moves a field, snapped, clamped, and emits once on release', () => {
    const w = make([f({ x: 100, y: 100 })]); const field = w.vm.localFields[0]
    w.vm.onFieldMouseDown(field, { button: 0, clientX: 0, clientY: 0, preventDefault: vi.fn() })
    mv(53, 27, { altKey: true }); expect([field.x, field.y]).toEqual([153, 127])
    mv(53, 27); expect([field.x, field.y]).toEqual([155, 125])
    mv(9999, 9999); expect([field.x, field.y]).toEqual([450, 770])
    mv(-9999, -9999); expect([field.x, field.y]).toEqual([0, 0])
    expect(w.emitted('update:modelValue')).toBeUndefined()
    window.dispatchEvent(new Event('pointerup'))
    expect(w.emitted('update:modelValue')).toHaveLength(1)
  })
  it('only the primary button drags, and not when disabled', () => {
    const w = make([f()]); const e = { button: 2, preventDefault: vi.fn() }
    w.vm.onFieldMouseDown(w.vm.localFields[0], e)
    expect(e.preventDefault).not.toHaveBeenCalled()
  })
  it('resizing is bounded by the minimum size and the page edge', () => {
    const w = make([f({ x: 100, y: 100, width: 150, height: 30 })]); const field = w.vm.localFields[0]
    w.vm.onResizeMouseDown(field, { clientX: 0, clientY: 0, preventDefault: vi.fn() })
    mv(-9999, -9999, { altKey: true }); expect([field.width, field.height]).toEqual([20, 10])
    mv(9999, 9999); expect([field.width, field.height]).toEqual([500, 700])
    window.dispatchEvent(new Event('pointerup'))
    expect(w.emitted('update:modelValue')).toHaveLength(1)
  })
})

describe('customer fields', () => {
  it('signatures and Customer_* types are customer filled', () => {
    const w = make()
    expect(['Signature', 'Customer_Text'].every((t) => w.vm.isCustomer({ type: t }))).toBe(true)
    expect(['Text', 'Number', 'Rich_Text'].some((t) => w.vm.isCustomer({ type: t }))).toBe(false)
  })
})

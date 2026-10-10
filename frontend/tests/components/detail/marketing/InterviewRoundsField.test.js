import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ made: {}, confirm: vi.fn(), sup: null, admin: false }))
vi.mock('frappe-ui', () => ({ Dialog: { template: '<div />' } }))
vi.mock('@/utils/common/roles', () => ({ hasRole: () => h.admin, isAdministrator: () => false }))
vi.mock('@/utils/common/siteTime', () => ({ siteTodayIso: () => '2026-05-15', roundInZone: (r) => r.__z || { converted: false } }))
vi.mock('@/utils/common/confirmDialog', () => ({ confirmLeave: (...a) => h.confirm(...a) }))
vi.mock('@/utils/common/notify', () => ({ notify: { success: vi.fn(), error: vi.fn() } }))
vi.mock('@/composables/detail/useIsSuperior', () => ({ useIsSuperior: () => ({ isSuperior: h.sup }) }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => (h.made[o.url.split('.').pop()] = reactive({ resource: { data: null, submit: vi.fn(async () => null) } })),
}))

vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppCombobox.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/DocStatusBadge.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/SectionCard.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/FieldControl.vue', () => ({ default: { template: '<i />' } }))

import Field from '@/components/detail/marketing/InterviewRoundsField.vue'

const detail = (rows = [], over = {}) => ({
  canWrite: ref(true), isNew: ref(false),
  tables: ref([{ fieldname: 'interview_rounds_table', columns: [{ fieldname: 'round' }, { fieldname: 'status' }, { fieldname: 'follow_up', fieldtype: 'Int' }, { fieldname: 'cancelled_by' }, { fieldname: 'notes', read_only: 1 }], rows: [] }]),
  values: reactive({ interview_rounds_table: rows, marketing_link: 'M1' }), ...over,
})
const make = (d, props = {}) => { h.made = {}; const w = shallowMount(Field, { props: { detail: d, ...props } }); return w }
beforeEach(() => { vi.clearAllMocks(); h.sup = ref(false); h.admin = false; h.confirm.mockReset() })

describe('columns and visibility', () => {
  it('the round number column is not edited by hand', () => {
    expect(make(detail()).vm.columns.map((c) => c.fieldname)).toEqual(['status', 'follow_up', 'cancelled_by', 'notes'])
  })
  it('cancellation details only show for called off rounds', () => {
    const w = make(detail())
    const col = { fieldname: 'cancelled_by' }
    for (const s of ['Cancelled', 'rescheduled', 'REJECTED']) expect(w.vm.showColumn(col, { status: s })).toBe(true)
    expect(w.vm.showColumn(col, { status: 'Scheduled' })).toBe(false)
    expect(w.vm.showColumn({ fieldname: 'status' }, { status: 'Scheduled' })).toBe(true)
  })
  it('follow up is always plain text', () => {
    expect(make(detail()).vm.fieldFor({ fieldname: 'follow_up', fieldtype: 'Int' }, {}).fieldtype).toBe('Data')
  })
  it('wide fields are long texts', () => {
    const w = make(detail()); expect(w.vm.wide({ fieldtype: 'Long Text' })).toBe(true); expect(w.vm.wide({ fieldtype: 'Data' })).toBe(false)
  })
  it('times in another zone are described, with the day shift', () => {
    const w = make(detail())
    expect(w.vm.inZone({})).toBe('')
    expect(w.vm.inZone({ __z: { converted: true, date: '2026-05-16', from: '01:00', to: '02:00', zone: 'IST', movedDays: 1 } })).toBe('2026-05-16 01:00 – 02:00 IST (next day)')
    expect(w.vm.inZone({ __z: { converted: true, date: '2026-05-14', from: '23:00', zone: 'PST', movedDays: -1 } })).toBe('2026-05-14 23:00 PST (previous day)')
  })
})

describe('who can edit what', () => {
  const rows = [{ name: 'R1', status: 'Scheduled' }, { name: 'R2', status: 'Scheduled' }]
  it('the assignee can only touch the latest round', () => {
    const w = make(detail(rows)); const col = { fieldname: 'follow_up' }
    expect(w.vm.fieldDisabled(col, rows[0], 0)).toBe(true)
    expect(w.vm.fieldDisabled(col, rows[1], 1)).toBe(false)
  })
  it('a superior can edit earlier rounds too', () => {
    h.sup = ref(true)
    expect(make(detail(rows)).vm.fieldDisabled({ fieldname: 'follow_up' }, rows[0], 0)).toBe(false)
  })
  it('read-only columns and locked or read-only pages are never editable', () => {
    const w = make(detail(rows)); expect(w.vm.fieldDisabled({ fieldname: 'notes', read_only: 1 }, rows[1], 1)).toBe(true)
    expect(make(detail(rows), { locked: true }).vm.fieldDisabled({ fieldname: 'follow_up' }, rows[1], 1)).toBe(true)
    const d = detail(rows); d.canWrite.value = false; expect(make(d).vm.editable).toBe(false)
  })
  it('a called off or completed round is frozen', () => {
    for (const status of ['Cancelled', 'Rescheduled', 'Rejected', 'Completed']) {
      const r = [{ name: 'R1', status }]
      expect(make(detail(r)).vm.fieldDisabled({ fieldname: 'follow_up' }, r[0], 0), status).toBe(true)
    }
  })
  it('a saved Completed round may still have its outcome set, from a short list, unless admin', () => {
    const r = [{ name: 'R1', status: 'Completed' }]
    const d = detail(r); d.tables.value[0].rows = [{ name: 'R1', status: 'Completed' }]
    const w = make(d)
    expect(w.vm.fieldDisabled({ fieldname: 'status' }, r[0], 0)).toBe(false)
    expect(w.vm.fieldDisabled({ fieldname: 'follow_up' }, r[0], 0)).toBe(true)
    const f = w.vm.fieldFor({ fieldname: 'status', fieldtype: 'Link' }, r[0])
    expect([f.fieldtype, f.options]).toEqual(['Select', 'Completed\nGet The Offer\nRejected'])
    expect(w.vm.fieldFor({ fieldname: 'status', fieldtype: 'Link' }, { name: 'NEW', status: 'Completed' }).fieldtype).toBe('Link')
  })
})

describe('adding and removing rounds', () => {
  it('a new round is numbered after the last and starts on today with the default status', () => {
    const d = detail([{ round: '1' }]); const w = make(d)
    h.made.get_single_value.resource.data = 'Scheduled'
    w.vm.addRound()
    expect(d.values.interview_rounds_table[1]).toEqual({ round: '2', follow_up: 0, status: 'Scheduled', date: '2026-05-15' })
    w.vm.removeRound(0)
    expect(d.values.interview_rounds_table.map((r) => r.round)).toEqual(['2'])
  })
  it('a new interview picks up the default status; an existing one never changes', async () => {
    const d = detail([], { isNew: ref(true) }); d.values.status = ''
    make(d); h.made.get_single_value.resource.data = 'Scheduled'
    await Promise.resolve()
    const d2 = detail([]); d2.values.status = 'Done'
    make(d2)
    expect(d2.values.status).toBe('Done')
  })
  it('the assignee used for the superior check comes from the marketing record', () => {
    make(detail())
    expect(h.made.get_value.resource.submit).toHaveBeenCalledWith({ doctype: 'Marketing', filters: 'M1', fieldname: 'assign_to' })
  })
})

describe('changing a status', () => {
  const setup = (rows) => { const d = detail(rows); return { d, w: make(d) } }
  it('plain edits go straight into the row; follow up keeps digits only', async () => {
    const { d, w } = setup([{ status: 'Scheduled', follow_up: 0 }])
    await w.vm.onChange(0, 'follow_up', '12ab3')
    expect(d.values.interview_rounds_table[0].follow_up).toBe('123')
    await w.vm.onChange(0, 'follow_up', null)
    expect(d.values.interview_rounds_table[0].follow_up).toBe('')
  })
  it('cancelling asks who and why before the status changes', async () => {
    const { d, w } = setup([{ status: 'Scheduled' }])
    await w.vm.onChange(0, 'status', 'Cancelled')
    expect(w.vm.statusDialogOpen).toBe(true)
    expect(w.vm.pendingStatus).toBe('Cancelled')
    expect(d.values.interview_rounds_table[0].status).toBe('Scheduled')
    w.vm.confirmStatusDialog() // nothing filled in
    expect(w.vm.statusDialogOpen).toBe(true)
    Object.assign(w.vm.statusForm, { cancelled_by: 'Client', reason_of_cancel: '  Budget  ' })
    w.vm.confirmStatusDialog()
    expect(d.values.interview_rounds_table[0]).toMatchObject({ status: 'Cancelled', cancelled_by: 'Client', reason_of_cancel: 'Budget' })
    expect(w.vm.statusDialogOpen).toBe(false)
  })
  it('rescheduled and rejected also ask', async () => {
    for (const s of ['Rescheduled', 'rejected']) {
      const { w } = setup([{ status: 'Scheduled' }]); await w.vm.onChange(0, 'status', s); expect(w.vm.statusDialogOpen, s).toBe(true)
    }
  })
  it('completing warns that the round locks, and only continues if confirmed', async () => {
    const { d, w } = setup([{ status: 'Scheduled' }])
    h.confirm.mockResolvedValue(false)
    await w.vm.onChange(0, 'status', 'Completed')
    expect(h.confirm.mock.calls[0][0].message).toContain("'Completed'")
    expect(d.values.interview_rounds_table[0].status).toBe('Scheduled')
    h.confirm.mockResolvedValue(true)
    await w.vm.onChange(0, 'status', 'Completed')
    expect(d.values.interview_rounds_table[0].status).toBe('Completed')
  })
  it('re-selecting the current status does nothing special', async () => {
    const { w } = setup([{ status: 'Cancelled' }])
    await w.vm.onChange(0, 'status', 'Cancelled')
    expect(w.vm.statusDialogOpen).toBe(false)
    expect(h.confirm).not.toHaveBeenCalled()
  })
  it('an ordinary status change needs no confirmation', async () => {
    const { d, w } = setup([{ status: 'Scheduled' }])
    await w.vm.onChange(0, 'status', 'Pending')
    expect(h.confirm).not.toHaveBeenCalled()
    expect(d.values.interview_rounds_table[0].status).toBe('Pending')
  })
})

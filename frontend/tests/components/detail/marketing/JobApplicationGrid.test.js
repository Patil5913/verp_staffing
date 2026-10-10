import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { reactive, ref } from 'vue'

vi.mock('@/utils/common/siteTime', () => ({ siteTodayIso: () => '2026-05-15' }))
vi.mock('@/composables/detail/useIsSuperior', () => ({ useIsSuperior: () => ({ isSuperior: ref(false) }) }))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/common/SectionCard.vue', () => ({ default: { template: '<div><slot /></div>' } }))

import Grid from '@/components/detail/marketing/JobApplicationGrid.vue'

const detail = (rows = []) => ({ canWrite: ref(true), values: reactive({ assign_to: 'a@x.com', job_application_count: rows }) })
const make = (d, props = {}) => shallowMount(Grid, { props: { detail: d, ...props } })
beforeEach(() => { window.user = 'me@x.com' })

describe('JobApplicationGrid', () => {
  it('summarises days and applications with correct pluralisation', () => {
    expect(make(detail([])).vm.summary).toBe('0 days logged · 0 applications')
    expect(make(detail([{ total_application: 4 }])).vm.summary).toBe('1 day logged · 4 applications')
    expect(make(detail([{ total_application: '3' }, { total_application: 2 }])).vm.summary).toBe('2 days logged · 5 applications')
  })
  it('a new row is dated today with zero counts', () => {
    const d = detail(); make(d).vm.addRow()
    expect(d.values.job_application_count).toEqual([{ date: '2026-05-15', small_application: 0, large_application: 0, total_application: 0 }])
  })
  it('counts are clamped to whole numbers >= 0 and the total follows', () => {
    const d = detail([{ date: '2026-05-15', small_application: 2, large_application: 3, total_application: 5 }])
    const w = make(d)
    w.vm.setCount(0, 'small_application', '7')
    expect(d.values.job_application_count[0]).toMatchObject({ small_application: 7, total_application: 10 })
    w.vm.setCount(0, 'large_application', '-4')
    expect(d.values.job_application_count[0]).toMatchObject({ large_application: 0, total_application: 7 })
    w.vm.setCount(0, 'large_application', 'abc')
    expect(d.values.job_application_count[0].large_application).toBe(0)
  })
  it('setField and removeRow touch only the right row', () => {
    const d = detail([{ date: 'a' }, { date: 'b' }, { date: 'c' }])
    const w = make(d)
    w.vm.setField(1, 'date', 'z')
    expect(d.values.job_application_count.map((r) => r.date)).toEqual(['a', 'z', 'c'])
    w.vm.removeRow(0)
    expect(d.values.job_application_count.map((r) => r.date)).toEqual(['z', 'c'])
  })
  it('only your own row dated today can have its counts edited', () => {
    const w = make(detail())
    expect(w.vm.rowLocked({ date: '2026-05-15', owner: 'me@x.com' })).toBe(false)
    expect(w.vm.rowLocked({ date: '2026-05-15' })).toBe(false) // new, unsaved row
    expect(w.vm.rowLocked({ date: '2026-05-14', owner: 'me@x.com' })).toBe(true)
    expect(w.vm.rowLocked({ date: '2026-05-15', owner: 'boss@x.com' })).toBe(true)
  })
  it('editable follows lock and write permission', () => {
    expect(make(detail()).vm.editable).toBe(true)
    expect(make(detail(), { locked: true }).vm.editable).toBe(false)
    const d = detail(); d.canWrite.value = false
    expect(make(d).vm.editable).toBe(false)
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { reactive } from 'vue'

const h = vi.hoisted(() => ({ made: {}, notify: { success: vi.fn(), error: vi.fn() } }))
vi.mock('frappe-ui', () => ({ Dialog: { template: '<div />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => (h.made[o.url.split('.').pop()] = reactive({ resource: { fetch: vi.fn(async () => null), submit: vi.fn(async () => null) }, isLoading: false })),
}))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))

import Panel from '@/components/detail/erp/SampleDataPanel.vue'

const make = (props = {}) => shallowMount(Panel, { props })
const summary = () => h.made.get_sample_data_summary.resource.fetch
const remove = () => h.made.remove_sample_data.resource.submit
beforeEach(() => { vi.clearAllMocks(); h.made = {} })

describe('checking what would be removed', () => {
  it('nothing tracked: say so, no dialog', async () => {
    const w = make(); summary().mockResolvedValue({ total: 0 })
    await w.vm.onCheck()
    expect(h.notify.success).toHaveBeenCalledWith('No sample data found.')
    expect(w.vm.showDialog).toBe(false)
  })
  it('a failed check does nothing', async () => {
    const w = make(); await w.vm.onCheck()
    expect(w.vm.showDialog).toBe(false)
  })
  it('records found: open the dialog, titled by whether live links exist', async () => {
    const w = make(); summary().mockResolvedValue({ total: 3, records: { Lead: ['a', 'b'], Weird: ['c'] }, conflicts: [], unexpected_doctypes: ['Weird'] })
    await w.vm.onCheck()
    expect(w.vm.showDialog).toBe(true)
    expect(w.vm.dialogTitle).toBe('Remove Sample Data')
    expect(w.vm.deletableTotal).toBe(2)
    expect(w.vm.relevantRecords).toEqual({ Lead: ['a', 'b'], Weird: ['c'] })
    w.vm.summary = { ...w.vm.summary, conflicts: [{}] }
    expect(w.vm.dialogTitle).toBe('Sample Data Has Live Links')
  })
  it('follows the removed flag given by the page', async () => {
    const w = make({ isSampleDataRemoved: 0 })
    expect(w.vm.removed).toBe(false)
    await w.setProps({ isSampleDataRemoved: 1 })
    expect(w.vm.removed).toBe(true)
  })
})

describe('removing', () => {
  const open = async (sum = { total: 1, records: { Lead: ['a'] }, conflicts: [], unexpected_doctypes: [] }) => {
    const w = make(); summary().mockResolvedValue(sum); await w.vm.onCheck(); return w
  }
  it('without live links, nothing extra is deleted', async () => {
    const w = await open(); remove().mockResolvedValue({ status: 'done', is_sample_data_removed: true, result: { doctype_counts: { Lead: 1 }, errors: [] } })
    await w.vm.onConfirmRemove()
    expect(remove()).toHaveBeenCalledWith({ delete_conflicts: 0 })
    expect(h.notify.success).toHaveBeenCalledWith('Sample data removed.')
    expect([w.vm.removed, w.vm.showDialog, w.emitted('removed')?.length]).toEqual([true, false, 1])
  })
  it('with live links the user has already agreed to delete them', async () => {
    const w = await open({ total: 1, records: {}, conflicts: [{ linked_name: 'x' }], unexpected_doctypes: [] })
    remove().mockResolvedValue({ status: 'done', is_sample_data_removed: true, result: {} })
    await w.vm.onConfirmRemove()
    expect(remove()).toHaveBeenCalledWith({ delete_conflicts: 1 })
  })
  it('newly found live links bring the dialog back with them listed, and delete nothing', async () => {
    const w = await open(); remove().mockResolvedValue({ status: 'conflicts', conflicts: [{ linked_name: 'x' }] })
    await w.vm.onConfirmRemove()
    expect(w.vm.summary.conflicts).toHaveLength(1)
    expect(w.vm.showDialog).toBe(true)
    expect(w.vm.removed).toBe(false)
  })
  it('failures are counted and the feature stays available for another try', async () => {
    const w = await open(); remove().mockResolvedValue({ status: 'done', is_sample_data_removed: false, result: { doctype_counts: { Lead: 4, Customer: 1 }, errors: [{ name: 'x' }] } })
    await w.vm.onConfirmRemove()
    expect(h.notify.error).toHaveBeenCalledWith('5 record(s) deleted; 1 failed - see the error log for details.')
    expect(w.vm.removed).toBe(false)
    expect(w.emitted('removed')).toBeUndefined()
  })
  it('records needing review are named, and also not treated as finished', async () => {
    const w = await open(); remove().mockResolvedValue({ status: 'done', is_sample_data_removed: false, result: { doctype_counts: { Lead: 2 }, errors: [], skipped_unexpected: { Weird: ['c'], Odd: [] } } })
    await w.vm.onConfirmRemove()
    expect(h.notify.success).toHaveBeenCalledWith('2 record(s) deleted. Left as-is (needs manual review): Weird, Odd.')
    expect(w.vm.removed).toBe(false)
  })
  it('a refused removal changes nothing', async () => {
    const w = await open(); await w.vm.onConfirmRemove()
    expect(w.vm.showDialog).toBe(true); expect(w.vm.removed).toBe(false)
  })
})

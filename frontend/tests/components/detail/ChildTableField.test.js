import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'

vi.mock('frappe-ui', () => ({ Dialog: { template: '<div />' } }))
vi.mock('@/utils/common/siteTime', () => ({ siteNowIso: () => '2026-05-15 10:00:00', siteTodayIso: () => '2026-05-15' }))
vi.mock('@/utils/detail/fieldProblems', () => ({
  DESCRIPTION_MIN_LENGTH: 10,
  rowFieldProblem: (table, field, value) => (field === 'month' && value === 'bad' ? 'Use MM-YYYY' : ''),
}))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/ui/TruncatedText.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/FieldControl.vue', () => ({ default: { template: '<i />' } }))

import Field from '@/components/detail/ChildTableField.vue'

const COLS = [
  { fieldname: 'company', label: 'Company', fieldtype: 'Data' },
  { fieldname: 'month', label: 'Month', fieldtype: 'Data' },
  { fieldname: 'date', label: 'Date', fieldtype: 'Datetime', default: 'Now' },
  { fieldname: 'day', label: 'Day', fieldtype: 'Date', default: 'Today' },
  { fieldname: 'kind', label: 'Kind', fieldtype: 'Data', default: 'Full time' },
  { fieldname: 'end', label: 'End', fieldtype: 'Data', depends_on: 'eval:!doc.current' },
  { fieldname: 'current', label: 'Current', fieldtype: 'Check' },
]
const make = (props = {}) => shallowMount(Field, { props: { table: { fieldname: 'exp', label: 'Experience', columns: COLS }, rows: [{ company: 'Acme' }], ...props } })

beforeEach(() => vi.clearAllMocks())

describe('opening a row', () => {
  it('a new row gets each columns default, with Now and Today resolved', () => {
    const w = make(); w.vm.openRow(null)
    expect(w.vm.draft).toEqual({ date: '2026-05-15 10:00:00', day: '2026-05-15', kind: 'Full time' })
    expect(w.vm.dialogTitle).toBe('Add Experience')
    expect(w.vm.dialogOpen).toBe(true)
  })
  it('editing copies the row, so cancelling changes nothing', () => {
    const rows = [{ company: 'Acme' }]
    const w = make({ rows }); w.vm.openRow(0)
    w.vm.draft.company = 'Changed'
    expect(rows[0].company).toBe('Acme')
    expect(w.vm.dialogTitle).toBe('Edit Experience')
  })
  it('previous errors are cleared', () => {
    const w = make(); w.vm.rowError = 'old'; w.vm.fieldProblems = { a: 'x' }
    w.vm.openRow(null)
    expect([w.vm.rowError, w.vm.fieldProblems]).toEqual(['', {}])
  })
})

describe('columns', () => {
  it('hidden columns and failed depends_on are left out of the dialog', () => {
    const w = make({ hiddenColumns: ['month'] }); w.vm.openRow(null)
    const names = w.vm.visibleColumns.map((c) => c.fieldname)
    expect(names).not.toContain('month')
    expect(names).toContain('end')
    w.vm.draft.current = 1
    expect(w.vm.visibleColumns.map((c) => c.fieldname)).not.toContain('end')
  })
  it('overrides are merged onto just that column', () => {
    const w = make({ fieldOverrides: { company: { accept: '.pdf' } } }); w.vm.openRow(null)
    expect(w.vm.visibleColumns.find((c) => c.fieldname === 'company').accept).toBe('.pdf')
    expect(w.vm.visibleColumns.find((c) => c.fieldname === 'month').accept).toBeUndefined()
  })
  it('the preview shows at most four columns', () => expect(make().vm.previewColumns).toHaveLength(4))
  it('add row disappears at the cap', () => {
    expect(make().vm.atMaxRows).toBe(false)
    expect(make({ maxRows: 1 }).vm.atMaxRows).toBe(true)
    expect(make({ maxRows: 2 }).vm.atMaxRows).toBe(false)
  })
  it('link queries may depend on the row being edited', () => {
    const fn = vi.fn((draft) => ({ role: { filters: { dept: draft.company } } }))
    const w = make({ linkQueries: fn }); w.vm.openRow(0)
    expect(w.vm.resolvedLinkQueries).toEqual({ role: { filters: { dept: 'Acme' } } })
    expect(make({ linkQueries: { a: 1 } }).vm.resolvedLinkQueries).toEqual({ a: 1 })
  })
})

describe('editing fields', () => {
  it('sets the value, applies a patch from onFieldChange, and tells the parent which row changed', async () => {
    const onFieldChange = vi.fn(async () => ({ uom: 'Nos' }))
    const w = make({ onFieldChange }); w.vm.openRow(0)
    await w.vm.onFieldInput('item', 'Widget')
    expect(w.vm.draft).toMatchObject({ item: 'Widget', uom: 'Nos' })
    expect(w.emitted('field-edited')[0][0]).toEqual({ index: 0, fieldname: 'item' })
  })
  it('a new row does not report field edits', async () => {
    const w = make(); w.vm.openRow(null)
    await w.vm.onFieldInput('company', 'X')
    expect(w.emitted('field-edited')).toBeUndefined()
  })
  it('live problems are recorded and block Done', async () => {
    const w = make(); w.vm.openRow(0)
    await w.vm.onFieldInput('month', 'bad')
    expect(w.vm.fieldProblems.month).toBe('Use MM-YYYY')
    await w.vm.commitRow()
    expect(w.vm.rowError).toMatch(/fix the highlighted/)
    expect(w.emitted('update:rows')).toBeUndefined()
    await w.vm.onFieldInput('month', '05-2026')
    await w.vm.commitRow()
    expect(w.emitted('update:rows')).toHaveLength(1)
  })
  it('file metadata can patch the draft', async () => {
    const onFileMeta = vi.fn(async () => ({ title: 'cv' }))
    const w = make({ onFileMeta }); w.vm.openRow(null)
    await w.vm.onFileMeta('document', { file_name: 'cv.pdf' })
    expect(onFileMeta).toHaveBeenCalledWith('document', { file_name: 'cv.pdf' }, w.vm.draft)
    expect(w.vm.draft.title).toBe('cv')
    await make().vm.onFileMeta('x', {}) // no handler: fine
  })
  it('counts description characters without whitespace', async () => {
    const w = make(); w.vm.openRow(null)
    w.vm.draft.description = ' a b\nc '
    expect(w.vm.descriptionCharCount).toBe(3)
  })
})

describe('saving', () => {
  it('adds a new row after the others', async () => {
    const w = make(); w.vm.openRow(null); w.vm.draft.company = 'Beta'
    await w.vm.commitRow()
    expect(w.emitted('update:rows')[0][0].map((r) => r.company)).toEqual(['Acme', 'Beta'])
    expect(w.emitted('row-saved')).toBeUndefined()
    expect(w.vm.dialogOpen).toBe(false)
  })
  it('replaces an edited row and says which', async () => {
    const w = make({ rows: [{ company: 'A' }, { company: 'B' }] }); w.vm.openRow(1); w.vm.draft.company = 'B2'
    await w.vm.commitRow()
    expect(w.emitted('update:rows')[0][0].map((r) => r.company)).toEqual(['A', 'B2'])
    expect(w.emitted('row-saved')[0]).toEqual([1])
  })
  it('a validateRow message blocks saving and stays on the dialog', async () => {
    const validateRow = vi.fn(async () => 'Dates overlap')
    const w = make({ validateRow }); w.vm.openRow(null)
    await w.vm.commitRow()
    expect(w.vm.rowError).toBe('Dates overlap')
    expect(w.vm.dialogOpen).toBe(true)
    expect(w.vm.validating).toBe(false)
    expect(w.emitted('update:rows')).toBeUndefined()
  })
  it('validateRow gets the draft, the rows and the index', async () => {
    const validateRow = vi.fn(async () => null)
    const w = make({ validateRow }); w.vm.openRow(0)
    await w.vm.commitRow()
    expect(validateRow).toHaveBeenCalledWith(w.vm.draft, w.vm.rows, 0)
    expect(w.emitted('update:rows')).toHaveLength(1)
  })
  it('removing a row leaves the others and the original array', () => {
    const rows = [{ a: 1 }, { a: 2 }, { a: 3 }]
    const w = make({ rows })
    w.vm.removeRow(1)
    expect(w.emitted('update:rows')[0][0]).toEqual([{ a: 1 }, { a: 3 }])
    expect(rows).toHaveLength(3)
  })
})

describe('formatting', () => {
  const col = (fieldtype) => ({ fieldtype })
  it('blank values are a dash; checks are Yes/No', () => {
    const w = make()
    for (const v of [null, undefined, '']) expect(w.vm.formatCell(col('Data'), v)).toBe('-')
    expect(w.vm.formatCell(col('Check'), 1)).toBe('Yes')
    expect(w.vm.formatCell(col('Check'), 0)).toBe('No')
    expect(w.vm.formatCell(col('Data'), 5)).toBe('5')
  })
  it('durations show in the unit they were saved with', () => {
    const w = make()
    expect(w.vm.formatDuration(5400, 'Minutes')).toBe('90 min')
    expect(w.vm.formatDuration(5400, 'Hours')).toBe('1.5 hr')
    expect(w.vm.formatDuration(7200, undefined)).toBe('2 hr')
    expect(w.vm.formatDuration(5400, undefined)).toBe('90 min')
    expect(w.vm.formatDuration(0, 'Hours')).toBe('0 min')
    expect(w.vm.formatCell(col('Duration'), 3600, { duration_unit: 'Hours' })).toBe('1 hr')
  })
  it('long text columns are wide', () => {
    const w = make()
    expect(w.vm.isWide(col('Small Text'))).toBe(true)
    expect(w.vm.isWide(col('Data'))).toBe(false)
  })
  it('row errors default to none', () => {
    const w = make({ rowErrors: { 1: ['bad'] } })
    expect(w.vm.rowErrorsAt(0)).toEqual([])
    expect(w.vm.rowErrorsAt(1)).toEqual(['bad'])
  })
})

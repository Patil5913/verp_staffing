import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'

const h = vi.hoisted(() => ({ call: vi.fn(), notify: { error: vi.fn() } }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), LoadingIndicator: { template: '<i />' }, FileUploader: { template: '<div />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/errors', () => ({ normalizeError: (e) => ({ message: e.message }) }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<i />' } }))

import Wizard from '@/components/common/DataImportWizard.vue'

const API = 'verp_staffing.setup.data_import_api.'
const FIELDS = {
  fields: [{ fieldname: 'name1', label: 'Name', reqd: 1 }, { fieldname: 'email', label: 'Email', reqd: 0 }],
  child_tables: [{ fieldname: 'items', label: 'Items', child_doctype: 'Item Row', fields: [{ fieldname: 'qty', label: 'Qty', reqd: 1 }, { fieldname: 'note', label: 'Note', reqd: 0 }] }],
  linked: { doctype: 'Lead Detail Form', fields: [{ fieldname: 'phone', label: 'Phone' }], child_tables: [{ fieldname: 'edu', label: 'Education', fields: [{ fieldname: 'school', label: 'School' }] }] },
}
const PREVIEW = {
  columns: [{ header_title: 'ID' }, { header_title: 'Name', df: { parent: 'Customer', fieldname: 'name1' } }, { header_title: 'Skip me', skip_import: 1 }, { header_title: 'Mystery' }],
  data: [['1', 'Pat', 'x', 'y'], ['2', 'Sam', 'x', 'y']], warnings: [{ type: 'info', message: 'fyi' }],
}
const open = async (answers = {}) => {
  h.call.mockImplementation(async (m, a) => {
    if (m in answers) { const v = answers[m]; if (typeof v === 'function') return v(a); if (v instanceof Error) throw v; return v }
    if (m === API + 'get_importable_doctypes') return { suggested: [{ doctype: 'Customer', label: 'Candidate' }], other: [{ doctype: 'Lead', label: 'Lead' }] }
    if (m === API + 'get_template_fields') return FIELDS
  })
  const w = shallowMount(Wizard); await flushPromises(); return w
}
beforeEach(() => { vi.clearAllMocks(); h.call.mockReset() })

describe('start', () => {
  it('lists importable doctypes; a failure is shown', async () => {
    expect((await open()).vm.doctypes.suggested).toHaveLength(1)
    const w = await open({ [API + 'get_importable_doctypes']: new Error('denied') })
    expect([w.vm.errorMessage, w.vm.loadingDoctypes]).toEqual(['denied', false])
  })
  it('choosing a doctype uses the friendly label and loads its fields', async () => {
    const w = await open()
    w.vm.chooseDoctype('Customer'); await flushPromises()
    expect(w.vm.selectedLabel).toBe('Candidate')
    expect(w.vm.templateFields.fields).toHaveLength(2)
    w.vm.chooseDoctype('Other'); expect(w.vm.selectedLabel).toBe('Other')
  })
})

describe('template field picking', () => {
  const picked = async () => { const w = await open(); w.vm.chooseDoctype('Customer'); await flushPromises(); return w }
  it('everything starts ticked except linked form fields', async () => {
    const w = await picked()
    expect(w.vm.selectedFieldCount).toBe(2 + 2)
  })
  it('required fields cannot be switched off, optional ones can', async () => {
    const w = await picked()
    w.vm.toggleField('name1'); expect(w.vm.selectedFields.has('name1')).toBe(true)
    w.vm.toggleField('email'); expect(w.vm.selectedFields.has('email')).toBe(false)
    w.vm.toggleField('email'); expect(w.vm.selectedFields.has('email')).toBe(true)
    w.vm.toggleChildField('items', 'qty'); expect(w.vm.selectedChildFields.items.has('qty')).toBe(true)
    w.vm.toggleChildField('items', 'note'); expect(w.vm.selectedChildFields.items.has('note')).toBe(false)
  })
  it('linked form fields toggle freely', async () => {
    const w = await picked()
    w.vm.toggleLinkedField('phone'); w.vm.toggleLinkedChildField('edu', 'school')
    expect(w.vm.selectedFieldCount).toBe(6)
    w.vm.toggleLinkedField('phone'); expect(w.vm.selectedFieldCount).toBe(5)
  })
  it('mandatory-only keeps required fields and clears the linked ones', async () => {
    const w = await picked(); w.vm.toggleLinkedField('phone')
    w.vm.selectMandatoryFields()
    expect([...w.vm.selectedFields]).toEqual(['name1'])
    expect([...w.vm.selectedChildFields.items]).toEqual(['qty'])
    expect(w.vm.selectedLinkedFields.size).toBe(0)
  })
  it('select all ticks everything including the linked form', async () => {
    const w = await picked(); w.vm.selectAllFields()
    expect(w.vm.selectedFieldCount).toBe(2 + 2 + 1 + 1)
  })
  it('changing the doctype resets the picker', async () => {
    const w = await picked(); w.vm.showFieldPicker = true
    w.vm.chooseDoctype(''); await flushPromises()
    expect([w.vm.showFieldPicker, w.vm.templateFields.fields, w.vm.selectedFieldCount]).toEqual([false, [], 0])
  })
  it('the downloaded template carries the selection', async () => {
    const w = await picked(); window.open = vi.fn()
    w.vm.toggleField('email'); w.vm.toggleLinkedField('phone')
    w.vm.downloadTemplate()
    const url = new URL('http://x' + window.open.mock.calls[0][0].replace('/api', '/api'))
    expect(url.pathname).toBe('/api/method/' + API + 'download_template')
    const q = url.searchParams
    expect([q.get('doctype'), q.get('export_records'), q.get('file_type')]).toEqual(['Customer', 'blank_template', 'Excel'])
    expect(JSON.parse(q.get('fields'))).toEqual(['name1'])
    expect(JSON.parse(q.get('child_fields'))).toEqual({ items: ['qty', 'note'] })
    expect(JSON.parse(q.get('linked_fields'))).toEqual(['phone'])
  })
  it('the mapping dropdown lists plain, child table and linked form fields', async () => {
    const w = await picked()
    const values = w.vm.fieldOptions.map((o) => o.value)
    expect(values).toEqual(["Don't Import", 'name1', 'email', 'items.qty', 'items.note', 'ldf::phone', 'ldf::edu.school'])
  })
})

describe('sheet links', () => {
  it('only https Google Sheets links are accepted', async () => {
    const w = await open()
    for (const bad of ['', 'not a url', 'http://docs.google.com/spreadsheets/d/1', 'https://evil.com/spreadsheets/d/1', 'https://docs.google.com/document/d/1']) {
      w.vm.sheetUrl = bad
      await w.vm.useSheetUrl()
      expect(w.vm.sheetUrlError, bad).toBeTruthy()
    }
    expect(h.call.mock.calls.some((c) => c[0] === API + 'start_data_import_wizard')).toBe(false)
  })
  it('a good link starts the import and moves on to the preview after a moment', async () => {
    vi.useFakeTimers()
    const w = await open({ [API + 'start_data_import_wizard']: { data_import: 'DI-1', preview: PREVIEW, column_map: {} } })
    w.vm.chooseDoctype('Customer'); w.vm.sheetUrl = ' https://docs.google.com/spreadsheets/d/abc/edit '
    await w.vm.useSheetUrl()
    expect(h.call).toHaveBeenCalledWith(API + 'start_data_import_wizard', { doctype: 'Customer', google_sheets_url: 'https://docs.google.com/spreadsheets/d/abc/edit' })
    expect(w.vm.sheetLinkVerified).toBe(true)
    vi.advanceTimersByTime(800)
    expect(w.vm.step).toBe(2)
    vi.useRealTimers()
  })
  it('a server rejection is shown on the link', async () => {
    const w = await open({ [API + 'start_data_import_wizard']: new Error('Sheet is private') })
    w.vm.sheetUrl = 'https://docs.google.com/spreadsheets/d/abc'
    await w.vm.useSheetUrl()
    expect(w.vm.sheetUrlError).toBe('Sheet is private')
    expect(w.vm.sheetLinkVerified).toBe(false)
  })
  it('switching source clears old messages', async () => {
    const w = await open(); w.vm.sheetUrlError = 'x'; w.vm.errorMessage = 'y'; w.vm.sheetLinkVerified = true
    w.vm.switchSourceMode('sheet')
    expect([w.vm.sourceMode, w.vm.sheetUrlError, w.vm.errorMessage, w.vm.sheetLinkVerified]).toEqual(['sheet', '', '', false])
  })
})

describe('preview', () => {
  const upload = async (over = {}) => {
    const w = await open({ [API + 'start_data_import_wizard']: { data_import: 'DI-1', preview: { ...PREVIEW, ...over }, column_map: { 3: 'name1' } } })
    w.vm.chooseDoctype('Customer'); await w.vm.onFileUploaded({ file_url: '/files/a.xlsx' }); return w
  }
  it('hides skipped columns and info notes, keeps real warnings', async () => {
    const w = await upload({ warnings: [{ type: 'info' }, { type: 'warning', message: 'bad row' }] })
    expect(w.vm.previewColumns).toEqual(['ID', 'Name', 'Mystery'])
    expect(w.vm.previewRows[0]).toEqual(['1', 'Pat', 'y'])
    expect(w.vm.warnings).toEqual([{ type: 'warning', message: 'bad row' }])
    expect(w.vm.totalRows).toBe(2)
    expect(w.vm.dataImportName).toBe('DI-1')
  })
  it('a failed upload forgets the file and shows why', async () => {
    const w = await open({ [API + 'start_data_import_wizard']: new Error('Bad file') })
    await w.vm.onFileUploaded({ file_url: '/f' })
    expect([w.vm.uploadedFile, w.vm.errorMessage, w.vm.creatingImport]).toEqual([null, 'Bad file', false])
  })
  it('column mapping: guessed from the file, overridden by the user, and counted when unmapped', async () => {
    const w = await upload()
    const cols = w.vm.mappedColumns
    expect(cols.map((c) => c.headerTitle)).toEqual(['Name', 'Skip me', 'Mystery'])
    expect(cols[0].currentValue).toBe('name1')
    expect(cols[1].currentValue).toBe("Don't Import")
    expect(cols[2].currentValue).toBe("Don't Import")
    w.vm.columnMap = { 2: 'email' }
    expect(w.vm.mappedColumns[2].currentValue).toBe('email') // a stored mapping wins over the guess
  })
  it('unmapped columns are counted', async () => {
    const w = await upload()
    w.vm.columnMap = {}
    expect(w.vm.unmappedColumnCount).toBe(2)
  })
  it('applying changes sends only what differs, refreshes the preview and clears the pending edits', async () => {
    const w = await upload()
    w.vm.columnMap = {}
    w.vm.pendingColumnMap[0] = 'name1'; w.vm.pendingColumnMap[1] = "Don't Import"
    expect(w.vm.hasPendingColumnChanges).toBe(false) // both equal the current mapping
    w.vm.pendingColumnMap[2] = 'email'
    expect(w.vm.hasPendingColumnChanges).toBe(true)
    h.call.mockImplementation(async () => ({ preview: PREVIEW, column_map: { 2: 'email' } }))
    await w.vm.applyColumnMapping()
    expect(h.call).toHaveBeenLastCalledWith(API + 'remap_data_import_columns', { data_import: 'DI-1', column_map: { 2: 'email' } })
    expect(w.vm.columnMap).toEqual({ 2: 'email' })
    expect(Object.keys(w.vm.pendingColumnMap)).toHaveLength(0)
    expect(w.vm.remapping).toBe(false)
  })
  it('nothing changed, nothing sent', async () => {
    const w = await upload(); h.call.mockClear()
    await w.vm.applyColumnMapping()
    expect(h.call).not.toHaveBeenCalled()
  })
})

describe('running the import', () => {
  afterEach(() => vi.useRealTimers())
  const ready = async (extra = {}) => {
    const w = await open({ [API + 'start_data_import_wizard']: { data_import: 'DI-1', preview: PREVIEW }, ...extra })
    w.vm.chooseDoctype('Customer'); await w.vm.onFileUploaded({ file_url: '/f' }); h.call.mockClear(); return w
  }
  it('is blocked while the preview still has warnings', async () => {
    const w = await ready(); w.vm.warnings = [{ type: 'warning' }]
    await w.vm.startImport()
    expect(h.call).not.toHaveBeenCalled()
  })
  it('runs, polls until finished and shows the result', async () => {
    vi.useFakeTimers()
    const w = await ready()
    let polls = 0
    h.call.mockImplementation(async (m) => {
      if (m === API + 'get_data_import_wizard_status') return ++polls < 3 ? { status: 'In Progress' } : { status: 'Partial Success', total: 10, success: 8, failed: 2, failures: [{ row: 3 }] }
    })
    const p = w.vm.startImport()
    await vi.advanceTimersByTimeAsync(2000 * 3)
    await p
    expect(h.call).toHaveBeenCalledWith(API + 'run_data_import_wizard', { data_import: 'DI-1', import_type: 'Insert New Records' })
    expect([w.vm.step, w.vm.result.success, w.vm.result.failed]).toEqual([4, 8, 2])
  })
  it('a refused start returns to the preview with the reason', async () => {
    const w = await ready(); h.call.mockRejectedValue(new Error('Not allowed'))
    await w.vm.startImport()
    expect([w.vm.step, w.vm.errorMessage, w.vm.starting]).toEqual([2, 'Not allowed', false])
  })
  it('gives up politely after five minutes', async () => {
    vi.useFakeTimers()
    const w = await ready()
    h.call.mockImplementation(async (m) => (m === API + 'get_data_import_wizard_status' ? { status: 'In Progress' } : undefined))
    const p = w.vm.startImport()
    await vi.advanceTimersByTimeAsync(2000 * 151)
    await p
    expect(w.vm.errorMessage).toMatch(/taking longer/)
    expect(w.vm.step).toBe(2)
  })
  it('start over clears everything', async () => {
    const w = await ready(); w.vm.step = 4; w.vm.errorMessage = 'x'
    w.vm.reset()
    expect([w.vm.step, w.vm.form.doctype, w.vm.dataImportName, w.vm.previewRows, w.vm.errorMessage, w.vm.result.total]).toEqual([0, '', '', [], '', 0])
  })
})

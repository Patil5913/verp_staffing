import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, computed } from 'vue'

const h = vi.hoisted(() => ({ tl: null, confirm: vi.fn(), sysmgr: vi.fn() }))
vi.mock('@/composables/detail/useTimeline', () => ({ useTimeline: () => h.tl }))
vi.mock('@/utils/common/confirmDialog', () => ({ confirmLeave: (...a) => h.confirm(...a) }))
vi.mock('@/utils/common/roles', () => ({ isSystemManager: () => h.sysmgr() }))
vi.mock('frappe-ui', () => ({
  call: vi.fn(), debounce: (f) => f,
  FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' }, Combobox: { template: '<div />' }, Popover: { template: '<div />' },
  Avatar: { template: '<span class="avatar" />' }, TextEditor: { template: '<div class="editor" />' },
  Dialog: { props: ['modelValue', 'options'], template: '<div v-if="modelValue" class="dialog"><h2>{{ options.title }}</h2><slot name="body-content" /><slot name="actions" /></div>' },
}))

import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'

const entries = [
  { type: 'note', id: 'N1', html: '<p>hello</p><script>x()</script>', added_by: 'a@x.com' },
  { type: 'update', id: 'U1', changes: [{ fieldname: 'status', old: 'Open', new: 'Won' }], creation: '2026-03-04 10:00:00', owner: 'a@x.com' },
  { type: 'task', id: 'T1', description: 'Call', date: '2026-03-05 10:00:00', assigned_to: 'a@x.com', is_completed: 0 },
  { type: 'event', id: 'E1', category: 'Meeting', summary: 'Sync', date: '2026-03-06 09:30:00' },
]

beforeEach(() => {
  window.site_time_zone = 'UTC'
  h.confirm.mockReset().mockResolvedValue(true)
  h.sysmgr.mockReset().mockReturnValue(false)
  h.tl = {
    timeline: {}, entries: ref(entries), adding: ref(false), creatingTask: ref(false), creatingEvent: ref(false), changing: ref(false),
    addNote: vi.fn(), createTask: vi.fn(async () => ({ name: 'T9' })), createEvent: vi.fn(async () => ({ name: 'E9' })),
    updateNote: vi.fn(async () => ({ ok: 1 })), deleteNote: vi.fn(), updateTask: vi.fn(async () => ({ ok: 1 })), updateEvent: vi.fn(async () => ({ ok: 1 })), deleteActivity: vi.fn(),
  }
})
afterEach(() => delete window.site_time_zone)

const mk = (props = {}) => mount(ActivityTimeline, { props: { doctype: 'Lead', name: 'L1', types: ['note', 'update'], ...props }, global: { stubs: { AppLinkField: { template: '<div />' }, AppCombobox: { template: '<div />' } } } })

describe('ActivityTimeline', () => {
  it('shows only the entry types this tab is for', () => {
    expect(mk().vm.entries.map((e) => e.id)).toEqual(['N1', 'U1'])
    expect(mk({ types: ['task', 'event'] }).vm.entries.map((e) => e.id)).toEqual(['T1', 'E1'])
  })
  it('the timeline is requested for the record it sits on', () => {
    expect(mk().vm.entries).toBeTruthy()
  })
  it('a note is sanitised before it is rendered', () => {
    const html = mk().html()
    expect(html).toContain('hello')
    expect(html).not.toContain('<script')
  })
  it('cleaning strips scripts and event handlers but keeps formatting', () => {
    const { clean } = mk().vm
    expect(clean('<b onclick="x()">bold</b><script>1</script>')).toBe('<b>bold</b>')
    expect(clean(null)).toBe('')
  })
  it('empty text is configurable', () => {
    h.tl.entries.value = []
    expect(mk({ emptyText: 'No notes yet.' }).text()).toContain('No notes yet.')
  })
});

describe('adding a note', () => {
  it('ignores a blank draft', () => {
    const w = mk({ showComposer: true })
    w.vm.draft = '   '
    w.vm.onAdd()
    expect(h.tl.addNote).not.toHaveBeenCalled()
  })
  it('sends the text and clears the composer', () => {
    const w = mk({ showComposer: true })
    w.vm.draft = 'Called, will follow up'
    w.vm.onAdd()
    expect(h.tl.addNote).toHaveBeenCalledWith('Called, will follow up')
    expect(w.vm.draft).toBe('')
  })
})

describe('creating tasks and events', () => {
  it('a new task defaults its time to now, in the company zone, and starts blank', () => {
    vi.useFakeTimers(); vi.setSystemTime(new Date('2026-03-04T12:34:56Z'))
    const w = mk({ types: ['task'], allowCreate: true })
    w.vm.openTaskDialog()
    expect(w.vm.showTaskDialog).toBe(true)
    expect(w.vm.taskForm).toEqual({ description: '', date: '2026-03-04T12:34', assignedTo: '' })
    vi.useRealTimers()
  })
  it('blank fields are left out rather than sent empty, and the dialog closes only on success', async () => {
    const w = mk({ types: ['task'], allowCreate: true })
    w.vm.openTaskDialog()
    Object.assign(w.vm.taskForm, { description: '', date: '', assignedTo: '' })
    await w.vm.onCreateTask()
    expect(h.tl.createTask).toHaveBeenCalledWith({ description: undefined, date: undefined, assigned_to: undefined })
    expect(w.vm.showTaskDialog).toBe(false)
    w.vm.openTaskDialog()
    h.tl.createTask.mockResolvedValue(null)
    await w.vm.onCreateTask()
    expect(w.vm.showTaskDialog).toBe(true)
  })
  it('an event needs a category, a date and a summary', async () => {
    const w = mk({ types: ['event'], allowCreate: true })
    w.vm.openEventDialog()
    await w.vm.onCreateEvent()
    expect(h.tl.createEvent).not.toHaveBeenCalled()
    Object.assign(w.vm.eventForm, { category: 'Call', summary: '   ' })
    await w.vm.onCreateEvent()
    expect(h.tl.createEvent).not.toHaveBeenCalled()
  })
  it('a valid event is sent trimmed with optional fields omitted', async () => {
    const w = mk({ types: ['event'], allowCreate: true })
    w.vm.openEventDialog()
    Object.assign(w.vm.eventForm, { category: 'Call', summary: '  Intro  ' })
    await w.vm.onCreateEvent()
    expect(h.tl.createEvent).toHaveBeenCalledWith({ category: 'Call', date: w.vm.eventForm.date, summary: 'Intro', description: undefined, assigned_to: undefined })
    expect(w.vm.showEventDialog).toBe(false)
  })
  it('reopening a creation dialog forgets the previous attempt', () => {
    const w = mk({ types: ['event'] })
    w.vm.openEventDialog()
    Object.assign(w.vm.eventForm, { category: 'Call', summary: 'old' })
    w.vm.openEventDialog()
    expect(w.vm.eventForm).toMatchObject({ category: '', summary: '', description: '', assignedTo: '' })
  })
})

describe('editing existing entries', () => {
  it('a note keeps its html and cannot be saved empty', async () => {
    const w = mk()
    w.vm.openNoteEdit(entries[0])
    expect(w.vm.noteEdit).toEqual({ id: 'N1', html: entries[0].html })
    w.vm.noteEdit.html = '<p> </p>'
    await w.vm.saveNote()
    expect(h.tl.updateNote).not.toHaveBeenCalled()
    w.vm.noteEdit.html = '<p>fixed</p>'
    await w.vm.saveNote()
    expect(h.tl.updateNote).toHaveBeenCalledWith('N1', '<p>fixed</p>')
    expect(w.vm.showNoteEdit).toBe(false)
  })
  it('the edit dialog stays open when the server refuses', async () => {
    h.tl.updateNote.mockResolvedValue(null)
    const w = mk()
    w.vm.openNoteEdit(entries[0])
    await w.vm.saveNote()
    expect(w.vm.showNoteEdit).toBe(true)
  })
  it('deleting asks first and only deletes when confirmed', async () => {
    const w = mk()
    h.confirm.mockResolvedValue(false)
    await w.vm.removeNote(entries[0])
    expect(h.tl.deleteNote).not.toHaveBeenCalled()
    h.confirm.mockResolvedValue(true)
    await w.vm.removeNote(entries[0])
    expect(h.tl.deleteNote).toHaveBeenCalledWith('N1')
    expect(h.confirm.mock.calls[0][0]).toMatchObject({ title: 'Delete this note?', leaveLabel: 'Delete' })
    await w.vm.removeActivity('CRM Task', entries[2], 'task')
    expect(h.tl.deleteActivity).toHaveBeenCalledWith('CRM Task', 'T1')
  })
  it('an ordinary user can only complete a task; a system manager can change it all', async () => {
    const w = mk({ types: ['task'] })
    w.vm.openTaskEdit(entries[2])
    expect(w.vm.taskEdit).toMatchObject({ id: 'T1', description: 'Call', date: '2026-03-05T10:00', assignedTo: 'a@x.com', isCompleted: false })
    w.vm.taskEdit.description = 'Changed'
    w.vm.taskEdit.isCompleted = true
    await w.vm.saveTask()
    expect(h.tl.updateTask).toHaveBeenLastCalledWith('T1', { is_completed: 1 })
    h.sysmgr.mockReturnValue(true)
    w.vm.openTaskEdit(entries[2])
    w.vm.taskEdit.description = 'Changed'
    await w.vm.saveTask()
    expect(h.tl.updateTask).toHaveBeenLastCalledWith('T1', { is_completed: 0, description: 'Changed', date: '2026-03-05T10:00', assigned_to: 'a@x.com' })
  })
  it('ticking a task off sends just the completion flag', () => {
    const w = mk({ types: ['task'] })
    w.vm.toggleTask(entries[2], true)
    w.vm.toggleTask(entries[2], false)
    expect(h.tl.updateTask.mock.calls).toEqual([['T1', { is_completed: 1 }], ['T1', { is_completed: 0 }]])
  })
  it('an event edit trims the summary and closes on success', async () => {
    const w = mk({ types: ['event'] })
    w.vm.openEventEdit(entries[3])
    expect(w.vm.eventEdit).toMatchObject({ id: 'E1', category: 'Meeting', date: '2026-03-06T09:30', summary: 'Sync' })
    w.vm.eventEdit.summary = '  Sync 2  '
    await w.vm.saveEvent()
    expect(h.tl.updateEvent).toHaveBeenCalledWith('E1', expect.objectContaining({ summary: 'Sync 2' }))
    expect(w.vm.showEventEdit).toBe(false)
  })
  it('date helpers', () => {
    const { inputDate, display, formatDate } = mk().vm
    expect(inputDate('2026-03-05 10:00:00')).toBe('2026-03-05T10:00')
    expect(inputDate(null)).toBe('')
    expect(display(null)).toBe('-')
    expect(display('')).toBe('-')
    expect(display(0)).toBe('0')
    expect(formatDate('')).toBe('')
    expect(formatDate('2026-03-05', true)).toMatch(/2026|3|5/)
  })
})

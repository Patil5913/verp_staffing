import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, reactive } from 'vue'

const h = vi.hoisted(() => ({ made: {} }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (opts) => {
    const r = reactive({ resource: { data: null, reload: vi.fn(), submit: vi.fn(async () => 'ok') }, isLoading: false, opts })
    h.made[opts.url.split('.').pop()] = r
    return r
  },
}))
import { useTimeline } from '@/composables/detail/useTimeline'

let t
beforeEach(() => { h.made = {}; t = useTimeline(ref('Lead'), ref('L1')) })

describe('useTimeline', () => {
  it('loads the timeline for the doc', () => {
    expect(h.made.get_timeline.opts.auto).toBe(true)
    expect(h.made.get_timeline.opts.makeParams()).toEqual({ doctype: 'Lead', name: 'L1' })
  })
  it('entries default to empty', () => {
    expect(t.entries.value).toEqual([])
    h.made.get_timeline.resource.data = { entries: [{ a: 1 }] }
    expect(t.entries.value).toEqual([{ a: 1 }])
  })
  it('addNote trims and ignores blanks', () => {
    t.addNote('   ')
    t.addNote(null)
    expect(h.made.add_comment.resource.submit).not.toHaveBeenCalled()
    t.addNote('  hi ')
    expect(h.made.add_comment.resource.submit).toHaveBeenCalledWith({ doctype: 'Lead', name: 'L1', content: 'hi' })
  })
  it('createTask / createEvent send doc + payload', async () => {
    await t.createTask({ title: 'x' })
    expect(h.made.create_task.resource.submit).toHaveBeenCalledWith({ doctype: 'Lead', name: 'L1', title: 'x' })
    await t.createEvent({ title: 'y' })
    expect(h.made.create_event.resource.submit).toHaveBeenCalledWith({ doctype: 'Lead', name: 'L1', title: 'y' })
  })
  it('edit/delete helpers map to the right params', () => {
    t.updateNote('N1', 'text'); expect(h.made.update_note.resource.submit).toHaveBeenCalledWith({ note_id: 'N1', note: 'text' })
    t.deleteNote('N1'); expect(h.made.delete_note.resource.submit).toHaveBeenCalledWith({ note_id: 'N1' })
    t.updateTask('T1', { status: 'Done' }); expect(h.made.update_task.resource.submit).toHaveBeenCalledWith({ task_name: 'T1', status: 'Done' })
    t.updateEvent('E1', { a: 1 }); expect(h.made.update_event.resource.submit).toHaveBeenCalledWith({ event_name: 'E1', a: 1 })
    t.deleteActivity('CRM Task', 'T1'); expect(h.made.delete_activity.resource.submit).toHaveBeenCalledWith({ doctype: 'CRM Task', name: 'T1' })
  })
  it('every mutation reloads the timeline on success', () => {
    for (const k of ['add_comment', 'create_task', 'create_event', 'update_note', 'delete_note', 'update_task', 'update_event', 'delete_activity']) {
      h.made[k].opts.onSuccess()
    }
    expect(h.made.get_timeline.resource.reload).toHaveBeenCalledTimes(8)
  })
  it('changing reflects any in-flight edit', () => {
    expect(t.changing.value).toBe(false)
    h.made.update_task.isLoading = true
    expect(t.changing.value).toBe(true)
  })
})

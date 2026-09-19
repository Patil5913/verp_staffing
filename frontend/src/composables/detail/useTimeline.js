import { computed } from 'vue'
import { useResource } from '@/composables/list/useResource'

export function useTimeline(doctype, name) {
  const timeline = useResource({
    url: 'verp_staffing.utils.detail_view.get_timeline',
    makeParams: () => ({ doctype: doctype.value, name: name.value }),
    auto: true,
  })

  const entries = computed(() => timeline.resource.data?.entries || [])

  const add = useResource({
    url: 'verp_staffing.utils.detail_view.add_comment',
    onSuccess: () => timeline.resource.reload(),
  })

  function addNote(content) {
    const trimmed = (content || '').trim()
    if (!trimmed) return
    add.resource.submit({ doctype: doctype.value, name: name.value, content: trimmed })
  }

  const taskCreate = useResource({
    url: 'verp_staffing.utils.detail_view.create_task',
    onSuccess: () => timeline.resource.reload(),
  })

  function createTask(payload) {
    return taskCreate.resource.submit({ doctype: doctype.value, name: name.value, ...payload })
  }

  const eventCreate = useResource({
    url: 'verp_staffing.utils.detail_view.create_event',
    onSuccess: () => timeline.resource.reload(),
  })

  function createEvent(payload) {
    return eventCreate.resource.submit({ doctype: doctype.value, name: name.value, ...payload })
  }

  // Edit / complete / delete an existing note, task or event. The server
  // (crm/api/notes.py, activities.py) decides who may — these just call it.
  const change = (url) => useResource({ url, onSuccess: () => timeline.resource.reload() })
  const noteUpdate = change('verp_staffing.crm.api.notes.update_note')
  const noteDelete = change('verp_staffing.crm.api.notes.delete_note')
  const taskUpdate = change('verp_staffing.crm.api.activities.update_task')
  const eventUpdate = change('verp_staffing.crm.api.activities.update_event')
  const activityDelete = change('verp_staffing.crm.api.activities.delete_activity')

  return {
    updateNote: (id, note) => noteUpdate.resource.submit({ note_id: id, note }),
    deleteNote: (id) => noteDelete.resource.submit({ note_id: id }),
    updateTask: (id, values) => taskUpdate.resource.submit({ task_name: id, ...values }),
    updateEvent: (id, values) => eventUpdate.resource.submit({ event_name: id, ...values }),
    deleteActivity: (activityDoctype, id) => activityDelete.resource.submit({ doctype: activityDoctype, name: id }),
    changing: computed(() => [noteUpdate, noteDelete, taskUpdate, eventUpdate, activityDelete].some((r) => r.isLoading)),
    timeline,
    entries,
    addNote,
    adding: computed(() => add.isLoading),
    createTask,
    creatingTask: computed(() => taskCreate.isLoading),
    createEvent,
    creatingEvent: computed(() => eventCreate.isLoading),
  }
}

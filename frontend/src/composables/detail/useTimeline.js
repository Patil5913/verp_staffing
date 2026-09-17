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

  return {
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

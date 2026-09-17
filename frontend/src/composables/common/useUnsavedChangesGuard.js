import { onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { confirmLeave } from '@/utils/common/confirmDialog'

// Reusable "your changes might get lost" guard for any form that holds
// unsaved edits in memory before an explicit Save — wire it up with a
// computed/ref tracking dirty state and it covers both in-app navigation
// (the router, via this app's own UnsavedChangesDialog) and hard navigation
// (tab close/refresh, where only the browser's native prompt is possible —
// no page can render its own UI at that point).
//
// `onSave`, if given, is an async () => boolean that performs the actual
// save — passing it adds a "Save" button to the dialog so the user isn't
// forced to choose only between leaving unsaved changes behind or
// cancelling the navigation.
export function useUnsavedChangesGuard(isDirty, onSave) {
  // Set right before a navigation that has already made the "unsaved
  // changes" moot (e.g. the record was just deleted) — skips one prompt
  // without weakening the guard for every other route change.
  const bypassed = ref(false)

  onBeforeRouteLeave(() => {
    if (bypassed.value) return true
    if (!isDirty.value) return true
    return confirmLeave({ onSave })
  })

  function onBeforeUnload(e) {
    if (bypassed.value || !isDirty.value) return
    e.preventDefault()
    e.returnValue = ''
  }

  onMounted(() => window.addEventListener('beforeunload', onBeforeUnload))
  onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload))

  // For actions that don't go through the router (e.g. a custom "back"
  // button that navigates programmatically) — call this first and only
  // proceed if it resolves true.
  function confirmDiscard() {
    if (!isDirty.value) return Promise.resolve(true)
    return confirmLeave({ onSave })
  }

  function bypassNext() {
    bypassed.value = true
  }

  return { confirmDiscard, bypassNext }
}

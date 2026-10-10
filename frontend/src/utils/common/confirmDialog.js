import { reactive } from 'vue'
import { playSound } from './sound'

// A single, app-wide "are you sure" dialog instance (see
// UnsavedChangesDialog.vue, mounted once in App.vue) instead of the
// browser's native window.confirm() - same role, this app's own look.
const state = reactive({
  open: false,
  title: '',
  message: '',
  html: '',
  leaveIcon: 'log-out',
  leaveLabel: 'Leave without saving',
  cancelLabel: 'Stay',
  // Optional async () => boolean - when given, the dialog offers a "Save"
  // button that runs it and only proceeds with navigation on success,
  // leaving the dialog open (so the user can still choose Leave/Stay) if
  // the save itself fails.
  onSave: null,
  saving: false,
  resolve: null,
})

// Resolves true to proceed with the navigation, false to stay.
export function confirmLeave({
  title = 'Unsaved changes',
  message = "You have unsaved changes. If you leave now, they'll be lost.",
  html = '',
  leaveIcon = 'log-out',
  leaveLabel = 'Leave without saving',
  cancelLabel = 'Stay',
  onSave = null,
} = {}) {
  return new Promise((resolve) => {
    state.title = title
    state.message = message
    state.html = html
    state.leaveIcon = leaveIcon
    state.leaveLabel = leaveLabel
    state.cancelLabel = cancelLabel
    state.onSave = onSave
    state.saving = false
    state.resolve = resolve
    state.open = true
    playSound('delete')
  })
}

export function useConfirmDialogState() {
  function settle(value) {
    state.open = false
    state.saving = false
    state.resolve?.(value)
    state.resolve = null
  }

  async function onSaveClick() {
    if (!state.onSave) return
    state.saving = true
    const ok = await state.onSave()
    if (ok) {
      settle(true)
    } else {
      // Save failed (already toasted by whatever it called) - leave the
      // dialog open so the user can retry Save or fall back to Leave/Stay.
      state.saving = false
    }
  }

  return { state, settle, onSaveClick }
}

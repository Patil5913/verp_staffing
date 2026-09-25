import { onMounted, onUnmounted } from 'vue'

// Ctrl/Cmd+S saves instead of triggering the browser's own "Save page"
// dialog - every page that can be saved (the generic detail controller,
// ERP Configuration, Hierarchy, ...) wires this the same way instead of
// each rolling its own keydown listener, so there's exactly one save
// shortcut active at a time, not several stacking on top of each other.
//
// `isDirty`/`onSave` are refs/functions, not values, so a page can pass its
// own live isDirty computed and onSave.
export function useSaveShortcut(isDirty, onSave) {
  function onKeydown(e) {
    const key = e.key?.toLowerCase()
    if (key !== 's') return
    if (!(e.ctrlKey || e.metaKey)) return
    // Exact Ctrl+S only - Ctrl+Shift+S (browsers' own "Save As") and any
    // other modifier combination must pass through untouched.
    if (e.shiftKey || e.altKey) return

    e.preventDefault()
    if (isDirty.value) onSave()
  }
  onMounted(() => window.addEventListener('keydown', onKeydown))
  onUnmounted(() => window.removeEventListener('keydown', onKeydown))
}

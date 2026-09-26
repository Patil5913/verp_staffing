import { reactive } from 'vue'

// Module-level on purpose: widths survive navigating between lists but are
// lost on a hard refresh (nothing is persisted).
const widths = reactive({})

export const columnWidths = widths

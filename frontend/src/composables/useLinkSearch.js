import { ref } from 'vue'
import { call, debounce } from 'frappe-ui'

// Backs a Link/Dynamic Link filter value's autocomplete. Reuses Frappe's own
// search_link (the same whitelisted method the desk's Link control calls)
// instead of a plain get_list, so results honor the doctype's search_fields/
// title field and standard user-permission filtering.
export function useLinkSearch(doctype) {
  const options = ref([])

  const run = debounce(async (txt) => {
    if (!doctype) return
    try {
      const results = await call('frappe.desk.search.search_link', {
        doctype,
        txt: txt || '',
      })
      options.value = (results || []).map((r) => ({
        value: r.value,
        label: r.description && r.description !== r.value ? `${r.value} (${r.description})` : (r.label || r.value),
      }))
    } catch {
      options.value = []
    }
  }, 300)

  function search(txt) {
    run(txt)
  }

  return { options, search }
}

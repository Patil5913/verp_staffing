import { reactive } from 'vue'
import { call } from 'frappe-ui'

// Human titles (Customer's name1, User's full_name, ...) for record IDs, so
// the UI can show "Name primary, ID secondary" wherever it has only an ID.
// One cache for the whole app: `titles[doctype][id]` is the title, or ''
// once the server has said there is none (the caller falls back to the ID).
const titles = reactive({})
const pending = {}
let flushTimer = null

function known(doctype, id) {
  return titles[doctype] && id in titles[doctype]
}

async function flush() {
  flushTimer = null
  const batch = { ...pending }
  for (const key of Object.keys(pending)) delete pending[key]

  await Promise.all(
    Object.entries(batch).map(async ([doctype, ids]) => {
      const wanted = [...ids]
      let found = {}
      try {
        found = (await call('verp_staffing.utils.record_labels.get_record_titles', { doctype, names: wanted })) || {}
      } catch {
        // Titles are decoration - a failed lookup just leaves the ID showing.
      }
      titles[doctype] ??= {}
      for (const id of wanted) titles[doctype][id] = found[id] || ''
    }),
  )
}

// Queue ids for lookup; lookups made in the same tick share one request per doctype.
export function requestTitles(doctype, ids) {
  if (!doctype) return
  for (const id of ids || []) {
    if (!id || typeof id !== 'string' || known(doctype, id)) continue
    ;(pending[doctype] ??= new Set()).add(id)
  }
  if (Object.keys(pending).length && !flushTimer) flushTimer = setTimeout(flush, 0)
}

// Reading is reactive: a template using it re-renders once the title arrives.
export function recordTitle(doctype, id) {
  return titles[doctype]?.[id] || ''
}

// Store a title already in hand (a doc's own title field), skipping a lookup.
export function setRecordTitle(doctype, id, title) {
  if (!doctype || !id) return
  titles[doctype] ??= {}
  titles[doctype][id] = title && title !== id ? title : ''
}

// Frappe's `depends_on`: an "eval:<js expression>" over `doc`, or a bare
// fieldname meaning "that field has a value". Shared by DocDetailView.vue
// (top-level fields) and ChildTableField.vue (a child table row's own
// dialog, which previously ignored depends_on entirely and always rendered
// every column - e.g. Lead Past Experience's End Month, meant to hide once
// "I am currently working in this role" is checked, per its own doctype
// JSON, but that JSON-declared depends_on was never evaluated client-side).
export function dependsOnPasses(field, doc) {
  const expr = field.depends_on
  if (!expr) return true
  try {
    if (expr.startsWith('eval:')) {
      const inList = (list, value) => Array.isArray(list) && list.includes(value)
      // eslint-disable-next-line no-new-func
      return Boolean(new Function('doc', 'in_list', `return (${expr.slice(5)})`)(doc, inList))
    }
    return Boolean(doc[expr])
  } catch {
    // A depends_on that fails to evaluate shows its field - hiding one on a
    // parse error would be worse.
    return true
  }
}

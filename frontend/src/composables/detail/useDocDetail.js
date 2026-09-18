import { computed, reactive, ref, watch } from 'vue'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'
import { validateFieldValue } from '@/utils/detail/fieldFormats'

// Generic single-record detail/form view on top of useResource: field +
// child-table metadata (backed by verp_staffing.utils.detail_view), current
// values, and a save() that round-trips through the same endpoint so the
// form always re-renders from the server's post-save state.
export function useDocDetail(doctype, name) {
  // The list view's "New" button routes here with name: 'new' (no real
  // docname yet) — treated the same as no name at all.
  const isNew = computed(() => !name.value || name.value === 'new')

  const meta = useResource({
    url: 'verp_staffing.utils.detail_view.get_doc_meta',
    makeParams: () => ({ doctype: doctype.value, name: isNew.value ? undefined : name.value }),
    auto: true,
  })

  // vue-router reuses this page's component instance when only the route's
  // :name param changes (e.g. navigating from one Lead straight to another
  // without an intervening list view), so `auto: true`'s one-shot fetch at
  // creation isn't enough — refetch whenever the record identity changes.
  watch([doctype, name], () => meta.resource.reload())

  const fields = computed(() => meta.resource.data?.fields || [])
  const tables = computed(() => meta.resource.data?.tables || [])
  const canWrite = computed(() => !!meta.resource.data?.perms?.write)
  const canDelete = computed(() => !!meta.resource.data?.perms?.delete)
  const titleField = computed(() => meta.resource.data?.title_field || 'name')

  const values = reactive({})
  // JSON snapshot of `values` right after a load/save — isDirty just diffs
  // against it, so it's the single source of truth both ChildTableField
  // (via values[fieldname]) and FieldControl write into.
  const snapshot = ref('')

  // Shared by the initial load and by a successful save — save_doc_fields
  // returns the same {values, tables, ...} shape get_doc_meta does, so
  // re-snapshotting directly off the save response keeps isDirty accurate
  // without waiting on a second reload() round-trip (which was the race:
  // clicking Save then immediately navigating away could hit the
  // unsaved-changes prompt before that reload had resolved).
  function applyData(data) {
    if (!data) return
    Object.keys(values).forEach((k) => delete values[k])
    Object.assign(values, data.values)
    // Table rows aren't part of `values` from the server (get_doc_meta's
    // `values` is scalar-fields-only) — seed them here too, since
    // ChildTableField reads/writes `values[table.fieldname]` the same
    // way FieldControl does for scalar fields.
    for (const table of data.tables || []) {
      values[table.fieldname] = table.rows || []
    }
    snapshot.value = JSON.stringify(values)
  }

  watch(() => meta.resource.data, applyData, { immediate: true })

  const isDirty = computed(() => JSON.stringify(values) !== snapshot.value)

  const save = useResource({
    url: 'verp_staffing.utils.detail_view.save_doc_fields',
    onSuccess(data) {
      meta.resource.setData(data)
      applyData(data)
      notify.success('Saved.')
    },
  })

  const triedSave = ref(false)

  function firstInvalidField() {
    return fields.value.find((f) => !f.read_only && validateFieldValue(f, values[f.fieldname]))
  }

  // Runs the same field-level validation FieldControl shows inline, so a
  // caller (the page's navbar Save button) can't submit invalid data just
  // because it doesn't render the fields itself.
  async function submit(changedValues) {
    triedSave.value = true
    if (!changedValues && firstInvalidField()) return false

    const result = await save.resource.submit({
      doctype: doctype.value,
      name: isNew.value ? undefined : name.value,
      values: changedValues ?? { ...values },
    })
    return !!result
  }

  return {
    meta,
    fields,
    tables,
    values,
    canWrite,
    canDelete,
    isDirty,
    isNew,
    titleField,
    save,
    submit,
    triedSave,
    refresh: () => meta.resource.reload(),
  }
}

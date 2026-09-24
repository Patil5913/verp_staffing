import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'
import { confirmSampleDataLinks } from '@/utils/detail/sampleDataGuard'
import { validateFieldValue } from '@/utils/detail/fieldFormats'

// Generic single-record detail/form view on top of useResource: field +
// child-table metadata (backed by verp_staffing.utils.detail_view), current
// values, and a save() that round-trips through the same endpoint so the
// form always re-renders from the server's post-save state.
export function useDocDetail(doctype, name) {
  const route = useRoute()
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
  // Submittable doctypes (Journal Entry, Payment Entry, invoices, ...):
  // docstatus 0 draft / 1 submitted / 2 cancelled. A doctype that isn't
  // submittable always reports 0, so nothing below needs a special case.
  const isSubmittable = computed(() => !!meta.resource.data?.is_submittable)
  const docstatus = computed(() => meta.resource.data?.docstatus ?? 0)
  // A page can freeze a record the user does have write permission on (the
  // desk forms' role rules, e.g. Employee being HR-only): it sets `locked`
  // and everything below that reads canWrite follows.
  const locked = ref(false)
  // A submitted/cancelled doc is frozen, whatever the user's write perm is.
  const canWrite = computed(() => !!meta.resource.data?.perms?.write && docstatus.value === 0 && !locked.value)
  const canSubmit = computed(() => isSubmittable.value && docstatus.value === 0 && !!meta.resource.data?.perms?.submit)
  const canCancel = computed(() => isSubmittable.value && docstatus.value === 1 && !!meta.resource.data?.perms?.cancel)
  const canDelete = computed(() => !!meta.resource.data?.perms?.delete)
  const titleField = computed(() => meta.resource.data?.title_field || 'name')

  const values = reactive({})
  // Read-only mirror of the doctype's hidden fields (see get_doc_meta) — for
  // page logic only, never rendered or saved.
  const hidden = reactive({})
  // Rows of hidden child tables (see get_doc_meta) — read by custom panels,
  // which write edits into `values[<table>]` to have them saved.
  const hiddenTables = reactive({})
  // JSON snapshot of `values` right after a load/save — isDirty just diffs
  // against it, so it's the single source of truth both ChildTableField
  // (via values[fieldname]) and FieldControl write into. Must start as
  // JSON.stringify(values) (i.e. '{}'), not '' — otherwise isDirty reads
  // true the instant the page mounts, before the doc has even loaded
  // ('{}' !== ''), so leaving the page in that window (e.g. clicking back
  // immediately) wrongly triggered the unsaved-changes prompt.
  const snapshot = ref(JSON.stringify(values))

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
    Object.keys(hidden).forEach((k) => delete hidden[k])
    Object.assign(hidden, data.hidden_values || {})
    Object.keys(hiddenTables).forEach((k) => delete hiddenTables[k])
    Object.assign(hiddenTables, data.hidden_tables || {})
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

  // "Create X for this customer" style links carry defaults in the query
  // string (/Sales Order/new?customer=CUST-1) — the desk's frappe.new_doc(
  // doctype, { customer }). Only a new doc takes them, only for fields this
  // doctype actually has, and they land after the snapshot so the form
  // starts dirty (there is something to save).
  watch(
    () => meta.resource.data,
    (data) => {
      if (!data || data.name) return
      const known = new Set((data.fields || []).map((f) => f.fieldname))
      for (const [key, value] of Object.entries(route.query)) {
        if (known.has(key)) values[key] = value
      }
    },
    { immediate: true },
  )

  const isDirty = computed(() => JSON.stringify(values) !== snapshot.value)

  const save = useResource({
    url: 'verp_staffing.utils.detail_view.save_doc_fields',
    onSuccess(data) {
      meta.resource.setData(data)
      applyData(data)
      notify.success('Saved.')
    },
  })

  // submit/cancel both answer with the same refreshed meta payload a save
  // does, so they re-snapshot through the same applyData.
  function transitionResource(url, notifyOnError = true) {
    return useResource({
      url,
      notifyOnError,
      onSuccess(data) {
        meta.resource.setData(data)
        applyData(data)
      },
    })
  }
  // Submit's own errors aren't auto-toasted (notifyOnError: false) — the
  // caller (useDetailPageController's onSubmit) checks for the one specific
  // "Email is required to send ..." case (Sales Order's pre-submit checks)
  // to offer a recovery dialog instead, and shows a normal toast itself for
  // anything else. Cancel has no such case, so it keeps the default
  // auto-toast behavior.
  const submitResource = transitionResource('verp_staffing.utils.detail_view.submit_doc', false)
  const cancelResource = transitionResource('verp_staffing.utils.detail_view.cancel_doc')
  async function runTransition(resource, message) {
    const result = await resource.resource.submit({ doctype: doctype.value, name: name.value })
    if (result) notify.success(message)
    return !!result
  }
  const cancelDoc = () => runTransition(cancelResource, 'Cancelled.')

  async function submitDoc() {
    // resource.submit() rethrows after onError, so a failed submit lands here as
    // an exception (not a falsy result) — catch it, or the error is swallowed
    // and nothing is shown.
    try {
      const result = await submitResource.resource.submit({ doctype: doctype.value, name: name.value })
      if (result) {
        notify.success('Submitted.')
        return { ok: true }
      }
      return { ok: false, error: submitResource.resource.error }
    } catch (error) {
      return { ok: false, error }
    }
  }

  const triedSave = ref(false)

  function firstInvalidField() {
    return fields.value.find((f) => {
      // Server-derived (fetch_from) fields are filled on save when empty.
      if (f.read_only || (f.fetch_from && !values[f.fieldname])) return false
      return validateFieldValue(f, values[f.fieldname])
    })
  }

  // Runs the same field-level validation FieldControl shows inline, so a
  // caller (the page's navbar Save button) can't submit invalid data just
  // because it doesn't render the fields itself.
  async function submit(changedValues) {
    triedSave.value = true
    if (!changedValues) {
      // Say which field blocked the save — it may be on another tab or a
      // grid row, where the inline error isn't visible and Save looked dead.
      const invalid = firstInvalidField()
      if (invalid) {
        notify.error(validateFieldValue(invalid, values[invalid.fieldname]))
        return false
      }
    }

    // Only the moment the link is first created (a new doc) — same rule as Desk.
    if (isNew.value && !(await confirmSampleDataLinks(doctype.value, { ...(changedValues ?? values) }))) return false

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
    hidden,
    hiddenTables,
    canWrite,
    locked,
    canDelete,
    isSubmittable,
    docstatus,
    canSubmit,
    canCancel,
    submitDoc,
    cancelDoc,
    transitioning: computed(() => submitResource.isLoading || cancelResource.isLoading),
    isDirty,
    isNew,
    titleField,
    save,
    submit,
    triedSave,
    refresh: () => meta.resource.reload(),
  }
}

import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useDocDetail } from '@/composables/detail/useDocDetail'
import { useResource } from '@/composables/list/useResource'
import { useUnsavedChangesGuard } from '@/composables/common/useUnsavedChangesGuard'
import { useSaveShortcut } from '@/composables/common/useSaveShortcut'
import { recordTitle as lookedUpTitle, requestTitles } from '@/composables/common/useRecordTitles'
import { notify } from '@/utils/common/notify'
import { isEmailMissingError, normalizeError } from '@/utils/common/errors'

// Shared shell behind every doctype's detail page - the generic
// DocDetailPage and any doctype-specific one (LeadDetailPage,
// UserDetailPage, ...): loads the record, tracks dirty/save/delete, and
// wires the unsaved-changes guard. A doctype-specific page only adds its own
// tabs/fields on top of this.
//
// `extraIsDirty`/`extraSave` let a page fold a second, separately-saved form
// (e.g. Lead's "Lead Detail Form" profile) into the same Save button and
// the same unsaved-changes guard, without this composable knowing anything
// about that doctype.
export function useDetailPageController(doctype, name, options = {}) {
  const router = useRouter()
  const extraIsDirty = options.extraIsDirty ?? computed(() => false)
  const extraSave = options.extraSave ?? (async () => true)

  const detail = useDocDetail(doctype, name)

  const recordTitle = computed(() => {
    if (detail.isNew.value) return `New ${doctype.value}`
    const titleField = detail.titleField.value
    const own = titleField !== 'name' && detail.values[titleField]
    if (own) {
      // A title field that links to another record (Resume, Training, ... use `customer`)
      // holds that record's ID: show its name instead.
      const df = detail.fields.value.find((f) => f.fieldname === titleField)
      if (df?.fieldtype === 'Link' && df.options) {
        requestTitles(df.options, [own])
        return lookedUpTitle(df.options, own) || own
      }
      return own
    }
    // No title field on the doctype (User's full_name, ...): ask the server for one.
    requestTitles(doctype.value, [name.value])
    return lookedUpTitle(doctype.value, name.value) || name.value
  })

  const isDirty = computed(() => detail.isDirty.value || extraIsDirty.value)

  async function saveAll() {
    let ok = true
    if (detail.isDirty.value) ok = (await detail.submit()) && ok
    if (extraIsDirty.value) ok = (await extraSave()) && ok
    return ok
  }

  // Only bypassNext() is used directly here - the router-level leave/unload
  // prompts from this guard already cover the back button (it navigates via
  // router.push below), so a second manual confirmDiscard() check there
  // would just double the prompt.
  const { bypassNext } = useUnsavedChangesGuard(isDirty, saveAll)

  async function onSave() {
    // save's onSuccess already re-snapshots `values` from the response, so
    // isDirty clears synchronously - no separate detail.refresh() round-trip
    // needed (that gap was letting a just-saved page still look "dirty" for
    // a moment, triggering the leave-guard even right after a save).
    //
    // Goes through saveAll() (main doc + the extra form, e.g. a Lead's
    // Candidate Profile), not detail.submit() alone - this is the button/
    // Ctrl+S save path, and previously only saveAll() (used solely by the
    // unsaved-changes-guard's own "Save and leave" option) saved the extra
    // form at all, so a normal Save silently only saved the main doc.
    const wasNew = detail.isNew.value
    const ok = await saveAll()
    if (ok && wasNew) {
      // The doc now has a real name (save's onSuccess already re-snapshotted
      // detail.meta off the insert response) - swap the URL in place so a
      // refresh, or the delete/back flow, lands on its real docname instead
      // of re-triggering another insert. A plain path (not a named route)
      // so this lands correctly whether the doctype has its own detail page
      // route or falls through to the generic one.
      const newName = detail.meta.resource.data?.name
      bypassNext()
      router.replace(`/${encodeURIComponent(doctype.value)}/${encodeURIComponent(newName)}`)
    }
    return ok
  }

  // Submit/Cancel (submittable doctypes only): submit first saves any
  // pending edits, since Frappe submits what's on the server, not what's in
  // the form. Cancel asks first - it's the one irreversible transition.
  const showCancelDialog = ref(false)

  // Returns { emailMissing: boolean } so the caller (ConfigDetailPage) can
  // offer to collect an email and retry - see useDocDetail.js's submitDoc
  // for why submit's own errors aren't auto-toasted like everything else.
  async function onSubmit() {
    if (detail.isDirty.value && !(await detail.submit())) return { emailMissing: false }
    // Fields a doctype needs before it can be submitted (options.requiredOnSubmit) -
    // flag them inline and name them, instead of a bare server error after the fact.
    const missing = (options.requiredOnSubmit || []).filter((fn) => !detail.values[fn])
    if (missing.length) {
      detail.triedSave.value = true
      const labels = missing.map((fn) => detail.fields.value.find((f) => f.fieldname === fn)?.label || fn)
      notify.error(`Fill in ${labels.join(' and ')} before submitting.`)
      return { emailMissing: false }
    }
    const result = await detail.submitDoc()
    if (result.ok) return { emailMissing: false }
    if (isEmailMissingError(result.error)) return { emailMissing: true }
    if (result.missing?.length) {
      const labels = result.missing.map((f) => f.label).join(', ')
      notify.error(`Fill in ${labels} before submitting - they're marked on the form.`)
      return { emailMissing: false }
    }
    notify.error(normalizeError(result.error).message)
    return { emailMissing: false }
  }

  async function onCancelDoc() {
    if (await detail.cancelDoc()) showCancelDialog.value = false
  }

  function goBack() {
    router.push({ name: 'DocList', params: { doctype: doctype.value } })
  }

  const showDeleteDialog = ref(false)

  const deleteResource = useResource({
    url: 'verp_staffing.utils.list_view.delete_docs',
  })
  const deleting = computed(() => deleteResource.isLoading)

  async function onDelete() {
    const result = await deleteResource.resource.submit({ doctype: doctype.value, names: [name.value] })
    if (!result) return // request itself failed; useResource already toasted it

    if (result.failed.length) {
      notify.error(result.failed[0].error)
      return
    }

    showDeleteDialog.value = false
    notify.success('Deleted.')
    // Not goBack() - the record is already gone, so there's nothing left to
    // discard and no reason to ask.
    bypassNext()
    router.push({ name: 'DocList', params: { doctype: doctype.value } })
  }

  useSaveShortcut(isDirty, onSave)

  return {
    detail,
    recordTitle,
    isDirty,
    onSave,
    goBack,
    showDeleteDialog,
    deleting,
    onDelete,
    onSubmit,
    onCancelDoc,
    showCancelDialog,
    bypassNext,
  }
}

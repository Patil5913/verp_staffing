import { computed, reactive, ref, watch } from 'vue'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'

// A Lead / Opportunity / Customer's linked "Lead Detail Form" record
// (candidate-facing fields: education, experience, visa status, etc.),
// scoped to whatever fields the Administrator has exposed for that
// reference doctype — see verp_staffing.utils.detail_view. Mirrors
// useDocDetail's shape so LeadProfilePanel.vue can reuse FieldControl/
// ChildTableField the same way DocDetailView.vue does. Shared by Lead's own
// Candidate Profile tab and the equivalent tab on Opportunity/Customer
// (their doctypes carry the same `lead_details` link, previously only
// rendered inline via a now-dropped desk HTML field with no Vue equivalent).
export function useLeadDetailForm(referenceDoctype, referenceName) {
  const detail = useResource({
    url: 'verp_staffing.utils.detail_view.get_reference_detail_view',
    makeParams: () => ({ reference_doctype: referenceDoctype, reference_name: referenceName.value }),
    auto: true,
  })

  const exists = computed(() => !!detail.resource.data?.exists)
  const fields = computed(() => detail.resource.data?.fields || [])
  const tables = computed(() => detail.resource.data?.tables || [])
  const canWrite = computed(() => !!detail.resource.data?.perms?.write)
  const docname = computed(() => detail.resource.data?.docname || '')

  const values = reactive({})
  // Matches values' initial empty-object shape, not ''. Left as '' before,
  // any customer/lead/opportunity with no linked Lead Detail Form at all
  // (exists: false, so applyData's early return below never touches this)
  // permanently read as dirty — JSON.stringify({}) ('{}') is never ''. The
  // panel then renders nothing to edit, but the main page's Save button
  // still folds this "dirty" form into its save and unconditionally called
  // submit(), which the server rejects with "No Lead Detail Form is linked
  // to this {doctype}." on every single save of the page, whether or not
  // the user touched the Candidate Profile tab at all.
  const snapshot = ref(JSON.stringify(values))

  // Shared by the initial load and by a successful save — save_lead_detail_view
  // returns the same {values, tables, ...} shape get_lead_detail_view does,
  // so re-snapshotting off of either keeps isDirty accurate without a
  // separate reload() round-trip after every save.
  function applyData(data) {
    if (!data?.exists) {
      Object.keys(values).forEach((k) => delete values[k])
      snapshot.value = JSON.stringify(values)
      return
    }
    Object.keys(values).forEach((k) => delete values[k])
    Object.assign(values, data.values)
    for (const table of data.tables || []) {
      values[table.fieldname] = table.rows || []
    }
    snapshot.value = JSON.stringify(values)
  }

  watch(() => detail.resource.data, applyData, { immediate: true })

  const isDirty = computed(() => JSON.stringify(values) !== snapshot.value)

  // lead_detail_form.js's update_parent_skills: the skills summary is the
  // manually typed skills plus every experience row's skills, de-duplicated.
  // Only reacts to edits made since the form loaded, so opening a profile
  // never marks it changed.
  const splitSkills = (text) => String(text || '').split(',').map((s) => s.trim()).filter(Boolean)
  watch(
    () => [values.additional_skills, JSON.stringify((values.past_experience_table || []).map((r) => r.skills))],
    () => {
      if (!isDirty.value) return
      const merged = [...new Set([...splitSkills(values.additional_skills), ...(values.past_experience_table || []).flatMap((r) => splitSkills(r.skills))])].join(', ')
      if (merged !== (values.additional_skills || '')) values.additional_skills = merged
    },
  )

  const save = useResource({
    url: 'verp_staffing.utils.detail_view.save_reference_detail_view',
    onSuccess(data) {
      detail.resource.setData(data)
      applyData(data)
      notify.success('Lead details saved.')
    },
  })

  async function submit() {
    // Nothing to save when there's no linked Lead Detail Form to begin with
    // (the panel renders no fields either way) — belt-and-suspenders
    // alongside the isDirty fix above, so a caller that submits regardless
    // of isDirty still can't hit the server's "No Lead Detail Form is
    // linked" throw.
    if (!exists.value) return true
    const result = await save.resource.submit({
      reference_doctype: referenceDoctype,
      reference_name: referenceName.value,
      values: { ...values },
    })
    return !!result
  }

  // Share of the fields this user can fill that already have a value (a
  // table counts once it has a row) — a nudge for the profile, not a
  // validation.
  const completeness = computed(() => {
    const inputs = fields.value.filter((f) => !f.read_only && f.fieldtype !== 'Check')
    const total = inputs.length + tables.value.length
    if (!total) return 100
    const filled =
      inputs.filter((f) => String(values[f.fieldname] ?? '').trim()).length +
      tables.value.filter((t) => (values[t.fieldname] || []).length).length
    return Math.round((filled / total) * 100)
  })

  return { detail, exists, docname, fields, tables, values, canWrite, isDirty, completeness, save, submit }
}

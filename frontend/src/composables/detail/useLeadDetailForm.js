import { computed, reactive, ref, watch } from 'vue'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'

// The Lead's linked "Lead Detail Form" record (candidate-facing fields:
// education, experience, visa status, etc.), scoped to whatever fields the
// Administrator has exposed for Lead — see verp_staffing.utils.detail_view.
// Mirrors useDocDetail's shape so LeadProfilePanel.vue can reuse
// FieldControl/ChildTableField the same way DocDetailView.vue does.
export function useLeadDetailForm(leadName) {
  const detail = useResource({
    url: 'verp_staffing.utils.detail_view.get_lead_detail_view',
    makeParams: () => ({ lead_name: leadName.value }),
    auto: true,
  })

  const exists = computed(() => !!detail.resource.data?.exists)
  const fields = computed(() => detail.resource.data?.fields || [])
  const tables = computed(() => detail.resource.data?.tables || [])
  const canWrite = computed(() => !!detail.resource.data?.perms?.write)
  const docname = computed(() => detail.resource.data?.docname || '')

  const values = reactive({})
  const snapshot = ref('')

  // Shared by the initial load and by a successful save — save_lead_detail_view
  // returns the same {values, tables, ...} shape get_lead_detail_view does,
  // so re-snapshotting off of either keeps isDirty accurate without a
  // separate reload() round-trip after every save.
  function applyData(data) {
    if (!data?.exists) return
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
    url: 'verp_staffing.utils.detail_view.save_lead_detail_view',
    onSuccess(data) {
      detail.resource.setData(data)
      applyData(data)
      notify.success('Lead details saved.')
    },
  })

  async function submit() {
    const result = await save.resource.submit({ lead_name: leadName.value, values: { ...values } })
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

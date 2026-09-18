<template>
  <DetailPageLayout title="ERP Configuration" :tabs="tabs" v-model:active-tab="activeTab" @back="goBack">
    <template #actions>
      <RecordActionBar show-save save-dirty :save-loading="saving" @save="onSave" />
    </template>

    <template #tab-general>
      <div class="h-full overflow-y-auto px-6 py-4">
        <div class="flex flex-col gap-6">
          <div class="flex flex-col gap-3 rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
            <h3 class="text-p-base font-medium text-app-text">Immediate Triggerer Configuration</h3>
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FieldControl v-for="f in fieldsFor(['send_agreement_immediatly_after_sales_order_creation','send_candidate_form_immediatly_after_sales_order_creation','expiry_hours_of_agreement'])" :key="f.fieldname" :field="f" :disabled="!canWrite" :model-value="values[f.fieldname]" show-errors @update:model-value="(v) => (values[f.fieldname] = v)" />
            </div>
          </div>

          <div class="flex flex-col gap-3 rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
            <h3 class="text-p-base font-medium text-app-text">Interview &amp; Company Configuration</h3>
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FieldControl v-for="f in fieldsFor(['default_interview_status','default_company'])" :key="f.fieldname" :field="f" :disabled="!canWrite" :model-value="values[f.fieldname]" show-errors @update:model-value="(v) => (values[f.fieldname] = v)" />
            </div>
          </div>

          <div class="flex flex-col gap-3 rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
            <div class="flex items-center justify-between">
              <h3 class="text-p-base font-medium text-app-text">Permission Request Configuration</h3>
            </div>
            <ChildTableField :table="permissionTable" :rows="tableRows" :disabled="!canWrite" @update:rows="(rows) => (tableRows = rows)" />
          </div>

          <div class="flex flex-col gap-3 rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
            <h3 class="text-p-base font-medium text-app-text">Email Usage Configuration</h3>
            <EmailConfiguratorGrid :disabled="!canWrite" v-model="emailConfigRows" />
          </div>

          <div class="flex flex-col gap-3 rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
            <h3 class="text-p-base font-medium text-app-text">Social Links Configuration</h3>
            <p class="text-p-sm text-app-text-muted">Add social links of the company which display in emails.</p>
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FieldControl v-for="f in fieldsFor(['linkedin','facebook','twitter_x','youtube'])" :key="f.fieldname" :field="f" :disabled="!canWrite" :model-value="values[f.fieldname]" @update:model-value="(v) => (values[f.fieldname] = v)" />
            </div>
          </div>

          <div class="flex flex-col gap-3 rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
            <h3 class="text-p-base font-medium text-app-text">Sample Data</h3>
            <SampleDataPanel @removed="loadHiddenFields" />
          </div>
        </div>
      </div>
    </template>

    <template #tab-candidate-form>
      <div class="h-full overflow-y-auto px-6 py-4">
        <FieldSelectorWidget
          title="Candidate Form Fields — per Service"
          description="Controls <strong>which fields appear</strong> on the candidate's application form for a specific service. Each service shows only its relevant fields."
          impact="Affects: Candidate application form"
          selector-label="service"
          is-candidate-form
          :items-list="services"
          :field-sections="fieldSections"
          :disabled="!canWrite"
          v-model="candidateFormConfig"
        />
      </div>
    </template>

    <template #tab-department-display>
      <div class="h-full overflow-y-auto px-6 py-4">
        <FieldSelectorWidget
          title="Department Display Fields"
          description="Controls <strong>which fields are visible</strong> when viewing a candidate's details form under a specific context. Sensitive data can be hidden where it isn't needed."
          impact="Affects: Candidate details form visibility"
          selector-label="context"
          :items-list="servicesPlusForDisplay"
          :field-sections="fieldSections"
          :disabled="!canWrite"
          v-model="deptDisplayConfig"
        />
      </div>
    </template>

    <template #tab-department-access>
      <div class="h-full overflow-y-auto px-6 py-4">
        <FieldSelectorWidget
          title="Department Access Fields"
          description="Controls <strong>which fields can be edited</strong> on a candidate's profile in a specific context — all other fields become read-only."
          impact="Affects: Edit authority on candidate details form"
          selector-label="context"
          :items-list="servicesPlus"
          :field-sections="fieldSections"
          :disabled="!canWrite"
          v-model="deptAccessConfig"
        />
      </div>
    </template>

    <template #tab-website>
      <div class="h-full overflow-y-auto px-6 py-4">
        <WebsiteSystemSettingsPanel
          :field-groups="systemSettings.fieldGroups.value"
          :values="systemSettings.values.value"
          :disabled="!canWrite"
          @stage="systemSettings.stage"
        />
      </div>
    </template>
  </DetailPageLayout>
</template>

<script setup>
// ERP Configuration's own page — a Single doctype, so it's built on
// get_settings_meta/frappe.client.set_value (the same generic single-
// doctype primitives SettingsFormPage.vue already uses) rather than
// useDocDetail, which only works for non-Single doctypes. Its 4 hidden
// JSON storage fields (table_tpxt, candidate_details_form_fields,
// department_display_form_fields, department_access_form_fields,
// email_configuration_detail) follow the same fetch-via-frappe.client.get /
// bulk-save-via-frappe.client.set_value pattern used for Hierarchy's and
// Pdf Agreement Template's hidden fields. No delete/create flow — a
// Single always exists — so this page skips the usual
// isNew/delete/unsaved-changes-guard machinery entirely.
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import FieldControl from '@/components/detail/FieldControl.vue'
import ChildTableField from '@/components/detail/ChildTableField.vue'
import EmailConfiguratorGrid from '@/components/detail/erp/EmailConfiguratorGrid.vue'
import FieldSelectorWidget from '@/components/detail/erp/FieldSelectorWidget.vue'
import WebsiteSystemSettingsPanel from '@/components/detail/erp/WebsiteSystemSettingsPanel.vue'
import SampleDataPanel from '@/components/detail/erp/SampleDataPanel.vue'
import { useResource } from '@/composables/list/useResource'
import { useSystemSettingsPanel } from '@/composables/detail/useSystemSettingsPanel'
import { notify } from '@/utils/common/notify'

const router = useRouter()

const tabs = [
  { key: 'general', label: 'General' },
  { key: 'candidate-form', label: 'Candidate Form Fields' },
  { key: 'department-display', label: 'Department Display Fields' },
  { key: 'department-access', label: 'Department Access Fields' },
  { key: 'website', label: 'Website Settings' },
]
const activeTab = ref('general')

function goBack() {
  router.push('/')
}

// ── Basic scalar fields (get_settings_meta) ────────────────────────────────
const EXCLUDED_FIELDNAMES = ['sample_data_log', 'is_sample_data_removed']

const metaResource = useResource({
  url: 'verp_staffing.utils.list_view.get_settings_meta',
  makeParams: () => ({ doctype: 'ERP Configuration' }),
  auto: true,
})
const allFields = computed(() => (metaResource.resource.data?.fields || []).filter((f) => !EXCLUDED_FIELDNAMES.includes(f.fieldname)))
const canWrite = computed(() => !!metaResource.resource.data?.perms?.write)

const values = reactive({})
function seedValues() {
  const data = metaResource.resource.data?.values || {}
  Object.keys(values).forEach((k) => delete values[k])
  Object.assign(values, data)
}
function fieldsFor(fieldnames) {
  return allFields.value.filter((f) => fieldnames.includes(f.fieldname))
}

// ── Hidden JSON fields + the table, fetched once via frappe.client.get
// (same as Hierarchy/Pdf Agreement Template's hidden-field pattern) ────────
const permissionTable = {
  fieldname: 'table_tpxt',
  label: 'Permission Request Configuration',
  columns: [
    { fieldname: 'department', label: 'Department', fieldtype: 'Link', options: 'Department', reqd: true },
    { fieldname: 'role', label: 'Role', fieldtype: 'Link', options: 'Role', reqd: true },
  ],
}
const tableRows = ref([])
const emailConfigRows = ref([])
const candidateFormConfig = ref({})
const deptDisplayConfig = ref({})
const deptAccessConfig = ref({})

const singleResource = useResource({ url: 'frappe.client.get', notifyOnError: false })
function parseJSON(raw, fallback) {
  if (!raw) return fallback
  try {
    return JSON.parse(raw)
  } catch {
    return fallback
  }
}
async function loadHiddenFields() {
  const doc = await singleResource.resource.submit({ doctype: 'ERP Configuration' })
  if (!doc) return
  tableRows.value = doc.table_tpxt || []
  emailConfigRows.value = parseJSON(doc.email_configuration_detail, [])
  candidateFormConfig.value = parseJSON(doc.candidate_details_form_fields, {})
  deptDisplayConfig.value = parseJSON(doc.department_display_form_fields, {})
  deptAccessConfig.value = parseJSON(doc.department_access_form_fields, {})
}

watch(
  () => metaResource.resource.data,
  (data) => {
    if (data) seedValues()
  },
  { immediate: true },
)
loadHiddenFields()

// ── Services / field-picker item lists (get_services + Lead Detail Form's
// own field sections, both existing/new generic endpoints) ─────────────────
const servicesResource = useResource({
  url: 'verp_staffing.settings.doctype.erp_configuration.erp_configuration.get_services',
  auto: true,
})
const services = computed(() => servicesResource.resource.data || [])
const servicesPlus = computed(() => [...services.value, 'Lead', 'Customer'])
const servicesPlusForDisplay = computed(() => [...services.value, 'Customer', 'Opportunity'])

const LEAD_DETAIL_FORM_EXCLUDE_FIELDS = [
  'name', 'owner', 'creation', 'modified', 'modified_by', 'docstatus', 'idx',
  'form_token', 'signature_method', 'signature', 'agreement_html', 'authentication_html',
  'signature_image', 'signature_custom_html', 'files_custom_html', 'reference_table',
  'my_electronic_signature_has_same_effect_as_handwritten',
  'i_consent_to_receive_sign_and_store_documents_electronically',
  'i_confirm_my_identity_and_signing_this_document_intentionally',
]
const sectionsResource = useResource({
  url: 'verp_staffing.utils.detail_view.get_doctype_field_sections',
  makeParams: () => ({ doctype: 'Lead Detail Form', exclude_fieldnames: LEAD_DETAIL_FORM_EXCLUDE_FIELDS }),
  auto: true,
})
const fieldSections = computed(() => sectionsResource.resource.data || [])

// ── Website Settings tab's System Settings panel ────────────────────────
const systemSettings = useSystemSettingsPanel()

// ── Save ────────────────────────────────────────────────────────────────
const saving = ref(false)
const saveResource = useResource({ url: 'frappe.client.set_value' })

async function onSave() {
  saving.value = true
  try {
    const flushed = await systemSettings.flush()
    if (!flushed) return

    const payload = {
      ...values,
      table_tpxt: tableRows.value,
      candidate_details_form_fields: JSON.stringify(candidateFormConfig.value),
      department_display_form_fields: JSON.stringify(deptDisplayConfig.value),
      department_access_form_fields: JSON.stringify(deptAccessConfig.value),
      email_configuration_detail: JSON.stringify(emailConfigRows.value),
    }

    const result = await saveResource.resource.submit({
      doctype: 'ERP Configuration',
      name: 'ERP Configuration',
      fieldname: payload,
    })
    if (!result) return

    seedValues()
    notify.success('Saved.')
  } finally {
    saving.value = false
  }
}
</script>

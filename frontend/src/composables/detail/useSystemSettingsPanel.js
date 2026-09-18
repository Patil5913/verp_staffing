import { computed, ref } from 'vue'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'

// Same 15 fields erp_configuration.py's MANAGED_SYSTEM_SETTINGS_FIELDS
// allows writing to — hardcoded here (rather than fetched) since these are
// standard, stable Frappe core fields; only their current values (and the
// timezone list for time_zone's options) come from the server.
const FIELD_DEFS = {
  country: { label: 'Country', fieldtype: 'Link', options: 'Country' },
  language: { label: 'Language', fieldtype: 'Link', options: 'Language' },
  time_zone: { label: 'Time Zone', fieldtype: 'Select', options: '' },
  currency: { label: 'Currency', fieldtype: 'Link', options: 'Currency' },
  date_format: {
    label: 'Date Format',
    fieldtype: 'Select',
    options: 'yyyy-mm-dd\ndd-mm-yyyy\ndd/mm/yyyy\ndd.mm.yyyy\nmm/dd/yyyy\nmm-dd-yyyy',
  },
  time_format: { label: 'Time Format', fieldtype: 'Select', options: 'HH:mm:ss\nHH:mm' },
  number_format: {
    label: 'Number Format',
    fieldtype: 'Select',
    options:
      "#,###.##\n#.###,##\n# ###.##\n# ###,##\n#'###.##\n#, ###.##\n#,##,###.##\n#,###.###\n#.###\n#,###",
  },
  session_expiry: { label: 'Session Expiry (idle timeout)', fieldtype: 'Data' },
  deny_multiple_sessions: { label: 'Allow only one session per user', fieldtype: 'Check' },
  reset_password_link_expiry_duration: { label: 'Reset Password Link Expiry Duration', fieldtype: 'Duration' },
  password_reset_limit: { label: 'Password Reset Link Generation Limit', fieldtype: 'Int' },
  welcome_email_template: { label: 'Welcome Email Template', fieldtype: 'Link', options: 'Email Template' },
  reset_password_template: { label: 'Reset Password Template', fieldtype: 'Link', options: 'Email Template' },
  max_file_size: { label: 'Max File Size (MB)', fieldtype: 'Int' },
  allowed_file_extensions: { label: 'Allowed File Extensions', fieldtype: 'Small Text' },
}
const FIELD_GROUPS = [
  { label: '', fields: ['country', 'language', 'time_zone', 'currency'] },
  { label: 'Date and Number Format', fields: ['date_format', 'time_format', 'number_format'] },
  {
    label: 'Session, Password & Email Limits',
    fields: [
      'session_expiry',
      'deny_multiple_sessions',
      'reset_password_link_expiry_duration',
      'password_reset_limit',
      'welcome_email_template',
      'reset_password_template',
    ],
  },
  { label: 'Files', fields: ['max_file_size', 'allowed_file_extensions'] },
]

// Backs ERP Configuration's Website Settings tab: a curated System
// Settings quick-edit panel, staged locally and flushed as one batch on
// the outer form's save — mirrors the old desk erp_configuration.js's
// stage_system_settings_change()/flush_system_settings_changes(). Owned by
// the PAGE (not the tab's presentational component), since
// DetailPageLayout only keeps the active tab's content mounted — a
// component-local pending-changes ref would be lost switching tabs before
// Save is clicked.
export function useSystemSettingsPanel() {
  const values = ref({})
  const timezones = ref([])
  let pending = {}

  const fieldGroups = computed(() =>
    FIELD_GROUPS.map((group) => ({
      label: group.label,
      fields: group.fields.map((fieldname) => {
        const def = FIELD_DEFS[fieldname]
        return {
          fieldname,
          label: def.label,
          fieldtype: def.fieldtype,
          options: fieldname === 'time_zone' ? timezones.value.join('\n') : def.options,
        }
      }),
    })),
  )

  const loadResource = useResource({
    url: 'verp_staffing.settings.doctype.erp_configuration.erp_configuration.get_system_settings_fields',
  })
  const updateResource = useResource({
    url: 'verp_staffing.settings.doctype.erp_configuration.erp_configuration.update_system_settings_fields',
  })

  async function load() {
    const data = await loadResource.resource.fetch()
    if (!data) return
    values.value = data.values || {}
    timezones.value = data.timezones || []
  }
  load()

  function stage(fieldname, value) {
    pending[fieldname] = value
    values.value = { ...values.value, [fieldname]: value }
  }

  async function flush() {
    if (!Object.keys(pending).length) return true
    const valuesToSave = pending
    pending = {}

    const result = await updateResource.resource.submit({ values: valuesToSave })
    if (!result) {
      Object.assign(pending, valuesToSave)
      return false
    }

    values.value = { ...values.value, ...(result.values || {}) }
    if ('language' in valuesToSave) {
      notify.success('Refreshing…')
      window.location.reload()
    }
    return true
  }

  return { values, fieldGroups, stage, flush }
}

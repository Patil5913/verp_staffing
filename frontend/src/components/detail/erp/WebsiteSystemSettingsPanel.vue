<template>
  <div class="flex h-full flex-col">
    <SectionPills :sections="SECTIONS" />
    <div class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-3 py-4 md:px-6">

    <SectionCard id="ws-identity" title="App Identity" subtitle="Name, logo and regional defaults shown across the app.">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FieldControl :field="APP_NAME_FIELD" :disabled="disabled" :model-value="appName" @update:model-value="onAppNameChange" />
        <FieldControl :field="APP_LOGO_FIELD" :disabled="disabled" :model-value="appLogo" @update:model-value="onLogoChange" />
        <FieldControl :field="field('country')" :disabled="disabled" :model-value="values.country" @update:model-value="(v) => emit('stage', 'country', v)" />
        <FieldControl :field="field('language')" :disabled="disabled" :model-value="values.language" @update:model-value="(v) => emit('stage', 'language', v)" />
        <FieldControl :field="field('currency')" :disabled="disabled" :model-value="values.currency" @update:model-value="(v) => emit('stage', 'currency', v)" />
        <div class="flex flex-col gap-1.5">
          <AppCombobox
            label="Time Zone"
            :disabled="disabled"
            :options="timezoneOptions"
            :model-value="values.time_zone || ''"
            @update:model-value="(v) => emit('stage', 'time_zone', v)"
          />
          <p v-if="zoneClock" class="flex items-center gap-1.5 text-p-xs text-app-text-muted">
            <span class="lucide-clock size-3.5" /> Current time in {{ values.time_zone }}: <strong class="text-app-text">{{ zoneClock }}</strong>
          </p>
        </div>
      </div>
    </SectionCard>

    <SectionCard id="ws-format" title="Date & Number Format" subtitle="Examples update as you change a format.">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div v-for="f in FORMATS" :key="f.name" class="flex flex-col gap-1.5">
          <AppCombobox
            :label="f.label"
            :disabled="disabled"
            :options="optionsOf(f.name)"
            :model-value="values[f.name] || ''"
            @update:model-value="(v) => emit('stage', f.name, v)"
          />
          <p v-if="f.example(values[f.name])" class="text-p-xs text-app-text-muted">
            Example: <strong class="text-app-text">{{ f.example(values[f.name]) }}</strong>
          </p>
        </div>
      </div>
    </SectionCard>

    <SectionCard id="ws-limits" title="Session, Password & Email Limits">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <AppDurationInput
          label="Session Expiry (idle timeout)"
          storage="hhmm"
          :units="['Minutes', 'Hours', 'Days']"
          :disabled="disabled"
          :model-value="values.session_expiry"
          @update:model-value="(v) => emit('stage', 'session_expiry', v)"
        />
        <AppDurationInput
          label="Reset Password Link Expiry"
          storage="seconds"
          :units="['Minutes', 'Hours', 'Days']"
          :disabled="disabled"
          :model-value="values.reset_password_link_expiry_duration"
          @update:model-value="(v) => emit('stage', 'reset_password_link_expiry_duration', v)"
        />
        <FieldControl :field="field('password_reset_limit')" :disabled="disabled" :model-value="values.password_reset_limit" @update:model-value="(v) => emit('stage', 'password_reset_limit', v)" />
        <div class="flex items-end pb-1.5">
          <AppSwitch
            label="Allow only one session per user"
            :disabled="disabled"
            :model-value="values.deny_multiple_sessions"
            @update:model-value="(v) => emit('stage', 'deny_multiple_sessions', v)"
          />
        </div>
        <FieldControl :field="field('welcome_email_template')" :disabled="disabled" :model-value="values.welcome_email_template" @update:model-value="(v) => emit('stage', 'welcome_email_template', v)" />
        <FieldControl :field="field('reset_password_template')" :disabled="disabled" :model-value="values.reset_password_template" @update:model-value="(v) => emit('stage', 'reset_password_template', v)" />
      </div>
    </SectionCard>

    <SectionCard id="ws-files" title="Files">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FieldControl :field="field('max_file_size')" :disabled="disabled" :model-value="values.max_file_size" @update:model-value="(v) => emit('stage', 'max_file_size', v)" />
      </div>
      <AppChipInput
        label="Allowed File Extensions"
        placeholder="Type an extension, press Enter"
        hint="Letters and numbers only, 1-6 characters, e.g. pdf, docx."
        :disabled="disabled"
        :validate="validateExtension"
        :normalize="normalizeExtension"
        :model-value="extensions"
        @update:model-value="(v) => emit('stage', 'allowed_file_extensions', v.join('\n'))"
      />
    </SectionCard>
    </div>
  </div>
</template>

<script setup>
// ERP Configuration's "Website Settings" tab. App Name/App Logo are Website
// Settings' own fields, saved immediately per-field here (same as the old
// render_website_app_settings()) - safe to keep self-contained since nothing
// is lost if this component remounts on a tab switch. Everything else is the
// System Settings quick-edit state owned by the page's useSystemSettingsPanel()
// (fieldGroups/values/stage) since that has pending, unsaved edits that must
// survive a tab switch. Stored formats are unchanged: durations are shown as
// value + unit but saved in the same HH:MM / seconds form as before.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { debounce } from 'frappe-ui'
import AppCombobox from '@/components/ui/AppCombobox.vue'
import AppChipInput from '@/components/ui/AppChipInput.vue'
import AppDurationInput from '@/components/ui/AppDurationInput.vue'
import AppSwitch from '@/components/ui/AppSwitch.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import SectionPills from '@/components/common/SectionPills.vue'
import FieldControl from '@/components/detail/FieldControl.vue'
import { useResource } from '@/composables/list/useResource'
import { formatDateExample, formatNumberExample, formatTimeExample, timeInZone } from '@/utils/detail/formatExamples'
import { notify } from '@/utils/common/notify'

const props = defineProps({
  fieldGroups: { type: Array, default: () => [] },
  values: { type: Object, default: () => ({}) },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['stage'])

const SECTIONS = [
  { id: 'ws-identity', label: 'App Identity' },
  { id: 'ws-format', label: 'Date & Number Format' },
  { id: 'ws-limits', label: 'Limits' },
  { id: 'ws-files', label: 'Files' },
]
const FORMATS = [
  { name: 'date_format', label: 'Date Format', example: formatDateExample },
  { name: 'time_format', label: 'Time Format', example: formatTimeExample },
  { name: 'number_format', label: 'Number Format', example: formatNumberExample },
]

const APP_NAME_FIELD = { fieldname: 'app_name', label: 'App Name', fieldtype: 'Data' }
const APP_LOGO_FIELD = { fieldname: 'app_logo', label: 'App Logo', fieldtype: 'Attach Image' }

const allFields = computed(() => Object.fromEntries(props.fieldGroups.flatMap((g) => g.fields).map((f) => [f.fieldname, f])))
const field = (name) => allFields.value[name] || { fieldname: name, label: name, fieldtype: 'Data' }
const optionsOf = (name) => (field(name).options || '').split('\n').filter(Boolean)
const timezoneOptions = computed(() => optionsOf('time_zone'))

// ── Live clock for the selected time zone (needs real IANA names) ─────────
const now = ref(new Date())
let timer
onMounted(() => (timer = setInterval(() => (now.value = new Date()), 1000)))
onBeforeUnmount(() => clearInterval(timer))
const zoneClock = computed(() => (props.values.time_zone ? timeInZone(props.values.time_zone, now.value) : ''))

// ── Allowed file extensions (newline-separated string <-> chips) ──────────
const extensions = computed(() =>
  String(props.values.allowed_file_extensions || '')
    .split(/[\n,]+/)
    .map((e) => e.trim())
    .filter(Boolean),
)
const normalizeExtension = (v) => v.trim().replace(/^\./, '').toLowerCase()
const validateExtension = (v) => (/^[a-z0-9]{1,6}$/.test(v) ? '' : 'Use 1-6 letters or numbers only')

// ── App name / logo (saved immediately) ────────────────────────────────────
const appName = ref('')
const appLogo = ref('')
let savedWebsiteValues = { app_name: '', app_logo: '' }

const websiteResource = useResource({ url: 'verp_staffing.settings.doctype.erp_configuration.erp_configuration.get_website_app_settings' })
const updateWebsiteResource = useResource({
  url: 'verp_staffing.settings.doctype.erp_configuration.erp_configuration.update_website_app_settings',
})

async function loadWebsiteSettings() {
  const data = await websiteResource.resource.fetch()
  if (!data) return
  appName.value = data.app_name || ''
  appLogo.value = data.app_logo || ''
  savedWebsiteValues = { app_name: appName.value, app_logo: appLogo.value }
}
loadWebsiteSettings()

async function saveWebsiteField(fieldname, value) {
  if (savedWebsiteValues[fieldname] === value) return
  const data = await updateWebsiteResource.resource.submit({ [fieldname]: value })
  if (!data) return
  savedWebsiteValues = { app_name: data.app_name, app_logo: data.app_logo }
  notify.success('Website Settings updated.')
}
function onLogoChange(value) {
  appLogo.value = value
  saveWebsiteField('app_logo', value)
}
const debouncedSaveAppName = debounce((value) => saveWebsiteField('app_name', value), 600)
function onAppNameChange(value) {
  appName.value = value
  debouncedSaveAppName(value)
}
</script>

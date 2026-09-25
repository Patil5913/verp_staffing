<template>
  <div class="flex flex-col gap-6">
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <FieldControl :field="APP_NAME_FIELD" :disabled="disabled" :model-value="appName" @update:model-value="onAppNameChange" />
      <FieldControl :field="APP_LOGO_FIELD" :disabled="disabled" :model-value="appLogo" @update:model-value="onLogoChange" />
    </div>

    <div v-for="group in fieldGroups" :key="group.label" class="flex flex-col gap-3">
      <h4 v-if="group.label" class="border-t border-app-border pt-4 text-p-base font-medium text-app-text">
        {{ group.label }}
      </h4>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FieldControl
          v-for="field in group.fields"
          :key="field.fieldname"
          :field="field"
          :disabled="disabled"
          :model-value="values[field.fieldname]"
          @update:model-value="(v) => emit('stage', field.fieldname, v)"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
// Ports ERP Configuration's "Website Settings" tab. App Name/App Logo are
// Website Settings' own fields, saved immediately per-field here (same as
// the old render_website_app_settings()) - safe to keep self-contained
// since nothing is lost if this component remounts on a tab switch. The
// System Settings quick-edit grid below it is otherwise-owned state
// (fieldGroups/values/stage come from the page's useSystemSettingsPanel())
// since THAT has pending, unsaved edits that must survive a tab switch.
import { ref } from 'vue'
import { debounce } from 'frappe-ui'
import FieldControl from '@/components/detail/FieldControl.vue'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'

defineProps({
  fieldGroups: { type: Array, default: () => [] },
  values: { type: Object, default: () => ({}) },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['stage'])

const APP_NAME_FIELD = { fieldname: 'app_name', label: 'App Name', fieldtype: 'Data' }
const APP_LOGO_FIELD = { fieldname: 'app_logo', label: 'App Logo', fieldtype: 'Attach Image' }

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

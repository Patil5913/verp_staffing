<template>
  <DetailPageLayout :title="doctype" :tabs="tabs" v-model:active-tab="activeTab" @back="router.back()">
    <template #actions>
      <RecordActionBar v-if="canWrite" show-save :save-loading="save.loading" @save="onSave" />
    </template>

    <template #tab-settings>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <div class="mx-auto flex max-w-2xl flex-col gap-4">
          <StateBanner
            v-if="meta.isPermissionError"
            icon="lock"
            title="Permission denied"
            :description="`You don't have access to view ${doctype}.`"
          />
          <StateBanner
            v-else-if="meta.hasError"
            icon="alert-triangle"
            title="Couldn't load settings"
            :description="meta.errorMessage"
          />
          <div v-else-if="meta.isLoading && !meta.resource.data" class="flex justify-center py-16">
            <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
          </div>

          <div v-else class="flex flex-col gap-4 rounded-lg border border-app-border bg-app-panel p-6">
            <AppInput
              v-for="field in fields"
              :key="field.fieldname"
              :type="controlType(field)"
              :label="field.label"
              :model-value="values[field.fieldname]"
              :options="selectOptions(field)"
              :disabled="!canWrite || field.read_only"
              @update:model-value="(v) => (values[field.fieldname] = v)"
            />
          </div>
        </div>
      </div>
    </template>
  </DetailPageLayout>
</template>

<script setup>
import AppInput from '@/components/ui/AppInput.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { LoadingIndicator } from 'frappe-ui'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'
import StateBanner from '@/components/common/StateBanner.vue'

const route = useRoute()
const router = useRouter()
const doctype = computed(() => route.params.doctype)
const tabs = [{ key: 'settings', label: 'Settings' }]
const activeTab = ref('settings')

const meta = useResource({
  url: 'verp_staffing.utils.list_view.get_settings_meta',
  makeParams: () => ({ doctype: doctype.value }),
  auto: true,
})

const fields = computed(() => meta.resource.data?.fields || [])
const canWrite = computed(() => !!meta.resource.data?.perms?.write)

const values = reactive({})
watch(
  () => meta.resource.data,
  (data) => {
    if (!data) return
    Object.keys(values).forEach((k) => delete values[k])
    Object.assign(values, data.values)
  },
  { immediate: true },
)

const TYPE_MAP = {
  Data: 'text',
  'Small Text': 'textarea',
  'Long Text': 'textarea',
  'Text Editor': 'textarea',
  Code: 'textarea',
  JSON: 'textarea',
  Int: 'number',
  Float: 'number',
  Currency: 'number',
  Percent: 'number',
  Duration: 'number',
  Rating: 'number',
  Check: 'checkbox',
  Select: 'select',
  Date: 'date',
  Datetime: 'datetime-local',
  Link: 'text', // no dedicated link-picker in this pass; plain text entry of the linked name
}

function controlType(field) {
  return TYPE_MAP[field.fieldtype] || 'text'
}

function selectOptions(field) {
  if (field.fieldtype !== 'Select') return undefined
  return (field.options || '').split('\n').filter(Boolean).map((v) => ({ label: v, value: v }))
}

const save = useResource({
  url: 'frappe.client.set_value',
  onSuccess() {
    notify.success('Saved.')
    meta.resource.reload()
  },
})

function onSave() {
  save.resource.submit({
    doctype: doctype.value,
    name: doctype.value,
    fieldname: { ...values },
  })
}
</script>

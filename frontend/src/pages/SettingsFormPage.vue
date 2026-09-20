<template>
  <div class="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-8">
    <h1 class="text-2xl font-semibold text-app-text">{{ doctype }}</h1>

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

      <div v-if="canWrite" class="flex justify-end border-t border-app-border pt-4">
        <AppButton variant="solid" :loading="save.loading" @click="onSave">Save</AppButton>
      </div>
    </div>
  </div>
</template>

<script setup>
import AppInput from '@/components/ui/AppInput.vue'
import AppButton from '@/components/common/AppButton.vue'
import { computed, reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
import { LoadingIndicator } from 'frappe-ui'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'
import StateBanner from '@/components/common/StateBanner.vue'

const route = useRoute()
const doctype = computed(() => route.params.doctype)

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

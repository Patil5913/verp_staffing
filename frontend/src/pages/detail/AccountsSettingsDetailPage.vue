<template>
  <DetailPageLayout title="Accounts Settings" :tabs="tabs" v-model:active-tab="activeTab" @back="goBack">
    <template #actions>
      <RecordActionBar v-if="canWrite" show-save :save-dirty="isDirty" :save-loading="saving" @save="onSave" />
    </template>

    <template #tab-settings>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <div class="mx-auto flex max-w-2xl flex-col gap-4">
          <StateBanner
            v-if="metaResource.resource.isPermissionError"
            icon="lock"
            title="Permission denied"
            description="You don't have access to view Accounts Settings."
          />
          <StateBanner
            v-else-if="metaResource.resource.hasError"
            icon="alert-triangle"
            title="Couldn't load settings"
            :description="metaResource.resource.errorMessage"
          />
          <div v-else-if="metaResource.resource.isLoading && !metaResource.resource.data" class="flex justify-center py-16">
            <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
          </div>

          <SectionCard v-else id="settings" title="Accounts Settings">
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FieldControl
                v-for="f in fields"
                :key="f.fieldname"
                :field="f"
                :disabled="!canWrite"
                :model-value="values[f.fieldname]"
                show-errors
                @update:model-value="(v) => (values[f.fieldname] = v)"
              />
            </div>
          </SectionCard>
        </div>
      </div>
    </template>
  </DetailPageLayout>
</template>

<script setup>
// Accounts Settings' own page - a Single doctype, so like ERP Configuration
// it's built on get_settings_meta/frappe.client.set_value (useDocDetail only
// works for non-Single doctypes) rather than the generic DocDetailPage.
// FieldControl renders each field by its real fieldtype (a Check becomes a
// checkbox, a Select a dropdown, ...) instead of SettingsFormPage's plain
// text-input-for-everything fallback.
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { LoadingIndicator } from 'frappe-ui'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import FieldControl from '@/components/detail/FieldControl.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { useResource } from '@/composables/list/useResource'
import { useUnsavedChangesGuard } from '@/composables/common/useUnsavedChangesGuard'
import { useSaveShortcut } from '@/composables/common/useSaveShortcut'
import { notify } from '@/utils/common/notify'

const router = useRouter()
const tabs = [{ key: 'settings', label: 'Accounts Settings' }]
const activeTab = ref('settings')

function goBack() {
  router.push('/')
}

const metaResource = useResource({
  url: 'verp_staffing.utils.list_view.get_settings_meta',
  makeParams: () => ({ doctype: 'Accounts Settings' }),
  auto: true,
})
const fields = computed(() => metaResource.resource.data?.fields || [])
const canWrite = computed(() => !!metaResource.resource.data?.perms?.write)

const values = reactive({})
function seedValues() {
  const data = metaResource.resource.data?.values || {}
  Object.keys(values).forEach((k) => delete values[k])
  Object.assign(values, data)
}
watch(
  () => metaResource.resource.data,
  (data) => {
    if (data) seedValues()
  },
  { immediate: true },
)

const snapshot = () => JSON.stringify(values)
const baseline = ref(null)
const isDirty = computed(() => baseline.value !== null && snapshot() !== baseline.value)
watch(
  () => metaResource.resource.data,
  async (data) => {
    if (!data || baseline.value !== null) return
    await nextTick()
    baseline.value = snapshot()
  },
  { immediate: true },
)

const saving = ref(false)
const saveResource = useResource({ url: 'frappe.client.set_value' })

async function onSave() {
  saving.value = true
  try {
    const result = await saveResource.resource.submit({
      doctype: 'Accounts Settings',
      name: 'Accounts Settings',
      fieldname: { ...values },
    })
    if (!result) return false

    metaResource.resource.setData({ ...metaResource.resource.data, values: result })
    seedValues()
    notify.success('Saved.')
    await nextTick()
    baseline.value = snapshot()
    return true
  } finally {
    saving.value = false
  }
}

useUnsavedChangesGuard(isDirty, onSave)
useSaveShortcut(isDirty, onSave)
</script>

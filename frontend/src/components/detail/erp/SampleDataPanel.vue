<template>
  <div class="flex flex-col gap-3">
    <p v-if="removed" class="text-p-sm text-app-text-muted">Sample data has already been removed from this site.</p>
    <template v-else>
      <p class="text-p-sm text-app-text-muted">
        Removes every record inserted by the "Add sample data" setup-wizard step. This can't be undone.
      </p>
      <div>
        <AppButton variant="danger" icon="trash-2" :loading="checking" @click="onCheck">Remove Sample Data</AppButton>
      </div>
    </template>
  </div>

  <Dialog v-model="showDialog" :options="{ title: dialogTitle, size: 'lg' }">
    <template #body-content>
      <div class="flex flex-col gap-3">
        <p class="text-p-sm text-app-text">
          This will permanently delete {{ deletableTotal }} sample record(s). This cannot be undone.
        </p>
        <p v-if="summary?.conflicts?.length" class="text-p-sm text-app-text">
          {{ summary.conflicts.length }} document(s) were created on top of sample data and will also be deleted.
        </p>
        <p v-if="summary?.unexpected_doctypes?.length" class="text-p-sm text-app-text">
          The doctype(s) below aren't safe to remove automatically (some are shared structural records, not just
          demo transactions) - they'll be left as-is; everything else will still be deleted. Review these manually
          if you want them gone too.
        </p>

        <div class="max-h-72 overflow-y-auto rounded-lg border border-app-border">
          <div v-for="(names, doctype) in relevantRecords" :key="doctype" class="border-b border-app-border p-3 last:border-0">
            <div class="mb-1 flex items-center gap-2 text-p-sm font-medium text-app-text">
              <span class="rounded bg-app-panel-2 px-1.5 py-0.5 text-p-xs uppercase text-app-text-muted">{{ doctype }}</span>
              <span v-if="summary?.unexpected_doctypes?.includes(doctype)" class="text-p-xs text-app-text-muted">will be skipped</span>
              <span>{{ names.length }}</span>
            </div>
            <div class="flex flex-wrap gap-1.5">
              <span v-for="n in names" :key="n" class="rounded-md bg-app-panel-2 px-2 py-0.5 text-p-xs text-app-text">{{ n }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
    <template #actions>
      <div class="flex w-full justify-end gap-2">
        <AppButton variant="outline" @click="showDialog = false">Cancel</AppButton>
        <AppButton variant="danger" :loading="removing" @click="onConfirmRemove">Delete Sample Data</AppButton>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
// Simplified port of ERP Configuration's "Remove Sample Data" flow
// (get_sample_data_summary / remove_sample_data - both existing backend
// endpoints, no change there). The old widget split this into 3 separate
// dialog variants (plain / conflicts / unexpected-doctypes); this collapses
// them into one dialog whose body adapts, since visually they were mostly
// the same "here's what gets deleted" listing either way.
import { computed, ref, watch } from 'vue'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'

const props = defineProps({
  isSampleDataRemoved: { type: [Boolean, Number], default: false },
})
const emit = defineEmits(['removed'])

// Mirrors the old desk erp_configuration.js refresh(frm)'s button-visibility
// rule: once is_sample_data_removed is set, there's nothing left to remove.
const removed = ref(Boolean(props.isSampleDataRemoved))
watch(() => props.isSampleDataRemoved, (v) => (removed.value = Boolean(v)))

const summaryResource = useResource({
  url: 'verp_staffing.settings.doctype.erp_configuration.erp_configuration.get_sample_data_summary',
})
const removeResource = useResource({
  url: 'verp_staffing.settings.doctype.erp_configuration.erp_configuration.remove_sample_data',
})

const checking = computed(() => summaryResource.isLoading)
const removing = computed(() => removeResource.isLoading)
const showDialog = ref(false)
const summary = ref(null)

const dialogTitle = computed(() => {
  if (summary.value?.conflicts?.length) return 'Sample Data Has Live Links'
  return 'Remove Sample Data'
})

// Every tracked doctype is listed - unexpected ones just get an extra
// "will be skipped" note (see the template) rather than being the only
// thing shown, now that they no longer block deleting the rest.
const relevantRecords = computed(() => summary.value?.records || {})

const deletableTotal = computed(() => {
  if (!summary.value) return 0
  const skipped = summary.value.unexpected_doctypes || []
  return Object.entries(summary.value.records || {})
    .filter(([dt]) => !skipped.includes(dt))
    .reduce((sum, [, names]) => sum + names.length, 0)
})

async function onCheck() {
  const data = await summaryResource.resource.fetch()
  if (!data) return
  if (!data.total) {
    notify.success('No sample data found.')
    return
  }
  summary.value = data
  showDialog.value = true
}

async function onConfirmRemove() {
  const deleteConflicts = summary.value?.conflicts?.length ? 1 : 0
  const res = await removeResource.resource.submit({ delete_conflicts: deleteConflicts })
  if (!res) return

  if (res.status === 'conflicts') {
    summary.value = { ...summary.value, conflicts: res.conflicts }
    return
  }

  showDialog.value = false
  const result = res.result || {}
  const deletedTotal = Object.values(result.doctype_counts || {}).reduce((a, b) => a + b, 0)
  const skippedDoctypes = Object.keys(result.skipped_unexpected || {})

  // The server marks sample data removed once this run finishes regardless
  // of skipped_unexpected (that's a deliberate "don't auto-delete shared
  // structural masters" carve-out, not a failure) - real problems only show
  // up as result.errors. is_sample_data_removed in the response is instead
  // "was every tracked record actually gone", which is never true while
  // anything was intentionally skipped, so it's not what should decide
  // whether this counts as success.
  if (result.errors?.length) {
    notify.error(`${deletedTotal} record(s) deleted; ${result.errors.length} failed - see the error log for details.`)
  } else if (skippedDoctypes.length) {
    notify.success(`${deletedTotal} record(s) deleted. Left as-is (needs manual review): ${skippedDoctypes.join(', ')}.`)
  } else {
    notify.success('Sample data removed.')
  }
  // Only a clean run switches the feature off; leftovers (errors, records needing review) can be retried.
  if (res.is_sample_data_removed) {
    removed.value = true
    emit('removed')
  }
}
</script>

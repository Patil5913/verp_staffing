<template>
  <div v-if="!detail.isNew.value" class="flex flex-col gap-1.5">
    <label class="text-p-sm font-medium text-app-text-muted">Assigned To</label>
    <AppLinkField
      doctype="Employee"
      v-model="detail.values.assign_to"
      :disabled="!detail.canWrite.value || !allowed"
      query="verp_staffing.crm.api.helpers.get_subordinate_employees"
      :filters="{ department: 'Marketing' }"
    />
    <p v-if="!allowed" class="text-p-xs text-app-text-muted">Only the highest authority of Marketing can change this.</p>
  </div>
</template>

<script setup>
// Who an Interview belongs to. It stays with the employee who ran it when the Marketing record moves
// on; only the Marketing's top authority may hand it to someone else (also enforced on save).
import { computed, ref, watch } from 'vue'
import { call } from 'frappe-ui'
import AppLinkField from '@/components/common/AppLinkField.vue'

const props = defineProps({
  detail: { type: Object, required: true },
  name: { type: String, default: '' },
})

const allowed = ref(false)
watch(
  () => [props.name, props.detail.isNew.value],
  async ([name, fresh]) => {
    allowed.value = false
    if (!name || fresh) return
    try {
      allowed.value = !!(await call('verp_staffing.crm.api.helpers.can_reassign_interview', { name }))?.allowed
    } catch {
      allowed.value = false
    }
  },
  { immediate: true },
)
</script>

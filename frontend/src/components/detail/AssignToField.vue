<template>
  <div class="flex flex-col gap-1.5">
    <label class="text-p-sm font-medium text-app-text-muted">{{ label }}</label>
    <AppLinkField
      doctype="Employee"
      v-model="detail.values[fieldname]"
      :disabled="locked || !detail.canWrite.value"
      :query="query"
      :filters="mergedFilters"
    />
  </div>
</template>

<script setup>
// The "Assign To" Employee picker every service record has — restricted
// server-side by a whitelisted standard query (desk's frm.set_query on
// assign_to): `get_assign_to_by_service` for a service + customer, or
// `get_subordinate_employees` for a department's subordinates.
import { computed } from 'vue'
import AppLinkField from '@/components/common/AppLinkField.vue'

const props = defineProps({
  detail: { type: Object, required: true },
  locked: { type: Boolean, default: false },
  label: { type: String, default: 'Assign To' },
  fieldname: { type: String, default: 'assign_to' },
  query: { type: String, default: 'verp_staffing.crm.api.helpers.get_subordinate_employees' },
  filters: { type: Object, default: () => ({}) },
  // Adds the record's customer / service / department to the query's filters.
  withCustomer: { type: Boolean, default: false },
  serviceField: { type: String, default: '' },
  departmentField: { type: String, default: '' },
})

const mergedFilters = computed(() => ({
  ...props.filters,
  ...(props.withCustomer ? { customer: props.detail.values.customer } : {}),
  ...(props.serviceField ? { service: props.detail.values[props.serviceField] } : {}),
  ...(props.departmentField ? { department: props.detail.values[props.departmentField] } : {}),
}))
</script>

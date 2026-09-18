<template>
  <SectionCard :title="title" :subtitle="subtitle">
    <p v-if="!customer" class="py-4 text-center text-p-sm text-app-text-muted">No customer selected.</p>
    <div v-else-if="displayFields.isLoading || (records.isLoading && !records.resource.data)" class="flex justify-center py-6">
      <LoadingIndicator class="h-5 w-5 text-app-text-muted" />
    </div>
    <p v-else-if="!fields.length" class="py-4 text-center text-p-sm text-app-text-muted">
      No fields are configured to show here for {{ displayKey }}. An administrator can set them in ERP Configuration.
    </p>
    <p v-else-if="!(records.resource.data || []).length" class="py-4 text-center text-p-sm text-app-text-muted">
      No records found.
    </p>

    <div v-else class="flex flex-col gap-4">
      <div
        v-for="record in records.resource.data"
        :key="record.name"
        class="overflow-hidden rounded-lg border border-app-border"
      >
        <dl class="divide-y divide-app-border">
          <div
            v-for="field in record.fields"
            :key="field.fieldname"
            class="grid grid-cols-1 gap-1 px-4 py-2.5 sm:grid-cols-[220px_1fr] sm:gap-4"
          >
            <dt class="text-p-sm font-medium text-app-text-muted">{{ field.label }}</dt>
            <dd class="min-w-0 break-words text-p-sm text-app-text">
              <a
                v-if="isFile(field)"
                :href="field.value"
                target="_blank"
                rel="noopener"
                class="text-app-primary hover:underline"
              >
                {{ fileName(field.value) }}
              </a>
              <template v-else>{{ display(field) || '—' }}</template>
            </dd>
          </div>
        </dl>

        <div v-for="table in record.tables" :key="table.fieldname" class="border-t border-app-border">
          <p class="bg-app-panel-2 px-4 py-2 text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">
            {{ table.label }}
          </p>
          <div v-if="table.rows.length" class="overflow-x-auto">
            <table class="w-full text-left text-p-sm">
              <thead class="text-p-xs text-app-text-muted">
                <tr>
                  <th v-for="col in table.columns" :key="col.fieldname" class="whitespace-nowrap px-4 py-1.5 font-medium">
                    {{ col.label }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in table.rows" :key="i" class="border-t border-app-border">
                  <td v-for="col in table.columns" :key="col.fieldname" class="px-4 py-1.5 text-app-text">
                    {{ row[col.fieldname] ?? '—' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="px-4 py-3 text-p-sm text-app-text-muted">No rows.</p>
        </div>
      </div>
    </div>
  </SectionCard>
</template>

<script setup>
// The customer's Lead Detail Form data, limited to the fields ERP
// Configuration allows this department to see — the desk form's
// "customer details / lead details" HTML block. `displayKey` is the
// department (doctype) name that config is keyed by.
import { computed } from 'vue'
import { LoadingIndicator } from 'frappe-ui'
import SectionCard from '@/components/common/SectionCard.vue'
import { useCustomerContext } from '@/composables/detail/useCustomerContext'
import { formatFieldValue } from '@/utils/list/formatValue'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  customer: { type: String, default: '' },
  detail: { type: Object, default: null },
  displayKey: { type: String, default: '' },
  // ...or the field on the record whose value is the key (Other Services
  // are keyed by their `service` item, not by doctype).
  displayKeyField: { type: String, default: '' },
  // Overrides the ERP Configuration allowlist with a fixed fieldname list
  // (CR / Onboardings show a hardcoded set).
  fixedFields: { type: Array, default: null },
  title: { type: String, default: 'Customer Details' },
  subtitle: { type: String, default: '' },
})

const customer = computed(() => props.customer || props.detail?.values.customer || '')
const displayKey = computed(() => props.displayKey || props.detail?.values[props.displayKeyField] || '')
const { fields: configured, displayFields, records } = useCustomerContext(customer, displayKey, computed(() => props.fixedFields))
const fields = computed(() => props.fixedFields || configured.value)

const FILE_TYPES = ['Attach', 'Attach Image']
const isFile = (f) => FILE_TYPES.includes(f.fieldtype) && f.value
const fileName = (url) => decodeURIComponent(String(url).split('/').pop())
const display = (f) => (f.fieldtype === 'Text Editor' ? String(f.value ?? '').replace(/<[^>]+>/g, ' ') : formatFieldValue(f.value, f))
</script>

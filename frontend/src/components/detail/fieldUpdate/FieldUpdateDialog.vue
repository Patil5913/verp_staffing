<template>
  <Dialog v-model="open" :options="{ title: 'Update Detail', size: '3xl' }">
    <template #body-content>
      <div v-if="loading" class="flex justify-center py-10"><LoadingIndicator class="h-6 w-6 text-app-text-muted" /></div>
      <StateBanner v-else-if="loadError" icon="alert-triangle" title="Couldn't load the fields" :description="loadError" />
      <StateBanner
        v-else-if="!simpleList.length && !tableList.length"
        icon="lock"
        title="Nothing you can update"
        description="No fields are set up for your department to change. Ask an administrator."
      />

      <div v-else class="flex flex-col gap-5">
        <p class="text-p-sm text-app-text-muted">
          Pick the details you need changed and enter the new values.
          {{ isHigherAuthority ? "You are the top of your department's hierarchy, so on save the data will be directly updated - Please be sure before confirming." : 'Your update request are sent to your manager for approval.' }}
        </p>

        <div class="flex flex-wrap gap-2">
          <button
            v-for="f in [...simpleList, ...tableList]"
            :key="f.fieldname"
            type="button"
            class="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-p-sm transition-colors"
            :class="selected.has(f.fieldname) ? 'border-app-primary bg-app-primary-tint font-medium text-app-primary' : 'border-app-border text-app-text hover:bg-app-panel-2'"
            @click="toggle(f)"
          >
            <span :class="selected.has(f.fieldname) ? 'lucide-square-check' : 'lucide-square'" class="size-3.5" />
            {{ f.label }}
            <span v-if="f.isTable" class="text-p-xs text-app-text-muted">(table)</span>
          </button>
        </div>

        <div v-for="f in simpleList.filter((x) => selected.has(x.fieldname))" :key="f.fieldname" class="flex flex-col gap-1 rounded-lg border border-app-border p-3">
          <FieldControl :field="f" v-model="newValues[f.fieldname]" show-errors />
          <p class="text-p-xs text-app-text-muted">Current: {{ show(current[f.fieldname]) }}</p>
          <p v-if="errors[f.fieldname]" class="text-p-xs text-red-600">{{ errors[f.fieldname] }}</p>
        </div>

        <div v-for="t in tableList.filter((x) => selected.has(x.fieldname))" :key="t.fieldname" class="rounded-lg border border-app-border p-3">
          <ChildTableField :table="t.table" :rows="tableRows[t.fieldname] || []" @update:rows="(rows) => (tableRows[t.fieldname] = rows)" />
        </div>

        <AppTextarea
          v-if="selected.size"
          v-model="reason"
          label="Reason for update"
          required
          placeholder="Explain why these details need to change."
        />
      </div>
    </template>
    <template #actions>
      <AppButton :loading="submitting" :disabled="!selected.size || !reason.trim()" @click="submit">
        {{ isHigherAuthority ? 'Update' : 'Send for approval' }}
      </AppButton>
    </template>
  </Dialog>
</template>

<script setup>
import AppTextarea from '@/components/ui/AppTextarea.vue'
// The "Update Detail" dialog (permission_feature.js's _open_update_detail_dialog):
// a department member - or the customer's owner - picks which Lead Detail Form
// fields need changing, enters new values and a reason, and the request is
// routed to an approver by verp_staffing.crm.api.permission_request (or applied
// straight away for the head of the department).
import { computed, reactive, ref, watch } from 'vue'
import { call, Dialog, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import ChildTableField from '@/components/detail/ChildTableField.vue'
import FieldControl from '@/components/detail/FieldControl.vue'
import { isPhoneField, sanitizePhone, validateFieldValue } from '@/utils/detail/fieldFormats'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

const API = 'verp_staffing.crm.api.permission_request'

const open = defineModel({ type: Boolean, default: false })
const props = defineProps({
  customer: { type: String, required: true },
  // 'service' - a department form (Resume, RUC, ...); 'owner' - the Customer form.
  mode: { type: String, default: 'service' },
  // service mode: which department's field list, and which record asked
  fieldsKey: { type: String, default: '' },
  serviceDoctype: { type: String, default: '' },
  serviceName: { type: String, default: '' },
  extraInfo: { type: String, default: '' },
  isHigherAuthority: { type: Boolean, default: false },
})
const emit = defineEmits(['done'])

const loading = ref(false)
const loadError = ref('')
const current = ref({})
const simple = ref({})
const tables = ref({})

const selected = ref(new Set())
const newValues = reactive({})
const tableRows = reactive({})
const errors = reactive({})
const reason = ref('')
const submitting = ref(false)

const prettify = (name) => name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

const simpleList = computed(() =>
  Object.entries(simple.value).map(([fieldname, m]) => ({
    fieldname,
    label: m.label || prettify(fieldname),
    fieldtype: m.fieldtype,
    options: m.options || '',
    reqd: 0,
  })),
)
const tableList = computed(() =>
  Object.entries(tables.value).map(([fieldname, m]) => ({
    fieldname,
    label: m.label || prettify(fieldname),
    isTable: true,
    table: {
      fieldname,
      label: m.label || prettify(fieldname),
      columns: Object.entries(m.columns || {}).map(([cn, c]) => ({
        fieldname: cn,
        label: c.label || prettify(cn),
        fieldtype: c.fieldtype,
        options: c.options || '',
        reqd: c.reqd || 0,
        description: c.description || '',
      })),
    },
  })),
)

const show = (value) => {
  if (Array.isArray(value)) return value.length ? `${value.length} row${value.length === 1 ? '' : 's'}` : '-'
  return value === null || value === undefined || value === '' ? '-' : String(value)
}

function toggle(f) {
  const next = new Set(selected.value)
  if (next.has(f.fieldname)) {
    next.delete(f.fieldname)
  } else {
    next.add(f.fieldname)
    if (f.isTable) tableRows[f.fieldname] = (current.value[f.fieldname] || []).map((r) => ({ ...r }))
    else newValues[f.fieldname] = current.value[f.fieldname] ?? ''
  }
  selected.value = next
}

watch(open, async (isOpen) => {
  if (!isOpen) return
  selected.value = new Set()
  reason.value = ''
  Object.keys(errors).forEach((k) => delete errors[k])
  loading.value = true
  loadError.value = ''
  try {
    const fieldsCall =
      props.mode === 'owner'
        ? call(`${API}.get_customer_owner_updatable_fields`)
        : call(`${API}.get_department_updatable_fields`, { doctype: props.fieldsKey })
    const [values, fields] = await Promise.all([call(`${API}.get_lead_detail_field_values`, { customer_name: props.customer }), fieldsCall])
    current.value = values || {}
    simple.value = fields?.simple_fields || {}
    tables.value = fields?.table_fields || {}
  } catch (e) {
    loadError.value = normalizeError(e).message
  } finally {
    loading.value = false
  }
})

function collect() {
  const updates = {}
  let ok = true
  for (const f of simpleList.value.filter((x) => selected.value.has(x.fieldname))) {
    errors[f.fieldname] = ''
    let value = newValues[f.fieldname]
    if (f.fieldtype === 'Check') {
      value = value ? 1 : 0
    } else {
      value = String(value ?? '').trim()
      if (!value) {
        errors[f.fieldname] = `Please enter a new value for "${f.label}".`
        ok = false
        continue
      }
      if (isPhoneField(f.fieldname)) value = sanitizePhone(value)
      const problem = validateFieldValue(f, value)
      if (problem) {
        errors[f.fieldname] = problem
        ok = false
        continue
      }
    }
    updates[f.fieldname] = { old: current.value[f.fieldname] ?? '', new: value }
  }
  for (const t of tableList.value.filter((x) => selected.value.has(x.fieldname))) {
    updates[t.fieldname] = { old: current.value[t.fieldname] || [], new: tableRows[t.fieldname] || [] }
  }
  return ok ? updates : null
}

async function submit() {
  const updates = collect()
  if (!updates) return
  submitting.value = true
  try {
    const args = { customer_name: props.customer, reason: reason.value.trim(), field_updates: JSON.stringify(updates) }
    const res = await call(
      props.mode === 'owner' ? `${API}.request_field_update_by_owner` : `${API}.request_field_update`,
      props.mode === 'owner'
        ? args
        : { ...args, service_doctype: props.serviceDoctype || null, service_name: props.serviceName || null, extra_info: props.extraInfo || null },
    )
    if (res?.applied_directly) notify.success('Changes applied directly.')
    else notify.success(`Request sent to ${res?.manager_employee || 'your manager'} for approval.`)
    open.value = false
    emit('done')
  } catch (e) {
    notify.error(normalizeError(e).message)
  } finally {
    submitting.value = false
  }
}
</script>

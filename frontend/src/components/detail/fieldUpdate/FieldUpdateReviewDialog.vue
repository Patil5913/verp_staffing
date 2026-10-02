<template>
  <Dialog v-model="open" :options="{ title: 'Review update requests', size: '3xl' }">
    <template #body-content>
      <div class="flex max-h-[60vh] flex-col gap-5 overflow-y-auto pr-1">
        <div v-for="req in requests" :key="req.comment_name" class="flex flex-col gap-3 rounded-lg border border-app-border p-4">
          <div>
            <p class="text-p-sm font-medium text-app-text">Requested by {{ req.requested_by }}</p>
            <p class="text-p-sm text-app-text-muted">Reason: {{ req.reason }}</p>
          </div>
          <AppCheckbox
            v-for="(change, fieldname) in req.field_updates"
            :key="fieldname"
            class="!items-start !gap-3 rounded-lg border [&_input]:mt-1 px-3 py-2 transition-colors"
            :class="isPicked(req, fieldname) ? 'border-app-primary bg-app-primary-tint' : 'border-app-border hover:bg-app-panel-2'"
            :model-value="isPicked(req, fieldname)"
            @update:model-value="(v) => pick(req, fieldname, v)"
          >
            <span class="min-w-0 flex-1">
              <span class="block text-p-sm font-medium text-app-text">{{ labelOf(fieldname) }}</span>
              <template v-if="Array.isArray(change.new)">
                <span class="block text-p-xs text-app-text-muted">{{ (change.old || []).length }} → {{ change.new.length }} rows</span>
                <span v-for="(row, i) in change.new" :key="i" class="block truncate text-p-xs text-app-text">{{ i + 1 }}. {{ rowText(row) }}</span>
              </template>
              <span v-else class="block text-p-sm">
                <span class="text-app-text-muted line-through">{{ show(change.old) }}</span>
                <span class="mx-1.5 text-app-text-muted">→</span>
                <span class="text-app-text">{{ show(change.new) }}</span>
              </span>
            </span>
          </AppCheckbox>
        </div>
      </div>
    </template>
    <template #actions>
      <AppButton variant="danger" icon="x" :loading="working === 'reject'" :disabled="!!working" @click="rejectAll">Reject all</AppButton>
      <AppButton icon="check" :loading="working === 'accept'" :disabled="!!working || !pickedCount" @click="accept">Accept selected</AppButton>
    </template>
  </Dialog>
</template>

<script setup>
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
// The approver's "Accept Updates" dialog (permission_feature.js's
// _open_accept_updates_dialog): each pending request lists the fields it wants
// changed as old → new; the approver ticks the ones to apply (the rest are
// rejected by the server) or rejects the lot.
import { reactive, ref, watch } from 'vue'
import { call, Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import { confirmLeave } from '@/utils/common/confirmDialog'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

const API = 'verp_staffing.crm.api.permission_request'

const open = defineModel({ type: Boolean, default: false })
const props = defineProps({
  customer: { type: String, required: true },
  requests: { type: Array, default: () => [] },
  // { fieldname: { label } } - nicer names than the raw fieldnames
  labels: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['done'])

const picked = reactive({})
const working = ref('')
const pickedCount = ref(0)

const key = (req, fieldname) => `${req.comment_name}::${fieldname}`
const isPicked = (req, fieldname) => !!picked[key(req, fieldname)]
function pick(req, fieldname, on) {
  picked[key(req, fieldname)] = on
  pickedCount.value = Object.values(picked).filter(Boolean).length
}
watch(open, (o) => {
  if (!o) return
  Object.keys(picked).forEach((k) => delete picked[k])
  pickedCount.value = 0
})

const prettify = (name) => name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
const labelOf = (fieldname) => props.labels[fieldname]?.label || prettify(fieldname)
const show = (v) => (v === null || v === undefined || v === '' ? '-' : String(v))
const rowText = (row) =>
  Object.entries(row)
    .filter(([k, v]) => v !== null && v !== '' && !['name', 'idx', 'parent', 'parentfield', 'parenttype', 'doctype'].includes(k))
    .map(([, v]) => v)
    .join(' · ')

async function accept() {
  const byRequest = {}
  for (const req of props.requests) {
    const fields = Object.keys(req.field_updates || {}).filter((f) => isPicked(req, f))
    if (fields.length) byRequest[req.comment_name] = fields
  }
  working.value = 'accept'
  try {
    await Promise.all(
      Object.entries(byRequest).map(([comment, fields]) =>
        call(`${API}.apply_field_updates`, { customer_name: props.customer, comment_name: comment, approved_fields: JSON.stringify(fields) }),
      ),
    )
    notify.success('Updated successfully.')
    open.value = false
    emit('done')
  } catch (e) {
    notify.error(normalizeError(e).message)
  } finally {
    working.value = ''
  }
}

async function rejectAll() {
  if (!(await confirmLeave({ title: 'Reject all updates?', message: 'The requesters will be told their changes were rejected.', leaveLabel: 'Reject', cancelLabel: 'Cancel' }))) return
  working.value = 'reject'
  try {
    await Promise.all(props.requests.map((req) => call(`${API}.reject_field_update_request`, { customer_name: props.customer, comment_name: req.comment_name })))
    notify.success('All updates rejected.')
    open.value = false
    emit('done')
  } catch (e) {
    notify.error(normalizeError(e).message)
  } finally {
    working.value = ''
  }
}
</script>

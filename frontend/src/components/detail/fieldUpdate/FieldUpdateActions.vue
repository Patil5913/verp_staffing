<template>
  <template v-if="state.canUpdate">
    <AppButton v-if="!hideButtons" variant="outline" icon="pencil" :loading="preparing" @click="openUpdate">Update Detail</AppButton>
  </template>
  <AppBadge v-else-if="state.myPending" theme="orange" class="self-center">Your update request is pending approval</AppBadge>

  <AppButton v-if="state.requests.length && !hideButtons" variant="outline" icon="check-check" :loading="preparing" @click="openReview">
    Accept Updates ({{ state.requests.length }})
  </AppButton>

  <FieldUpdateDialog
    v-model="showUpdate"
    :customer="customer"
    :mode="mode"
    :fields-key="fieldsKey"
    :service-doctype="mode === 'service' ? doctype : ''"
    :service-name="mode === 'service' ? name : ''"
    :extra-info="extraInfo"
    :is-higher-authority="higherAuthority"
    @done="load"
  />
  <FieldUpdateReviewDialog v-model="showReview" :customer="customer" :requests="state.requests" :labels="labels" @done="onReviewed" />
</template>

<script setup>
import AppBadge from '@/components/ui/AppBadge.vue'
// The field-change request flow from permission_feature.js / customer.js, as
// two buttons on a record's action bar:
//  * Update Detail - for the record's assignee or the customer's owner: ask to
//    change details held on the customer's Lead Detail Form (the server routes
//    it to an approver, or applies it directly for the head of the department);
//  * Accept Updates - for an approver with requests waiting.
// `mode` "service" is a department form (Resume, RUC, ... - the customer is
// the record's `customer`); "owner" is the Customer form itself.
import { computed, reactive, ref, watch } from 'vue'
import { call } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import FieldUpdateDialog from './FieldUpdateDialog.vue'
import FieldUpdateReviewDialog from './FieldUpdateReviewDialog.vue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

const API = 'verp_staffing.crm.api.permission_request'

const props = defineProps({
  detail: { type: Object, required: true },
  doctype: { type: String, required: true },
  name: { type: String, required: true },
  mode: { type: String, default: 'service' },
  // Buttons live in a menu instead (openUpdate / openReview and `state` are exposed).
  hideButtons: { type: Boolean, default: false },
  // Config-driven pages hand these to every action; not used here.
  locked: { type: Boolean, default: false },
  save: { type: Function, default: null },
})
const emit = defineEmits(['changed'])

const customer = computed(() => (props.mode === 'owner' ? props.name : props.detail.values.customer || ''))
// The department's field list is keyed by the service ("Other Services" records
// carry a `service`), else by the doctype itself.
const fieldsKey = computed(() => props.detail.values.service || props.doctype)
const extraInfo = computed(() => (props.doctype === 'Other Services' ? props.detail.values.service || '' : ''))

const state = reactive({ canUpdate: false, myPending: false, requests: [] })
const labels = ref({})
const higherAuthority = ref(false)
const preparing = ref(false)
const showUpdate = ref(false)
const showReview = ref(false)

const fetchValue = (doctype, filters, fieldname) => call('frappe.client.get_value', { doctype, filters, fieldname }).catch(() => null)

async function load() {
  Object.assign(state, { canUpdate: false, myPending: false, requests: [] })
  if (props.detail.isNew.value || !customer.value) return

  const employee = (await fetchValue('Employee', { user: window.user }, 'name'))?.name
  if (!employee) return

  try {
    if (props.mode === 'owner') {
      // customer.js: the owner may ask for changes once a candidate form is required.
      if (employee === props.detail.values.customer_owner) {
        const required = (await call(`${API}.get_candidate_form_required_status`, { customer_name: customer.value }))?.required
        if (required) {
          const mine = await call(`${API}.get_owner_pending_field_update_request`, { customer_name: customer.value })
          state.myPending = !!mine?.has_pending
          state.canUpdate = !state.myPending
        }
      }
      state.requests = (await call(`${API}.get_all_pending_field_update_requests`, { customer_name: customer.value })) || []
      return
    }

    const assignee = props.detail.values.assign_to
    const owner = (await fetchValue('Customer', customer.value, 'customer_owner'))?.customer_owner
    if (employee === assignee || employee === owner) {
      const mine = await call(`${API}.get_owner_pending_field_update_request`, { customer_name: customer.value })
      state.myPending = !!mine?.has_pending
      state.canUpdate = !state.myPending
    } else {
      const pending = await call(`${API}.get_pending_field_update_request`, { customer_name: customer.value })
      if (pending?.has_pending) state.requests = [pending]
    }
  } catch {
    // The buttons are a convenience; the server refuses whatever isn't allowed.
  }
}

watch(
  () => [props.name, customer.value, props.detail.values.assign_to, props.detail.values.customer_owner, props.detail.isNew.value],
  load,
  { immediate: true },
)

async function openUpdate() {
  preparing.value = true
  try {
    if (props.mode === 'service') {
      const status = await call(`${API}.get_higher_authority_status`, { service_doctype: props.doctype, extra_info: extraInfo.value || null }).catch(() => null)
      higherAuthority.value = !!status?.is_higher_authority
    } else {
      higherAuthority.value = false
    }
    showUpdate.value = true
  } finally {
    preparing.value = false
  }
}

async function openReview() {
  preparing.value = true
  try {
    const fields =
      props.mode === 'owner'
        ? await call(`${API}.get_customer_owner_updatable_fields`)
        : await call(`${API}.get_department_updatable_fields`, { doctype: fieldsKey.value })
    labels.value = { ...(fields?.simple_fields || {}), ...(fields?.table_fields || {}) }
  } catch (e) {
    labels.value = {}
    notify.error(normalizeError(e).message)
  } finally {
    preparing.value = false
  }
  showReview.value = true
}

async function onReviewed() {
  await load()
  props.detail.refresh?.()
  emit('changed')
}
defineExpose({ openUpdate, openReview, state })
</script>

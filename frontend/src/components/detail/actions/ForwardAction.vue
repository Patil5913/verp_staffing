<template>
  <ForwardCandidateButton
    v-if="!detail.isNew.value && customer"
    :doctype="doctype"
    :name="name"
    :customer="customer"
    :from-service-name="fromServiceName || (serviceField && detail.values[serviceField]) || doctype"
    @forwarded="detail.refresh()"
  />
</template>

<script setup>
// Adapter so ConfigDetailPage can drop the "Forward Candidate" action into
// any service record's action bar from config alone (it hands every action
// {detail, doctype, name}). `fromServiceName` is a fixed name, or
// `serviceField` names the field holding it (Other Services forwards under
// its `service` item).
import { computed } from 'vue'
import ForwardCandidateButton from './ForwardCandidateButton.vue'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  doctype: { type: String, required: true },
  name: { type: String, required: true },
  fromServiceName: { type: String, default: '' },
  serviceField: { type: String, default: '' },
  customerField: { type: String, default: 'customer' },
})
const customer = computed(() => props.detail.values[props.customerField])
</script>

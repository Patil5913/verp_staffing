<template>
  <DocDetailView
    :doctype="doctype"
    :detail="detail"
    :fieldnames="['target', 'start_date', 'target_based_on']"
    :force-disabled="locked || !isSuperior"
  />
</template>

<script setup>
// Marketing's target block (target / start date / based-on). Only a
// superior of the assignee may set these — the assignee sees them but can't
// move their own goalposts (marketing.js's _is_superior_in_department).
import { computed } from 'vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import { useIsSuperior } from '@/composables/detail/useIsSuperior'

const props = defineProps({
  detail: { type: Object, required: true },
  doctype: { type: String, required: true },
  locked: { type: Boolean, default: false },
})

const { isSuperior } = useIsSuperior(
  computed(() => props.detail.values.assign_to),
  'Marketing',
)
</script>

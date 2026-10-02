<template>
  <span class="block min-w-0 max-w-full truncate" :class="titleClass">{{ display }}</span>
</template>

<script setup>
import { computed, watchEffect } from 'vue'
import { recordTitle, requestTitles, setRecordTitle } from '@/composables/common/useRecordTitles'

// A record's human name, shown in place of its ID. Falls back to the ID only
// when the record has no name of its own.
const props = defineProps({
  doctype: { type: String, default: '' },
  id: { type: String, default: '' },
  // A title the caller already has - skips the lookup.
  title: { type: String, default: '' },
  titleClass: { type: String, default: '' },
})

watchEffect(() => {
  if (props.title) setRecordTitle(props.doctype, props.id, props.title)
  else requestTitles(props.doctype, [props.id])
})

const display = computed(() => props.title || recordTitle(props.doctype, props.id) || props.id)
</script>

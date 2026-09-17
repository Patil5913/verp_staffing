<template>
  <NestedPopover>
    <template #target="{ open }">
      <div
        class="flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1 text-p-sm transition-colors"
        :class="
          open
            ? 'border-app-primary bg-app-primary-tint text-app-primary'
            : 'border-app-border bg-app-panel-2 text-app-text hover:border-app-text-muted'
        "
      >
        <span class="max-w-[200px] truncate">{{ summary }}</span>
        <button
          type="button"
          class="text-app-text-muted hover:text-red-600"
          @click.stop="$emit('remove')"
        >
          <FeatherIcon name="x" class="h-3 w-3" />
        </button>
      </div>
    </template>
    <template #body>
      <div class="my-2 w-64 rounded-xl border border-app-border bg-app-panel p-3 shadow-xl">
        <DocFilterRow :filter="filter" :docfields="docfields" />
      </div>
    </template>
  </NestedPopover>
</template>

<script setup>
import { computed } from 'vue'
import { FeatherIcon, NestedPopover } from 'frappe-ui'
import DocFilterRow from './DocFilterRow.vue'
import { describeFilter } from '@/utils/list/filterOperators'

const props = defineProps({
  filter: { type: Object, required: true },
  docfields: { type: Array, required: true },
})
defineEmits(['remove'])

const summary = computed(() => describeFilter(props.filter))
</script>

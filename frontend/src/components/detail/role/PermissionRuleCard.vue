<template>
  <div class="group flex flex-col gap-2 rounded-lg border border-app-border bg-app-panel px-3 py-2">
    <div class="flex items-start justify-between gap-2">
      <p class="text-p-sm font-medium text-app-text">
        <slot name="title">{{ row.parent }}</slot>
        <span class="text-p-xs font-normal text-app-text-muted">
          · Level {{ row.permlevel }}<span v-if="row.if_owner"> · Only if creator</span>
        </span>
      </p>
      <slot name="actions" />
    </div>
    <div class="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
      <label v-for="pt in PTYPES" :key="pt" class="flex items-center gap-2" :class="canWrite ? 'cursor-pointer' : 'opacity-70'">
        <AppCheckbox :model-value="!!row[pt]" :disabled="!canWrite" @update:model-value="emit('toggle', row, pt)" />
        <span class="text-p-sm capitalize text-app-text">{{ pt }}</span>
      </label>
    </div>
  </div>
</template>

<script setup>
import AppCheckbox from '@/components/ui/AppCheckbox.vue'

defineProps({
  row: { type: Object, required: true },
  canWrite: { type: Boolean, default: false },
})
const emit = defineEmits(['toggle'])

const PTYPES = ['read', 'write', 'create', 'delete', 'submit', 'cancel', 'amend', 'report', 'export', 'import', 'share', 'print', 'email', 'select']
</script>

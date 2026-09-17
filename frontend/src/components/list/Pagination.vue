<template>
  <div class="flex items-center gap-1">
    <Button
      variant="outline"
      icon="chevron-left"
      :disabled="page <= 1"
      @click="$emit('update:page', page - 1)"
    />
    <span class="px-2 text-p-base text-app-text-muted">
      Page {{ page }} of {{ pageCount }}
    </span>
    <Button
      variant="outline"
      icon="chevron-right"
      :disabled="page >= pageCount"
      @click="$emit('update:page', page + 1)"
    />
  </div>
</template>

<script setup>
import { Button } from 'frappe-ui'

defineProps({
  page: { type: Number, required: true },
  pageCount: { type: Number, required: true },
})
defineEmits(['update:page'])
</script>

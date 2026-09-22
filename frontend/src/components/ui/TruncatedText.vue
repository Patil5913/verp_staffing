<template>
  <span v-if="!isLong" class="truncate">{{ text }}</span>
  <span v-else class="inline-flex max-w-full flex-col gap-0.5">
    <span :class="expanded ? '' : 'truncate'">{{ text }}</span>
    <button
      type="button"
      class="w-fit shrink-0 text-p-xs font-medium text-app-primary hover:underline"
      @click.stop="expanded = !expanded"
    >
      {{ expanded ? 'View less' : 'View more' }}
    </button>
  </span>
</template>

<script setup>
// A long field value (a course description, an interview round's feedback,
// ...) rendered in a tight card/grid cell — plain CSS truncate cuts it off
// with no way back to the full text short of opening an edit dialog. This
// adds the missing expand/collapse.
import { computed, ref } from 'vue'

const props = defineProps({
  text: { type: String, default: '' },
  limit: { type: Number, default: 120 },
})

const isLong = computed(() => props.text.length > props.limit)
const expanded = ref(false)
</script>

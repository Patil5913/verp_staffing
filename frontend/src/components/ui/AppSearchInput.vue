<template>
  <div class="relative flex min-w-0 items-center" :class="$attrs.class" :style="$attrs.style">
    <span class="lucide-search pointer-events-none absolute left-3 size-4 text-app-text-muted" />
    <input
      v-bind="inputAttrs"
      :value="modelValue"
      type="text"
      :placeholder="placeholder"
      class="w-full min-w-0 rounded-lg border border-app-border bg-app-panel pl-9 text-p-sm text-app-text outline-none transition-colors placeholder:text-app-text-muted focus:border-app-primary focus:ring-2 focus:ring-app-primary/20"
      :class="[compact ? 'h-8' : 'h-9', $slots.suffix ? 'pr-9' : 'pr-3']"
      @input="emit('update:modelValue', $event.target.value)"
    />
    <div v-if="$slots.suffix" class="absolute right-3 flex items-center"><slot name="suffix" /></div>
  </div>
</template>

<script setup>
import { computed, useAttrs } from 'vue'

// Search box with the magnifier prefix used in every toolbar. The `suffix`
// slot holds an optional trailing widget (e.g. a syntax-help popover).
defineOptions({ inheritAttrs: false })
defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: 'Search' },
  compact: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const attrs = useAttrs()
const inputAttrs = computed(() => {
  const { class: _c, style: _s, ...rest } = attrs
  return rest
})
</script>

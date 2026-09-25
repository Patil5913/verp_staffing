<template>
  <div class="flex min-w-0 flex-col gap-1.5" :class="$attrs.class" :style="$attrs.style">
    <label v-if="label" class="text-p-sm font-medium text-app-text-muted">
      {{ label }}<span v-if="required" class="text-red-600"> *</span>
    </label>
    <textarea
      ref="el"
      v-bind="textareaAttrs"
      v-model="model"
      :rows="rows"
      :placeholder="placeholder"
      :disabled="disabled"
      class="w-full min-w-0 text-app-text placeholder:text-app-text-muted disabled:cursor-not-allowed disabled:opacity-60"
      :class="bare ? 'resize-none bg-transparent outline-none placeholder:text-app-text-muted' : [
        'resize-y rounded-lg border bg-app-panel px-3 py-2 outline-none transition-colors focus:border-app-primary focus:ring-2 focus:ring-app-primary/20',
        error ? 'border-red-500' : 'border-app-border',
      ]"
    />
    <p v-if="error" class="text-p-xs text-red-600">{{ error }}</p>
  </div>
</template>

<script setup>
import { computed, ref, useAttrs } from 'vue'

// Multi-line counterpart of AppInput (Small Text / Text fields).
defineOptions({ inheritAttrs: false })
const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  error: { type: String, default: '' },
  rows: { type: Number, default: 3 },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  // No border/background - for a textarea that sits inside a composer card.
  bare: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const el = ref(null)
const attrs = useAttrs()
const textareaAttrs = computed(() => {
  const { class: _c, style: _s, ...rest } = attrs
  return rest
})
defineExpose({ el, focus: () => el.value?.focus() })

const model = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
</script>


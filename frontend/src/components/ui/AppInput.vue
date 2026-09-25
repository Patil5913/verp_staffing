<template>
  <AppTextarea
    v-if="type === 'textarea'"
    v-bind="$attrs"
    :model-value="modelValue ?? ''"
    :label="label"
    :placeholder="placeholder"
    :error="error"
    :required="required"
    :disabled="disabled"
    @update:model-value="(v) => emit('update:modelValue', v)"
  />
  <AppDatePicker
    v-else-if="type === 'date' || type === 'datetime-local'"
    v-bind="$attrs"
    :model-value="String(modelValue ?? '')"
    :mode="type === 'date' ? 'date' : 'datetime'"
    :label="label"
    :placeholder="placeholder || (type === 'date' ? 'Select date' : 'Select date & time')"
    :error="error"
    :required="required"
    :disabled="disabled"
    :compact="compact"
    @update:model-value="(v) => emit('update:modelValue', v)"
  />
  <AppCombobox
    v-else-if="type === 'select'"
    v-bind="$attrs"
    :model-value="modelValue ?? ''"
    :label="label"
    :options="options"
    :placeholder="placeholder || 'Select'"
    :required="required"
    :disabled="disabled"
    @update:model-value="(v) => emit('update:modelValue', v)"
  />
  <div v-else class="flex min-w-0 flex-col gap-1.5" :class="$attrs.class" :style="$attrs.style">
    <label v-if="label" class="text-p-sm font-medium text-app-text-muted">
      {{ label }}<span v-if="required" class="text-red-600"> *</span>
    </label>
    <div class="relative">
      <!-- e.g. the currency symbol of an amount field -->
      <span v-if="prefix" class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-p-sm font-medium text-app-text-muted" :title="prefixTitle">{{ prefix }}</span>
      <input
        ref="el"
        v-bind="inputAttrs"
        :value="modelValue ?? ''"
        :type="isPassword && revealed ? 'text' : type"
        :placeholder="placeholder"
        :disabled="disabled"
        class="w-full min-w-0 text-p-sm text-app-text placeholder:text-app-text-muted outline-none disabled:cursor-not-allowed disabled:opacity-60"
        :class="bare ? 'bg-transparent' : [
          'rounded-lg border bg-app-panel transition-colors focus:border-app-primary focus:ring-2 focus:ring-app-primary/20',
          error ? 'border-red-500' : 'border-app-border',
          compact ? 'h-8' : 'h-9',
          prefix ? (prefix.length > 2 ? 'pl-10 pr-3' : 'pl-7 pr-3') : (compact ? 'px-2' : 'px-3'),
          isPassword ? '!pr-9' : '',
        ]"
        @input="emit('update:modelValue', $event.target.value)"
      />
      <!-- Password fields: an eye to show / hide what was typed. -->
      <button
        v-if="isPassword"
        type="button"
        tabindex="-1"
        class="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-app-text-muted transition-colors hover:text-app-text disabled:cursor-not-allowed"
        :disabled="disabled"
        :title="revealed ? 'Hide password' : 'Show password'"
        :aria-label="revealed ? 'Hide password' : 'Show password'"
        @click="revealed = !revealed"
      >
        <span v-if="revealed" class="lucide-eye-off size-4" />
        <span v-else class="lucide-eye size-4" />
      </button>
    </div>
    <p v-if="error" class="text-p-xs text-red-600">{{ error }}</p>
    <p v-else-if="hint || description" class="text-p-xs text-app-text-muted">{{ hint || description }}</p>
  </div>
</template>

<script setup>
import { computed, ref, useAttrs } from 'vue'
import AppTextarea from './AppTextarea.vue'
import AppDatePicker from './AppDatePicker.vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'

// The app's single control for text-like fields: text, number, date,
// datetime-local, email, password - plus `textarea`, `select` and `date` /
// `datetime-local`, which delegate to AppTextarea / AppCombobox / AppDatePicker so a form can drive every field
// through one component. Emits the raw string, like the input itself.
defineOptions({ inheritAttrs: false })
const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  type: { type: String, default: 'text' },
  label: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  hint: { type: String, default: '' },
  description: { type: String, default: '' },
  error: { type: String, default: '' },
  required: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  // No border/background - for an input inside a chip box or overlay row.
  bare: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  // select only: [{ label, value }] or plain strings.
  options: { type: Array, default: () => [] },
  prefix: { type: String, default: '' },
  prefixTitle: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const el = ref(null)
const isPassword = computed(() => props.type === 'password')
const revealed = ref(false)
defineExpose({ focus: () => el.value?.focus() })

// class/style belong to the wrapper; everything else (autocomplete, name,
// min/max, ...) belongs on the <input>.
const attrs = useAttrs()
const inputAttrs = computed(() => {
  const { class: _c, style: _s, ...rest } = attrs
  return rest
})
</script>

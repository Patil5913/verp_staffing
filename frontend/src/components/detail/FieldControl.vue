<template>
  <div v-if="field.fieldtype === 'Link'" class="app-link-field flex flex-col gap-1.5">
    <Link
      :label="field.label"
      :doctype="field.options"
      :model-value="modelValue || ''"
      :disabled="disabled"
      @update:model-value="(v) => emit('update:modelValue', v)"
    />
    <p v-if="error" class="text-p-xs text-red-600">{{ error }}</p>
  </div>

  <label v-else-if="controlType === 'checkbox'" class="flex items-center gap-2 pt-6">
    <input
      type="checkbox"
      class="h-4 w-4 rounded border-app-border text-app-primary accent-app-primary focus:outline-none focus:ring-2 focus:ring-app-primary/30 disabled:cursor-not-allowed disabled:opacity-60"
      :checked="Boolean(modelValue)"
      :disabled="disabled"
      @change="(e) => emit('update:modelValue', e.target.checked)"
    />
    <span class="text-p-sm text-app-text">{{ field.label }}</span>
  </label>

  <div v-else class="flex flex-col gap-1.5">
    <label v-if="field.label" class="text-p-sm font-medium text-app-text-muted">{{ field.label }}</label>

    <textarea
      v-if="controlType === 'textarea'"
      :class="[fieldInputClasses, 'resize-none']"
      rows="3"
      :value="displayValue ?? ''"
      :disabled="disabled"
      :placeholder="placeholder"
      @input="(e) => onInput(e.target.value)"
    />
    <select
      v-else-if="controlType === 'select'"
      :class="fieldInputClasses"
      :value="displayValue ?? ''"
      :disabled="disabled"
      @change="(e) => onInput(e.target.value)"
    >
      <option value="" disabled hidden>{{ placeholder || 'Select an option' }}</option>
      <option v-for="opt in selectOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
    </select>
    <input
      v-else
      :class="fieldInputClasses"
      :type="controlType"
      :value="displayValue ?? ''"
      :disabled="disabled"
      :placeholder="placeholder"
      @input="(e) => onInput(e.target.value)"
    />

    <p v-if="error" class="text-p-xs text-red-600">{{ error }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Link } from 'frappe-ui/frappe'
import {
  isEmailField,
  isMonthYearField,
  isPhoneField,
  toMonthYear,
  fromMonthYear,
  validateFieldValue,
} from '@/utils/detail/fieldFormats'

const props = defineProps({
  field: { type: Object, required: true },
  modelValue: { default: null },
  disabled: { type: Boolean, default: false },
  showErrors: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const TYPE_MAP = {
  Data: 'text',
  'Small Text': 'textarea',
  'Long Text': 'textarea',
  'Text Editor': 'textarea',
  Code: 'textarea',
  JSON: 'textarea',
  Int: 'number',
  Float: 'number',
  Currency: 'number',
  Percent: 'number',
  Duration: 'number',
  Rating: 'number',
  Check: 'checkbox',
  Select: 'select',
  Date: 'date',
  Datetime: 'datetime-local',
}

const controlType = computed(() => {
  if (isEmailField(props.field.fieldname)) return 'email'
  if (isPhoneField(props.field.fieldname) || isMonthYearField(props.field.fieldname)) return 'text'
  return TYPE_MAP[props.field.fieldtype] || 'text'
})

const placeholder = computed(() => {
  if (isMonthYearField(props.field.fieldname)) return 'MM-YYYY'
  if (isPhoneField(props.field.fieldname)) return 'Exp: +1xxxxxxxxxx'
  return undefined
})

const displayValue = computed(() => {
  if (isMonthYearField(props.field.fieldname)) return toMonthYear(props.modelValue)
  return props.modelValue
})

function onInput(value) {
  if (isMonthYearField(props.field.fieldname)) {
    emit('update:modelValue', fromMonthYear(value))
    return
  }
  emit('update:modelValue', value)
}

const selectOptions = computed(() => {
  if (props.field.fieldtype !== 'Select') return []
  return (props.field.options || '').split('\n').filter(Boolean).map((v) => ({ label: v, value: v }))
})

const error = computed(() => {
  if (!props.showErrors) return ''
  return validateFieldValue(props.field, props.modelValue)
})

// This app's own field styling, in place of frappe-ui's stock gray form
// inputs — matches AppButton's rounded, app-token-driven look so a detail
// form reads as this product's UI rather than an embedded Frappe form.
const fieldInputClasses =
  'w-full rounded-lg border border-app-border bg-app-panel px-3 py-1.5 text-p-sm text-app-text ' +
  'placeholder:text-app-text-muted transition-colors focus:border-app-primary focus:outline-none ' +
  'focus:ring-2 focus:ring-app-primary/20 disabled:cursor-not-allowed disabled:opacity-60'

defineExpose({ error })
</script>

<style scoped>
/* Reskins frappe-ui's Link/Combobox trigger to match the plain fields'
   Tailwind classes above — Link doesn't expose a class prop for its
   internal input, so this targets its own data-slot hooks instead. */
.app-link-field :deep(label) {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--app-text-muted);
}

.app-link-field :deep([data-slot='trigger']) {
  border-radius: 0.5rem;
  border: 1px solid var(--app-border);
  background-color: var(--app-panel);
  box-shadow: none;
}

.app-link-field :deep([data-slot='trigger']:focus-within) {
  border-color: var(--app-primary);
  box-shadow: 0 0 0 2px var(--app-primary-tint);
}

.app-link-field :deep([data-slot='input']) {
  color: var(--app-text);
  background-color: transparent;
}

.app-link-field :deep([data-slot='content-body']) {
  background-color: var(--app-panel);
  border: 1px solid var(--app-border);
}
</style>

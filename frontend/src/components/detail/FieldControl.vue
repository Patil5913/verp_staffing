<template>
  <Link
    v-if="field.fieldtype === 'Link'"
    :label="field.label"
    :doctype="field.options"
    :model-value="modelValue || ''"
    :disabled="disabled"
    @update:model-value="(v) => emit('update:modelValue', v)"
  />
  <div v-else class="flex flex-col gap-1.5" :class="controlType === 'checkbox' ? 'pt-6' : ''">
    <FormControl
      :type="controlType"
      :label="field.label"
      :model-value="displayValue"
      :options="selectOptions"
      :disabled="disabled"
      :placeholder="placeholder"
      @update:model-value="onInput"
    />
    <p v-if="error" class="text-p-xs text-red-600">{{ error }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { FormControl } from 'frappe-ui'
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
  if (props.field.fieldtype !== 'Select') return undefined
  return (props.field.options || '').split('\n').filter(Boolean).map((v) => ({ label: v, value: v }))
})

const error = computed(() => {
  if (!props.showErrors) return ''
  return validateFieldValue(props.field, props.modelValue)
})

defineExpose({ error })
</script>

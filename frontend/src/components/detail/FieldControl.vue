<template>
  <div v-if="field.fieldtype === 'Link'" class="flex flex-col gap-1.5">
    <AppLinkField
      :label="field.label"
      :doctype="field.options"
      :query="linkQuery?.query"
      :filters="linkQuery?.filters"
      :model-value="modelValue || ''"
      :disabled="disabled"
      @update:model-value="(v) => emit('update:modelValue', v)"
    />
    <p v-if="error" class="text-p-xs text-red-600">{{ error }}</p>
  </div>

  <div v-else-if="controlType === 'checkbox'" class="pt-6">
    <Checkbox
      :label="field.label"
      :model-value="Boolean(modelValue)"
      :disabled="disabled"
      @update:model-value="(v) => emit('update:modelValue', v)"
    />
  </div>

  <div v-else-if="controlType === 'attach'" class="flex flex-col gap-1.5">
    <label v-if="field.label" class="text-p-sm font-medium text-app-text-muted">{{ field.label }}</label>
    <div class="flex items-center gap-3">
      <img
        v-if="field.fieldtype === 'Attach Image' && modelValue"
        :src="modelValue"
        class="h-10 w-10 shrink-0 rounded-md border border-app-border object-cover"
      />
      <a
        v-else-if="modelValue"
        :href="modelValue"
        target="_blank"
        rel="noopener"
        class="min-w-0 truncate text-p-sm text-app-primary hover:underline"
      >
        {{ attachFileName }}
      </a>
      <span v-else class="text-p-sm text-app-text-muted">No file attached</span>

      <FileUploader v-if="!disabled" @success="(f) => emit('update:modelValue', f.file_url)">
        <template #default="{ uploading, progress, openFileSelector }">
          <AppButton variant="outline" size="sm" :loading="uploading" @click="openFileSelector">
            {{ uploading ? `Uploading ${progress}%` : modelValue ? 'Replace' : 'Upload' }}
          </AppButton>
        </template>
      </FileUploader>
      <AppButton
        v-if="!disabled && modelValue"
        variant="ghost"
        size="icon"
        icon="x"
        @click="clearFile"
      />
    </div>
  </div>

  <div v-else class="flex flex-col gap-1.5">
    <label v-if="field.label" class="text-p-sm font-medium text-app-text-muted">{{ field.label }}</label>

    <textarea
      v-if="controlType === 'textarea'"
      :class="[fieldInputClasses, 'h-auto resize-none py-1.5']"
      rows="3"
      :value="displayValue ?? ''"
      :disabled="disabled"
      :placeholder="placeholder"
      @input="(e) => onInput(e.target.value)"
    />
    <AppCombobox
      v-else-if="controlType === 'select'"
      :model-value="String(displayValue ?? '')"
      :options="selectOptions"
      :disabled="disabled"
      :placeholder="placeholder || 'Select an option'"
      @update:model-value="onInput"
    />
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
import { Checkbox, FileUploader } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import AppCombobox from '@/components/common/AppCombobox.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
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
  // { query?, filters? } for a Link field — a whitelisted standard query and/or
  // filters, like the desk's frm.set_query(fieldname, ...).
  linkQuery: { type: Object, default: null },
  // Optional async (fieldname) => boolean for a file the server should delete
  // straight away (Lead Detail Form, as on the desk) instead of just clearing
  // the field until the next Save. Resolve false to keep the file.
  removeFile: { type: Function, default: null },
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
  Attach: 'attach',
  'Attach Image': 'attach',
  Password: 'password',
}

async function clearFile() {
  if (props.removeFile && !(await props.removeFile(props.field.fieldname))) return
  emit('update:modelValue', '')
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

const attachFileName = computed(() => (props.modelValue || '').split('/').pop())

const selectOptions = computed(() => {
  if (props.field.fieldtype !== 'Select') return []
  const raw = (props.field.options || '').split('\n')
  const options = raw.filter(Boolean).map((v) => ({ label: v, value: v }))
  // A leading blank line is Frappe's "may be left empty" — offer that choice,
  // so a filter or optional Select can be cleared again once picked.
  return raw[0] === '' && raw.length > 1 ? [{ label: '—', value: '' }, ...options] : options
})

const error = computed(() => {
  if (!props.showErrors) return ''
  return validateFieldValue(props.field, props.modelValue)
})

// This app's own field styling, in place of frappe-ui's stock gray form
// inputs — matches AppButton's rounded, app-token-driven look so a detail
// form reads as this product's UI rather than an embedded Frappe form.
const fieldInputClasses =
  'w-full h-9 rounded-lg border border-app-border bg-app-panel px-3 text-p-sm text-app-text ' +
  'placeholder:text-app-text-muted transition-colors focus:border-app-primary focus:outline-none ' +
  'focus:ring-2 focus:ring-app-primary/20 disabled:cursor-not-allowed disabled:opacity-60'

defineExpose({ error })
</script>

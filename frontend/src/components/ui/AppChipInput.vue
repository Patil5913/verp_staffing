<template>
  <div class="flex min-w-0 flex-col gap-1.5">
    <label v-if="label" class="text-p-sm font-medium text-app-text-muted">{{ label }}</label>
    <div class="flex flex-wrap items-center gap-1.5">
      <span
        v-for="chip in modelValue"
        :key="chip"
        class="inline-flex items-center gap-1.5 rounded-lg border border-blue-700 bg-blue-600 py-1 pl-2.5 pr-1.5 text-p-sm font-medium text-white shadow-sm"
      >
        {{ chip }}
        <button v-if="!disabled" type="button" class="rounded-full p-0.5 text-blue-100 hover:bg-blue-800 hover:text-white" @click="remove(chip)">
          <FeatherIcon name="x" class="h-3.5 w-3.5" />
        </button>
      </span>

      <AppCombobox
        v-if="!disabled && options.length"
        compact
        class="w-40"
        model-value=""
        :placeholder="placeholder"
        :options="available"
        @update:model-value="add"
      />
      <AppInput
        v-else-if="!disabled"
        v-model="draft"
        compact
        class="w-40"
        :placeholder="placeholder"
        :error="error ? ' ' : ''"
        @keydown="onKey"
        @blur="addDraft"
      />
    </div>
    <p v-if="error" class="text-p-xs text-red-600">{{ error }}</p>
    <p v-else-if="hint" class="text-p-xs text-app-text-muted">{{ hint }}</p>
  </div>
</template>

<script setup>
// Chip multi-select: pick from `options` (a searchable list), or - with no
// options - type a value and press Enter. `validate(value)` returns an error
// message (or '') for typed values; duplicates are always rejected.
import { computed, ref } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import AppCombobox from '@/components/ui/AppCombobox.vue'
import AppInput from '@/components/ui/AppInput.vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  options: { type: Array, default: () => [] },
  label: { type: String, default: '' },
  hint: { type: String, default: '' },
  placeholder: { type: String, default: '+ Add' },
  disabled: { type: Boolean, default: false },
  validate: { type: Function, default: null },
  normalize: { type: Function, default: (v) => v.trim() },
})
const emit = defineEmits(['update:modelValue'])

const draft = ref('')
const error = ref('')
const available = computed(() => props.options.filter((o) => !props.modelValue.includes(typeof o === 'string' ? o : o.value)))

function add(value) {
  if (!value || props.modelValue.includes(value)) return
  emit('update:modelValue', [...props.modelValue, value])
}
function addDraft() {
  const value = props.normalize(draft.value || '')
  if (!value) {
    error.value = ''
    return
  }
  const problem = props.modelValue.includes(value) ? `"${value}" is already added` : props.validate?.(value) || ''
  error.value = problem
  if (problem) return
  add(value)
  draft.value = ''
}
function onKey(e) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addDraft()
  }
}
function remove(chip) {
  emit('update:modelValue', props.modelValue.filter((c) => c !== chip))
}
</script>

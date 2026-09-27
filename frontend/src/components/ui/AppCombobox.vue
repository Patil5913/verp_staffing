<template>
  <div class="flex min-w-0 flex-col gap-1.5">
    <label v-if="label" class="text-p-sm font-medium text-app-text-muted">
      {{ label }}<span v-if="required" class="text-red-600"> *</span>
    </label>
    <Combobox
      v-model="model"
      class="app-combobox"
      :class="{ 'app-combobox--compact': compact }"
      :options="options"
      :placeholder="placeholder"
      :disabled="disabled"
      trigger="button"
    />
  </div>
</template>

<script setup>
// AppLinkField's look for a fixed, already-known list of options (a period
// preset, a status) - AppLinkField itself searches a doctype on the server.
// `compact` is the 28px control used in toolbars.
import { computed } from 'vue'
import { Combobox } from 'frappe-ui'

const props = defineProps({
  modelValue: { type: String, default: '' },
  // [{ label, value }] - or plain strings, which are used for both.
  options: { type: Array, default: () => [] },
  label: { type: String, default: '' },
  required: { type: Boolean, default: false },
  placeholder: { type: String, default: 'Select' },
  disabled: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const model = computed({
  get: () => props.modelValue || '',
  // Combobox reports null when the selection is cleared; keep the last value.
  set: (value) => value && emit('update:modelValue', value),
})

const options = computed(() => props.options.map((o) => (typeof o === 'string' ? { label: o, value: o } : o)))
</script>

<style>
/* Not scoped: the trigger button is the Combobox's own (renderless) root, which
   never gets this component's scope attribute. */
.app-combobox {
  box-sizing: border-box;
  height: 2rem;
  min-height: 0;
  width: 100%;
  min-width: 0;
  border-radius: 0.5rem;
  border: 1px solid var(--app-border);
  background-color: var(--app-panel);
  padding: 0 0.75rem;
  box-shadow: none;
  color: var(--app-text);
  font-size: 13px;
}

.app-combobox:focus-within,
.app-combobox[data-state='open'] {
  border-color: var(--app-primary);
  box-shadow: 0 0 0 2px var(--app-primary-tint);
}

.app-combobox--compact {
  height: 1.75rem;
  border-radius: 0.5rem;
  padding: 0 0.5rem;
}
</style>

<template>
  <div class="flex min-w-0 flex-col gap-1.5">
    <label v-if="label" class="text-p-sm font-medium text-app-text-muted">{{ label }}</label>
    <div class="flex gap-2" :class="muted ? 'opacity-50' : ''">
      <AppInput
        class="w-28 shrink-0"
        type="number"
        min="0"
        :disabled="disabled"
        :error="error ? ' ' : ''"
        :model-value="amount"
        @update:model-value="onAmount"
      />
      <AppCombobox class="w-36" :disabled="disabled" :model-value="unit" :options="unitOptions" @update:model-value="onUnit" />
    </div>
    <p v-if="error" class="text-p-xs text-red-600">{{ error }}</p>
    <p v-else-if="hint" class="text-p-xs text-app-text-muted">{{ hint }}</p>
  </div>
</template>

<script setup>
// value + unit instead of a raw "48:00" / "1200" string. The stored value
// keeps whatever format the field already used, so no backend change:
//   storage="hhmm"    -> "HH:MM" text (agreement expiry, session expiry)
//   storage="seconds" -> whole seconds (reset-link expiry)
// `muted` only greys it out - the stored value is left alone and still saved.
import { computed, ref, watch } from 'vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'

const UNIT_MINUTES = { Minutes: 1, Hours: 60, Days: 1440 }

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  storage: { type: String, default: 'hhmm' }, // hhmm | seconds
  units: { type: Array, default: () => ['Minutes', 'Hours'] },
  label: { type: String, default: '' },
  hint: { type: String, default: '' },
  error: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  muted: { type: Boolean, default: false },
  // the unit the value was saved with, when the record keeps one; otherwise it is worked out from the value
  unit: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'update:unit'])

const unitOptions = computed(() => props.units)

function toMinutes(raw) {
  if (raw === '' || raw == null) return 0
  if (props.storage === 'seconds') return Math.round(Number(raw) / 60) || 0
  const [h, m] = String(raw).split(':')
  return (parseInt(h, 10) || 0) * 60 + (parseInt(m, 10) || 0)
}
function fromMinutes(min) {
  if (props.storage === 'seconds') return String(min * 60)
  return `${String(Math.floor(min / 60)).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}`
}
function bestUnit(min) {
  const usable = [...props.units].sort((a, b) => UNIT_MINUTES[b] - UNIT_MINUTES[a])
  return usable.find((u) => min > 0 && min % UNIT_MINUTES[u] === 0) || props.units[0]
}

const amount = ref('')
const unit = ref(props.units[0])
let lastEmitted = null

function syncFromModel() {
  const min = toMinutes(props.modelValue)
  unit.value = props.units.includes(props.unit) ? props.unit : bestUnit(min)
  amount.value = props.modelValue === '' || props.modelValue == null ? '' : String(min / UNIT_MINUTES[unit.value])
}
syncFromModel()
watch(
  () => props.modelValue,
  (v) => {
    if (String(v) !== lastEmitted) syncFromModel()
  },
)

function push() {
  if (amount.value === '') {
    lastEmitted = ''
    emit('update:modelValue', '')
    return
  }
  const out = fromMinutes(Math.max(0, Math.round(Number(amount.value) * UNIT_MINUTES[unit.value])))
  lastEmitted = out
  emit('update:modelValue', out)
}
function onAmount(v) {
  amount.value = v
  push()
}
function onUnit(u) {
  unit.value = u
  emit('update:unit', u)
  push()
}
</script>

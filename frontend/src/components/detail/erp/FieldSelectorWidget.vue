<template>
  <div class="flex flex-col gap-4">
    <div class="rounded-lg border border-app-border bg-app-panel-2 p-4">
      <h4 class="text-p-base font-medium text-app-text">{{ title }}</h4>
      <p class="mt-1 text-p-sm text-app-text-muted" v-html="description" />
      <p class="mt-2 text-p-xs font-medium text-app-primary">{{ impact }}</p>
    </div>

    <div class="grid grid-cols-1 gap-4 md:grid-cols-[220px_1fr]">
      <!-- Item picker -->
      <div class="flex flex-col gap-1.5">
        <div class="text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">
          Choose a {{ selectorLabel }}
        </div>
        <button
          v-for="item in itemsList"
          :key="item"
          type="button"
          class="flex items-center justify-between rounded-lg border px-3 py-2 text-left text-p-sm transition-colors"
          :class="
            item === currentItem
              ? 'border-app-primary bg-app-primary-tint text-app-text'
              : 'border-app-border bg-app-panel text-app-text hover:border-app-primary/40'
          "
          @click="currentItem = item"
        >
          <span class="truncate">{{ item }}</span>
          <span class="shrink-0 text-p-xs text-app-text-muted">{{ fieldCount(item) }}</span>
        </button>
      </div>

      <!-- Field picker -->
      <div v-if="!currentItem" class="flex items-center justify-center rounded-lg border border-dashed border-app-border p-10 text-p-sm text-app-text-muted">
        Select a {{ selectorLabel }} to configure its fields.
      </div>

      <div v-else class="flex flex-col gap-4 rounded-lg border border-app-border bg-app-panel p-4">
        <div v-if="isCandidateForm" class="flex flex-col gap-2 border-b border-app-border pb-4">
          <div class="text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">Service Options</div>
          <AppCheckbox
            label="Is Agreement Required"
            :disabled="disabled"
            :model-value="getFlag(currentItem, 'is_agreement_required')"
            @update:model-value="(v) => setFlag(currentItem, 'is_agreement_required', v)"
          />
          <AppCheckbox
            label="Is Candidate Form Required"
            :disabled="disabled"
            :model-value="getFlag(currentItem, 'is_candidate_form_required')"
            @update:model-value="(v) => setFlag(currentItem, 'is_candidate_form_required', v)"
          />
        </div>

        <div class="flex items-center gap-2">
          <AppSearchInput v-model="search" compact placeholder="Search fields…" class="flex-1" />
          <AppButton variant="outline" size="sm" :disabled="disabled" @click="toggleSelectAll">
            {{ allSelected ? 'Deselect all' : 'Select all' }}
          </AppButton>
          <AppButton v-if="copyableItems.length" variant="outline" size="sm" :disabled="disabled" @click="showCopyDialog = true">
            Copy Fields From
          </AppButton>
          <span class="shrink-0 text-p-xs text-app-text-muted">{{ getFields(currentItem).length }} selected</span>
        </div>

        <div class="flex max-h-96 flex-col gap-4 overflow-y-auto">
          <div v-for="section in filteredSections" :key="section.label" class="flex flex-col gap-1.5">
            <div class="text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">{{ section.label }}</div>
            <div class="grid grid-cols-1 gap-1 sm:grid-cols-2">
              <div
                v-for="field in section.fields"
                :key="field.fieldname"
                class="flex items-center justify-between gap-2 rounded-md px-2 py-1"
                :class="isFieldSelected(currentItem, field.fieldname) ? 'bg-app-panel-2' : ''"
              >
                <AppCheckbox
                  :label="field.label"
                  :disabled="disabled"
                  :model-value="isFieldSelected(currentItem, field.fieldname)"
                  @update:model-value="(v) => toggleFieldSelected(currentItem, field.fieldname, v)"
                />
                <AppCheckbox
                  v-if="isCandidateForm && isFieldSelected(currentItem, field.fieldname)"
                  label="Required"
                  class="shrink-0 !text-p-xs"
                  :disabled="disabled"
                  :model-value="isFieldRequired(currentItem, field.fieldname)"
                  @update:model-value="(v) => setFieldRequired(currentItem, field.fieldname, v)"
                />
              </div>
            </div>
          </div>
          <p v-if="!filteredSections.length" class="py-6 text-center text-p-sm text-app-text-muted">
            No fields match "{{ search }}"
          </p>
        </div>
      </div>
    </div>
  </div>

  <Dialog v-model="showCopyDialog" :options="{ title: `Copy Fields to ${currentItem}` }">
    <template #body-content>
      <p class="mb-3 text-p-sm text-app-text-muted">
        Copying will replace all fields and settings configured for <strong>{{ currentItem }}</strong> with the
        fields from the selected {{ selectorLabel }}.
      </p>
      <FieldControl :field="copySourceField" v-model="copySource" show-errors />
    </template>
    <template #actions>
      <AppButton :disabled="!copySource" @click="copyFrom">Copy &amp; Replace</AppButton>
    </template>
  </Dialog>
</template>

<script setup>
import AppSearchInput from '@/components/ui/AppSearchInput.vue'
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
// Ports the old desk render_field_selector_widget() (ERP Configuration's
// Candidate Form Fields / Department Display Fields / Department Access
// Fields tabs) onto this app's own components — same CONFIG shape (a JSON
// object keyed by item name, either a plain array of fieldnames or, for
// the candidate form, { fields: [{field_name, is_required}],
// is_agreement_required, is_candidate_form_required }), same search/
// select-all/copy-from behavior — just Checkbox/AppButton/Dialog instead
// of hand-built gradient HTML.
import { computed, ref, watch } from 'vue'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import FieldControl from '@/components/detail/FieldControl.vue'

const props = defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  impact: { type: String, default: '' },
  selectorLabel: { type: String, default: 'item' },
  itemsList: { type: Array, required: true },
  isCandidateForm: { type: Boolean, default: false },
  fieldSections: { type: Array, default: () => [] },
  modelValue: { type: Object, default: () => ({}) },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const localConfig = ref({})
watch(
  () => props.modelValue,
  (val) => {
    localConfig.value = JSON.parse(JSON.stringify(val || {}))
  },
  { immediate: true, deep: true },
)
function emitUpdate() {
  emit('update:modelValue', JSON.parse(JSON.stringify(localConfig.value)))
}

const currentItem = ref('')
const search = ref('')

function normalizeEntry(name) {
  if (!props.isCandidateForm) return
  const entry = localConfig.value[name]
  if (!entry) return
  if (Array.isArray(entry)) {
    localConfig.value[name] = { fields: entry, is_agreement_required: false, is_candidate_form_required: false }
  }
  const cur = localConfig.value[name]
  if (!Array.isArray(cur.fields)) cur.fields = []
  cur.fields = cur.fields
    .map((f) => (typeof f === 'string' ? { field_name: f, is_required: false } : { field_name: f.field_name, is_required: !!f.is_required }))
    .filter((f) => f.field_name)
}

function getFieldObjects(name) {
  if (!props.isCandidateForm) return []
  normalizeEntry(name)
  return localConfig.value[name]?.fields || []
}
function getFields(name) {
  if (props.isCandidateForm) return getFieldObjects(name).map((f) => f.field_name)
  return localConfig.value[name] || []
}
function isFieldSelected(name, fieldname) {
  return getFields(name).includes(fieldname)
}
function isFieldRequired(name, fieldname) {
  if (!props.isCandidateForm) return false
  return !!getFieldObjects(name).find((f) => f.field_name === fieldname)?.is_required
}
function toggleFieldSelected(name, fieldname, selected) {
  if (props.isCandidateForm) {
    if (!localConfig.value[name]) localConfig.value[name] = { fields: [], is_agreement_required: false, is_candidate_form_required: false }
    normalizeEntry(name)
    const cur = localConfig.value[name].fields
    if (selected) {
      if (!cur.some((f) => f.field_name === fieldname)) cur.push({ field_name: fieldname, is_required: false })
    } else {
      localConfig.value[name].fields = cur.filter((f) => f.field_name !== fieldname)
    }
  } else {
    const cur = localConfig.value[name] || []
    localConfig.value[name] = selected ? [...new Set([...cur, fieldname])] : cur.filter((f) => f !== fieldname)
  }
  emitUpdate()
}
function setFieldRequired(name, fieldname, required) {
  if (!props.isCandidateForm) return
  normalizeEntry(name)
  const obj = localConfig.value[name]?.fields.find((f) => f.field_name === fieldname)
  if (obj) obj.is_required = !!required
  emitUpdate()
}
function getFlag(name, flag) {
  return props.isCandidateForm ? !!localConfig.value[name]?.[flag] : false
}
function setFlag(name, flag, value) {
  if (!props.isCandidateForm) return
  if (!localConfig.value[name]) localConfig.value[name] = { fields: [], is_agreement_required: false, is_candidate_form_required: false }
  localConfig.value[name][flag] = value
  emitUpdate()
}

function fieldCount(name) {
  const n = getFields(name).length
  return `${n} field${n !== 1 ? 's' : ''}`
}

const allFieldNames = computed(() => props.fieldSections.flatMap((s) => s.fields.map((f) => f.fieldname)))
const allSelected = computed(() => {
  if (!currentItem.value) return false
  const cur = getFields(currentItem.value)
  return allFieldNames.value.length > 0 && allFieldNames.value.every((fn) => cur.includes(fn))
})
function toggleSelectAll() {
  if (!currentItem.value) return
  const turnOn = !allSelected.value
  allFieldNames.value.forEach((fn) => toggleFieldSelected(currentItem.value, fn, turnOn))
}

const filteredSections = computed(() => {
  const q = search.value.toLowerCase()
  return props.fieldSections
    .map((section) => ({
      label: section.label,
      fields: section.fields.filter((f) => !q || f.label.toLowerCase().includes(q) || f.fieldname.toLowerCase().includes(q)),
    }))
    .filter((s) => s.fields.length)
})

// ── Copy fields from another item ──────────────────────────────────────────
const showCopyDialog = ref(false)
const copySource = ref('')
const copyableItems = computed(() =>
  props.itemsList.filter((name) => {
    if (name === currentItem.value) return false
    return getFields(name).length > 0 || getFlag(name, 'is_agreement_required') || getFlag(name, 'is_candidate_form_required')
  }),
)
const copySourceField = computed(() => ({
  fieldname: 'source',
  label: `Copy Fields From ${props.selectorLabel}`,
  fieldtype: 'Select',
  options: copyableItems.value.join('\n'),
}))
watch(showCopyDialog, (open) => {
  if (open) copySource.value = ''
})
function copyFrom() {
  if (!copySource.value || !localConfig.value[copySource.value]) return
  localConfig.value[currentItem.value] = JSON.parse(JSON.stringify(localConfig.value[copySource.value]))
  emitUpdate()
  showCopyDialog.value = false
}
</script>

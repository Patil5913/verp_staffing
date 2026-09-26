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
        <div class="flex max-h-[calc(100vh-16rem)] flex-col gap-1.5 overflow-y-auto pr-1">
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
      </div>

      <!-- Field picker -->
      <div v-if="!currentItem" class="flex items-center justify-center rounded-lg border border-dashed border-app-border p-10 text-p-sm text-app-text-muted">
        Select a {{ selectorLabel }} to configure its fields.
      </div>

      <div v-else class="flex flex-col gap-4 rounded-lg border border-app-border bg-app-panel p-4">
        <div class="flex flex-col gap-3">
          <!-- Search -->
          <div class="flex items-center gap-3">
            <AppSearchInput v-model="search" placeholder="Search fields by name or label…" class="flex-1" />
            <AppBadge theme="blue" size="md">{{ getFields(currentItem).length }} selected</AppBadge>
          </div>

          <!-- Filters + bulk actions, kept apart from the search box -->
          <div class="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-app-border bg-app-panel-2 px-3 py-2">
            <span class="flex items-center gap-1.5 text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">
              <FeatherIcon name="filter" class="h-3.5 w-3.5" /> Filters
            </span>
            <AppSwitch v-model="selectedOnly" label="Selected only" />
            <AppSwitch v-if="isCandidateForm" v-model="requiredOnly" label="Required only" />

            <div class="ml-auto flex flex-wrap items-center gap-2">
              <AppButton variant="ghost" size="sm" @click="toggleAllSections">
                {{ allCollapsed ? 'Expand all' : 'Collapse all' }}
              </AppButton>
              <AppButton variant="outline" size="sm" :disabled="disabled" @click="toggleSelectAll">
                {{ allSelected ? 'Deselect all' : 'Select all' }}
              </AppButton>
              <AppButton v-if="copyableItems.length" variant="outline" size="sm" :disabled="disabled" @click="showCopyDialog = true">
                Copy Fields From
              </AppButton>
              <AppButton v-if="allowAddField" variant="primary" size="sm" icon="plus" :disabled="disabled" @click="openAddField">
                Add New Field
              </AppButton>
            </div>
          </div>
        </div>

        <div v-if="isCandidateForm" class="flex flex-col gap-2 rounded-lg border border-app-border bg-app-panel-2 p-3">
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

        <div class="flex max-h-[calc(100vh-16rem)] flex-col gap-4 overflow-y-auto">
          <div
            v-for="(section, si) in filteredSections"
            :key="section.label"
            class="flex flex-col gap-1.5 rounded-lg p-3"
            :style="sectionStyle(si)"
          >
            <button
              type="button"
              class="flex items-center gap-2 rounded-md py-1 text-left"
              @click="toggleSection(section.label)"
            >
              <FeatherIcon :name="isCollapsed(section.label) ? 'chevron-right' : 'chevron-down'" class="h-4 w-4 text-app-text-muted" />
              <span class="text-p-xs font-semibold uppercase tracking-wide text-app-text">{{ section.label }}</span>
              <AppBadge>{{ sectionSelected(section.label) }}/{{ sectionTotal(section.label) }} selected</AppBadge>
            </button>
            <div v-show="!isCollapsed(section.label)" class="grid grid-cols-1 gap-1 sm:grid-cols-2">
              <div
                v-for="field in section.fields"
                :key="field.fieldname"
                class="flex items-center justify-between gap-2 rounded-md px-2 py-1"
                :class="isFieldSelected(currentItem, field.fieldname) ? 'bg-app-panel shadow-sm' : ''"
              >
                <AppCheckbox
                  :label="field.label"
                  :disabled="disabled"
                  :model-value="isFieldSelected(currentItem, field.fieldname)"
                  @update:model-value="(v) => toggleFieldSelected(currentItem, field.fieldname, v)"
                />
                <AppCheckbox
                  v-if="isCandidateForm"
                  label="Required"
                  class="shrink-0 !text-p-xs"
                  :disabled="disabled || !isFieldSelected(currentItem, field.fieldname)"
                  :model-value="isFieldRequired(currentItem, field.fieldname)"
                  @update:model-value="(v) => setFieldRequired(currentItem, field.fieldname, v)"
                />
              </div>
            </div>
          </div>
          <p v-if="!filteredSections.length" class="py-6 text-center text-p-sm text-app-text-muted">
            No fields match the current filters
          </p>
        </div>
      </div>
    </div>
  </div>

  <Dialog v-model="showAddDialog" :options="{ title: 'Add New Field' }">
    <template #body-content>
      <div class="flex flex-col gap-3">
        <p class="text-p-sm text-app-text-muted">
          Creates a real field on the candidate form, so it can be picked (and made required) for any service.
        </p>
        <AppInput v-model="newField.label" label="Label" required placeholder="e.g. Passport Number" />
        <AppCombobox v-model="newField.fieldtype" label="Type" :options="NEW_FIELD_TYPES" />
        <AppTextarea
          v-if="newField.fieldtype === 'Select'"
          v-model="newField.options"
          label="Options (one per line)"
          required
        />
        <AppCombobox v-model="newField.section" label="Section" :options="fieldSections.map((s) => s.label)" />
      </div>
    </template>
    <template #actions>
      <AppButton :loading="addingField" :disabled="!newField.label.trim()" @click="submitAddField">Add Field</AppButton>
    </template>
  </Dialog>

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
import AppBadge from '@/components/ui/AppBadge.vue'
import AppSwitch from '@/components/ui/AppSwitch.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppTextarea from '@/components/ui/AppTextarea.vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'
// Ports the old desk render_field_selector_widget() (ERP Configuration's
// Candidate Form Fields / Department Display Fields / Department Access
// Fields tabs) onto this app's own components - same CONFIG shape (a JSON
// object keyed by item name, either a plain array of fieldnames or, for
// the candidate form, { fields: [{field_name, is_required}],
// is_agreement_required, is_candidate_form_required }), same search/
// select-all/copy-from behavior - just Checkbox/AppButton/Dialog instead
// of hand-built gradient HTML.
import { computed, ref, watch } from 'vue'
import { Dialog, FeatherIcon } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import FieldControl from '@/components/detail/FieldControl.vue'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'

// Each section is its own tinted block (cycling colours). Inline rgba so it
// works in light and dark mode and doesn't depend on the Tailwind palette.
const SECTION_RGB = ['37, 99, 235', '5, 150, 105', '217, 119, 6', '124, 58, 237', '225, 29, 72', '8, 145, 178']
const sectionStyle = (i) => {
  const rgb = SECTION_RGB[i % SECTION_RGB.length]
  return {
    backgroundColor: `rgba(${rgb}, 0.12)`,
    border: `1px solid rgba(${rgb}, 0.4)`,
    borderLeft: `5px solid rgb(${rgb})`,
  }
}

const props = defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  impact: { type: String, default: '' },
  selectorLabel: { type: String, default: 'item' },
  itemsList: { type: Array, required: true },
  isCandidateForm: { type: Boolean, default: false },
  // Shows "Add New Field" - creates a real Custom Field on the picked doctype.
  allowAddField: { type: Boolean, default: false },
  fieldSections: { type: Array, default: () => [] },
  modelValue: { type: Object, default: () => ({}) },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'field-added'])

const localConfig = ref({})
watch(
  () => props.modelValue,
  (val) => {
    localConfig.value = JSON.parse(JSON.stringify(val || {}))
    // Normalize once, right after loading - not lazily inside a getter that
    // runs during template render (see normalizeEntry below). A getter
    // called from `:class`/`:model-value` bindings runs on every render, and
    // for old-format entries (a plain array, pre-dating is_required) it used
    // to *write* localConfig.value[name] to migrate the shape - a reactive
    // mutation during render, which re-triggers the render that mutates it
    // again, crashing the Candidate Form Fields tab (the only tab whose
    // entries ever take the old array shape) with a "Maximum recursive
    // updates" loop.
    if (props.isCandidateForm) {
      Object.keys(localConfig.value).forEach(normalizeEntry)
    }
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
  // Read-only - normalization already happened once when localConfig was
  // loaded (see the modelValue watcher above), never here: this is called
  // from template bindings evaluated on every render, and a write here
  // instead of a read used to crash the tab (see that watcher's comment).
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

const selectedOnly = ref(false)
const requiredOnly = ref(false)
const collapsed = ref(new Set())

const filteredSections = computed(() => {
  const q = search.value.toLowerCase()
  const item = currentItem.value
  return props.fieldSections
    .map((section) => ({
      label: section.label,
      fields: section.fields.filter((f) => {
        if (q && !f.label.toLowerCase().includes(q) && !f.fieldname.toLowerCase().includes(q)) return false
        if (selectedOnly.value && !isFieldSelected(item, f.fieldname)) return false
        if (requiredOnly.value && !isFieldRequired(item, f.fieldname)) return false
        return true
      }),
    }))
    .filter((s) => s.fields.length)
})

function sectionTotal(label) {
  return props.fieldSections.find((s) => s.label === label)?.fields.length || 0
}
function sectionSelected(label) {
  const cur = getFields(currentItem.value)
  return (props.fieldSections.find((s) => s.label === label)?.fields || []).filter((f) => cur.includes(f.fieldname)).length
}
const isCollapsed = (label) => collapsed.value.has(label)
function toggleSection(label) {
  const next = new Set(collapsed.value)
  if (next.has(label)) next.delete(label)
  else next.add(label)
  collapsed.value = next
}
const allCollapsed = computed(() => props.fieldSections.length > 0 && collapsed.value.size >= props.fieldSections.length)
function toggleAllSections() {
  collapsed.value = allCollapsed.value ? new Set() : new Set(props.fieldSections.map((s) => s.label))
}

// ── Add a brand-new field to the form ────────────────────────────────────
const NEW_FIELD_TYPES = ['Data', 'Small Text', 'Long Text', 'Int', 'Float', 'Date', 'Select', 'Check', 'Phone']
const showAddDialog = ref(false)
const newField = ref({ label: '', fieldtype: 'Data', options: '', section: '' })
const addFieldResource = useResource({
  url: 'verp_staffing.settings.doctype.erp_configuration.erp_configuration.add_candidate_form_field',
})
const addingField = computed(() => addFieldResource.isLoading)

function openAddField() {
  newField.value = { label: '', fieldtype: 'Data', options: '', section: props.fieldSections[0]?.label || '' }
  showAddDialog.value = true
}
async function submitAddField() {
  const section = props.fieldSections.find((s) => s.label === newField.value.section)
  const res = await addFieldResource.resource.submit({
    label: newField.value.label,
    fieldtype: newField.value.fieldtype,
    options: newField.value.options,
    insert_after: section?.fields.at(-1)?.fieldname,
  })
  if (!res) return
  showAddDialog.value = false
  notify.success(`Field "${res.label}" added.`)
  emit('field-added', res)
  if (currentItem.value) toggleFieldSelected(currentItem.value, res.fieldname, true)
}

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

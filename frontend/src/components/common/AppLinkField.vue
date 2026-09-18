<template>
  <div class="flex flex-col gap-1.5">
    <label v-if="label" class="text-p-sm font-medium text-app-text-muted">{{ label }}</label>

    <Combobox
      v-model="model"
      v-model:open="isOpen"
      class="app-link-combobox"
      :options="comboOptions"
      :placeholder="placeholder || `Select ${doctype}`"
      :disabled="disabled"
      :loading="search.isLoading"
      open-on-focus
      @input="handleInput"
      @focus="loadOptions('')"
    >
      <template v-if="!hideAddNew" #footer>
        <button type="button" class="app-link-add-new" @click="openQuickCreate">
          <FeatherIcon name="plus" class="h-3.5 w-3.5 shrink-0" />
          <span class="truncate">Add New {{ doctype }}</span>
        </button>
      </template>
    </Combobox>

    <QuickCreateDialog
      v-if="!hideAddNew && showQuickCreate"
      v-model="showQuickCreate"
      :doctype="doctype"
      :initial-value="query"
      :navigate-on-create="false"
      @created="onCreated"
    />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Combobox, FeatherIcon, debounce } from 'frappe-ui'
import { useResource } from '@/composables/list/useResource'
import QuickCreateDialog from '@/components/list/QuickCreateDialog.vue'

const props = defineProps({
  doctype: { type: String, required: true },
  modelValue: { default: '' },
  label: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  filters: { type: Object, default: () => ({}) },
  // How many matches search_link returns — its own default is 10, too few
  // once a doctype has more matches than fit on one screen (e.g. picking a
  // DocType out of the few hundred this app defines).
  pageLength: { type: Number, default: 20 },
  // Hides the "Add New <doctype>" footer/quick-create flow — for fields
  // that link to something this page has no business creating on the fly
  // (e.g. picking an existing DocType in the Permission Manager).
  hideAddNew: { type: Boolean, default: false },
  // A whitelisted "standard query" method (e.g.
  // verp_staffing.crm.api.helpers.get_assign_to_by_service) that filters/
  // sorts results server-side beyond a plain `filters` dict — same `query`
  // param the classic desk Link field's set_query() passes through to
  // search_link.
  query: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const model = computed({
  get: () => props.modelValue || '',
  set: (value) => emit('update:modelValue', value),
})

const isOpen = ref(false)
const query = ref('')
const showQuickCreate = ref(false)

const search = useResource({
  url: 'frappe.desk.search.search_link',
  method: 'POST',
  makeParams: (txt) => ({
    doctype: props.doctype,
    txt: txt || '',
    filters: props.filters,
    page_length: props.pageLength,
    query: props.query || undefined,
  }),
  notifyOnError: false,
  transform: (data) => (data || []).map((doc) => ({ label: doc.label || doc.value, value: doc.value })),
})

function loadOptions(txt) {
  search.resource.fetch(txt)
}

const debouncedLoad = debounce((txt) => loadOptions(txt), 300)

function handleInput(txt) {
  query.value = txt
  debouncedLoad(txt)
}

watch(
  () => [props.doctype, props.filters, props.query],
  () => loadOptions(''),
  { immediate: true, deep: true },
)

const comboOptions = computed(() => search.resource.data || [])

function openQuickCreate() {
  isOpen.value = false
  showQuickCreate.value = true
}

function onCreated(newName) {
  if (!newName) return
  model.value = newName
  loadOptions('')
}
</script>

<style scoped>
.app-link-combobox :deep([data-slot='trigger']) {
  box-sizing: border-box;
  height: 2.25rem;
  min-height: 0;
  width: 100%;
  border-radius: 0.5rem;
  border: 1px solid var(--app-border);
  background-color: var(--app-panel);
  padding: 0 0.75rem;
  box-shadow: none;
}

.app-link-combobox :deep([data-slot='trigger']:focus-within) {
  border-color: var(--app-primary);
  box-shadow: 0 0 0 2px var(--app-primary-tint);
}

.app-link-combobox :deep([data-slot='input']) {
  color: var(--app-text);
  background-color: transparent;
  font-size: 13px;
  line-height: 1.5;
}

.app-link-add-new {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 0.5rem;
  border-top: 1px solid var(--app-border);
  padding: 0.5rem 0.75rem;
  font-size: 13px;
  font-weight: 500;
  color: var(--app-primary);
  background-color: transparent;
  transition: background-color 0.15s ease;
}

.app-link-add-new:hover {
  background-color: var(--app-panel-2);
}
</style>

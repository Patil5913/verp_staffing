<template>
  <div class="flex flex-col gap-1.5">
    <label v-if="label" class="text-p-sm font-medium text-app-text-muted">
      {{ label }}<span v-if="required" class="text-red-600"> *</span>
    </label>

    <Combobox
      v-model="model"
      v-model:open="isOpen"
      class="app-link-combobox"
      :class="{ 'app-link-combobox--compact': compact }"
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

    <PersonQuickCreateDialog
      v-if="!hideAddNew && showQuickCreate && isPersonDoctype"
      v-model="showQuickCreate"
      :doctype="doctype"
      :initial-value="query"
      :navigate-on-create="false"
      @created="onCreated"
    />
    <QuickCreateDialog
      v-else-if="!hideAddNew && showQuickCreate"
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
import { useRouter } from 'vue-router'
import { Combobox, FeatherIcon, debounce, call } from 'frappe-ui'
import { useResource } from '@/composables/list/useResource'
import QuickCreateDialog from '@/components/list/QuickCreateDialog.vue'
import PersonQuickCreateDialog from '@/components/common/PersonQuickCreateDialog.vue'
import { PERSON_DOCTYPES } from '@/configs/detail/listOptions'

const props = defineProps({
  doctype: { type: String, required: true },
  modelValue: { default: '' },
  label: { type: String, default: '' },
  required: { type: Boolean, default: false },
  placeholder: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  // The 28px toolbar-height control instead of the 36px form field.
  compact: { type: Boolean, default: false },
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

const router = useRouter()

const isOpen = ref(false)
const query = ref('')
const showQuickCreate = ref(false)
const isPersonDoctype = computed(() => PERSON_DOCTYPES.has(props.doctype))

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

// Guards against an out-of-order response: two overlapping searches (e.g.
// typing a term, then clearing it right after) can resolve in either
// order — without this, a slower earlier request finishing after a faster
// later one silently overwrites the fresher results, leaving the dropdown
// stuck showing the stale filtered list even once the search box is empty.
// `results` only accepts a response whose request is still the latest one
// issued, so `comboOptions` never regresses to a superseded search.
let requestSeq = 0
const results = ref([])

async function loadOptions(txt) {
  const seq = ++requestSeq
  await search.resource.fetch(txt)
  if (seq === requestSeq) results.value = search.resource.data || []
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

const comboOptions = computed(() => results.value)

async function openQuickCreate() {
  isOpen.value = false
  if (isPersonDoctype.value) {
    showQuickCreate.value = true
    return
  }
  // Checked up front, same reason as DocListView's onAddNew — no meta for
  // this doctype is preloaded here (unlike a list page), so this one extra
  // round trip replaces the generic QuickCreateDialog's own after-the-fact
  // check, which used to flash the dialog open before redirecting.
  const quickEntry = await call('verp_staffing.utils.detail_view.get_quick_entry_flag', { doctype: props.doctype }).catch(() => false)
  if (quickEntry) {
    showQuickCreate.value = true
  } else {
    router.push(`/${encodeURIComponent(props.doctype)}/new`)
  }
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

<style>
/* Not scoped: the trigger is the Combobox's own (renderless) root, which never
   gets this component's scope attribute, and a scoped :deep() only reaches
   descendants. Without an explicit width it grows to its text and spills over
   whatever sits beside it. */
.app-link-combobox--compact {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  height: 1.75rem;
  min-height: 0;
  padding: 0 0.5rem;
  border: 1px solid var(--app-border);
  border-radius: 0.375rem;
  background-color: var(--app-panel);
  box-shadow: none;
  font-size: 13px;
}

.app-link-combobox--compact input {
  font-size: 13px;
}

.app-link-combobox--compact:focus-within {
  border-color: var(--app-primary);
  box-shadow: 0 0 0 2px var(--app-primary-tint);
}
</style>

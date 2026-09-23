<template>
  <Dialog v-model="show" :options="{ title: 'Filter Interviews by Customer(s)', size: 'lg' }">
    <template #body-content>
      <div class="flex flex-col gap-3">
        <div class="flex items-center gap-2">
          <AppButton variant="outline" size="sm" @click="selectAll">Select all</AppButton>
          <AppButton variant="outline" size="sm" @click="clearAll">Clear all</AppButton>
          <AppSearchInput v-model="searchTerm" class="flex-1" placeholder="Search customers…" />
        </div>
        <p class="text-p-xs text-app-text-muted">{{ selected.size }} selected</p>

        <div class="grid max-h-96 grid-cols-1 gap-1 overflow-y-auto rounded-lg border border-app-border p-2 sm:grid-cols-2" @scroll="onScroll">
          <label
            v-for="option in loaded"
            :key="option.value"
            class="flex min-w-0 cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-p-sm text-app-text hover:bg-app-panel-2"
          >
            <input type="checkbox" :checked="selected.has(option.value)" @change="toggle(option.value)" />
            <span class="min-w-0 truncate" :title="option.label">{{ option.label }}</span>
          </label>
          <p v-if="!loaded.length && !loading" class="col-span-full py-6 text-center text-p-sm text-app-text-muted">No customers found.</p>
          <p v-if="loading" class="col-span-full py-2 text-center text-p-xs text-app-text-muted">Loading…</p>
        </div>
      </div>
    </template>
    <template #actions>
      <AppButton :disabled="!selected.size" @click="apply">Apply</AppButton>
    </template>
  </Dialog>
</template>

<script setup>
// Ported from interview_list.js's open_marketing_customer_dialog — a
// searchable, paginated (scroll-to-load-more), multi-select checkbox list
// of every Marketing/Customer pair the user is assigned to, backed by the
// same get_assigned_marketing_customers used for the default "select all".
import { computed, ref, watch } from 'vue'
import { call, Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppSearchInput from '@/components/ui/AppSearchInput.vue'
import { useMarketingCustomerFilter } from '@/composables/list/useMarketingCustomerFilter'

const METHOD = 'verp_staffing.marketing.doctype.interview.interview.get_assigned_marketing_customers'
const PAGE_SIZE = 30

const show = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['applied'])

const { selectedCustomers, setSelectedCustomers } = useMarketingCustomerFilter()

const selected = ref(new Set())
const loaded = ref([])
const searchTerm = ref('')
const loading = ref(false)
const start = ref(0)
const hasMore = ref(true)

watch(show, (open) => {
  if (!open) return
  selected.value = new Set(selectedCustomers.value)
  searchTerm.value = ''
  fetchPage(true)
})

async function fetchPage(reset) {
  if (loading.value) return
  if (reset) {
    loaded.value = []
    start.value = 0
    hasMore.value = true
  } else if (!hasMore.value) {
    return
  }
  loading.value = true
  try {
    const rows = (await call(METHOD, { txt: searchTerm.value, start: start.value, page_length: PAGE_SIZE })) || []
    hasMore.value = rows.length === PAGE_SIZE
    start.value += rows.length
    loaded.value = [...loaded.value, ...rows]
  } finally {
    loading.value = false
  }
}

let searchTimer = null
watch(searchTerm, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => fetchPage(true), 300)
})

function onScroll(e) {
  const el = e.target
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 80) fetchPage(false)
}

function toggle(value) {
  const next = new Set(selected.value)
  if (next.has(value)) next.delete(value)
  else next.add(value)
  selected.value = next
}
function selectAll() {
  selected.value = new Set([...selected.value, ...loaded.value.map((o) => o.value)])
}
function clearAll() {
  const loadedValues = new Set(loaded.value.map((o) => o.value))
  selected.value = new Set([...selected.value].filter((v) => !loadedValues.has(v)))
}

function apply() {
  const values = [...selected.value]
  setSelectedCustomers(values)
  show.value = false
  emit('applied', values)
}
</script>

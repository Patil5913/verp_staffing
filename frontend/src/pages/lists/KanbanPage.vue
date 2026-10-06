<template>
  <div class="flex h-full flex-col bg-app-bg">
    <SubNavbar :title="doctype">
      <template #left><ViewSwitcher :doctype="doctype" current="kanban" /></template>
      <AppSearchInput v-model="search" class="w-full" placeholder="Search cards">
      </AppSearchInput>
      <template #right>
        <AppButton v-if="doctype === 'Interview'" variant="outline" size="sm" icon="users" @click="showCustomerDialog = true">
          Select Customer
        </AppButton>
        <AppButton variant="ghost" icon="refresh-cw" tooltip="Refresh" @click="load" />
      </template>
    </SubNavbar>

    <div class="flex min-h-0 flex-1 flex-col gap-3 px-3 md:px-6 py-3">
      <StateBanner v-if="!config" icon="columns-3" title="No board for this doctype" />
      <StateBanner v-else-if="loadError" icon="alert-triangle" title="Couldn't load the board" :description="loadError" />
      <div v-else-if="initialLoading" class="flex justify-center py-16">
        <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
      </div>
      <KanbanBoard
        :column-colors="config.columnColors"
        v-else-if="config"
        :columns="config.columns"
        :cards="filtered"
        :status-field="config.statusField"
        :has-more="hasMoreMap"
        :loading-more="loadingMore"
        :counts="counts"
        @open="(card) => router.push(`/${encodeURIComponent(doctype)}/${encodeURIComponent(card.name)}`)"
        @move="onMove"
        @load-more="onLoadMore"
      >
        <template #card="{ card }">
          <RecordLabel :doctype="doctype" :id="card.name" :title="card[config.title] || ''" title-class="text-p-sm font-medium text-app-text" />
          <p v-if="card[config.subtitle]" class="truncate text-p-xs text-app-text-muted">{{ card[config.subtitle] }}</p>
          <RecordLabel v-if="card.customer" doctype="Customer" :id="card.customer" class="mt-1 w-full" title-class="text-p-xs text-app-text-muted" />
          <ul v-if="rounds[card.name]?.length" class="mt-2 flex flex-col gap-1 border-t border-app-border pt-2">
            <li v-for="(r, i) in rounds[card.name].slice(-3)" :key="i" class="flex items-center justify-between gap-2 text-p-xs">
              <span class="truncate text-app-text-muted">{{ r.round_title || `Round ${r.round}` }} · {{ formatDate(r.date_of_interview) || 'no date' }}</span>
              <DocStatusBadge :status="r.status" />
            </li>
            <li v-if="rounds[card.name].length > 3" class="text-p-xs text-app-text-muted">+{{ rounds[card.name].length - 3 }} earlier</li>
          </ul>
        </template>
      </KanbanBoard>
    </div>

    <Dialog v-model="reason.open" :options="{ title: `Mark as ${reason.to}`, size: 'md' }">
      <template #body-content>
        <div class="flex flex-col gap-4">
          <AppInput type="select" :label="`${reason.to} By`" v-model="reason.by" :options="['', 'Company', 'Candidate']" required />
          <AppInput type="textarea" :label="`Reason of ${reason.to}`" v-model="reason.text" required />
        </div>
      </template>
      <template #actions>
        <AppButton :disabled="!reason.by || !reason.text.trim()" :loading="moving" @click="submitReason">Confirm</AppButton>
      </template>
    </Dialog>

    <SelectCustomerDialog v-if="doctype === 'Interview'" v-model="showCustomerDialog" @applied="load" />
  </div>
</template>

<script setup>
import RecordLabel from '@/components/common/RecordLabel.vue'
import AppSearchInput from '@/components/ui/AppSearchInput.vue'
import AppInput from '@/components/ui/AppInput.vue'
// Kanban view of a doctype (today: Interview, ported from interview_list.js).
// Each column loads its own page of cards (PAGE_SIZE at a time, more on
// scroll), and turns a drag into the doctype's own move method - optimistic,
// rolled back if the server refuses (e.g. a round that's already Completed
// can't be moved again).
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call, Dialog, FeatherIcon, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import SubNavbar from '@/components/common/SubNavbar.vue'
import ViewSwitcher from '@/components/common/ViewSwitcher.vue'
import KanbanBoard from '@/components/list/KanbanBoard.vue'
import SelectCustomerDialog from '@/components/list/SelectCustomerDialog.vue'
import { KANBAN } from '@/configs/detail/listOptions'
import { useMarketingCustomerFilter } from '@/composables/list/useMarketingCustomerFilter'
import { formatDate } from '@/utils/list/formatValue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

const route = useRoute()
const router = useRouter()
const doctype = computed(() => route.params.doctype)
const config = computed(() => KANBAN[doctype.value])
const search = ref('')
const showCustomerDialog = ref(false)

// interview_list.js's apply_marketing_auto_filter: the board only ever
// shows cards for whichever customers are currently selected - every
// customer assigned to the user the first time, whatever "Select Customer"
// was last set to after that.
const { selectedCustomers, ensureDefaultCustomers } = useMarketingCustomerFilter()

const PAGE_SIZE = 10
const cards = ref([])
const rounds = ref({})
const initialLoading = ref(true)
const loadError = ref('')
// { [column]: { start, hasMore } } - each column paginates independently.
const pageState = reactive({})
const loadingMore = reactive({})
const counts = reactive({}) // { [column]: total rows on the server, not just loaded }
const hasMoreMap = computed(() => Object.fromEntries(config.value.columns.map((c) => [c, !!pageState[c]?.hasMore])))

async function fetchCount(column) {
  const isInterview = doctype.value === 'Interview'
  const baseFilters = isInterview && selectedCustomers.value.length ? { marketing_link: ['in', selectedCustomers.value] } : {}
  const filters = { ...baseFilters, [config.value.statusField]: column }
  try {
    counts[column] = isInterview
      ? await call('verp_staffing.marketing.doctype.interview.interview.get_interview_count', { filters })
      : await call('frappe.client.get_count', { doctype: doctype.value, filters })
  } catch {
    delete counts[column] // falls back to the loaded count in KanbanBoard
  }
}

async function loadRoundsFor(rows) {
  if (!config.value?.summaryMethod || !rows.length) return
  try {
    const data = await call(config.value.summaryMethod, { names: JSON.stringify(rows.map((c) => c.name)) })
    Object.assign(rounds.value, data)
  } catch {
    // stale round summaries stay as-is; not worth failing the board over.
  }
}

async function fetchColumn(column, { append = false } = {}) {
  const state = pageState[column]
  const isInterview = doctype.value === 'Interview'
  const baseFilters = isInterview && selectedCustomers.value.length ? { marketing_link: ['in', selectedCustomers.value] } : {}
  const rows = await call(isInterview ? 'verp_staffing.marketing.doctype.interview.interview.get_interview_list' : 'frappe.client.get_list', {
    ...(isInterview ? {} : { doctype: doctype.value }),
    fields: ['name', config.value.statusField, ...config.value.cardFields],
    filters: { ...baseFilters, [config.value.statusField]: column },
    order_by: 'modified desc',
    limit_start: state.start,
    limit_page_length: PAGE_SIZE,
  })
  state.hasMore = rows.length === PAGE_SIZE
  state.start += rows.length
  cards.value = append ? [...cards.value, ...rows] : [...cards.value.filter((c) => c[config.value.statusField] !== column), ...rows]
  loadRoundsFor(rows)
}

async function onLoadMore(column) {
  if (loadingMore[column] || !pageState[column]?.hasMore) return
  loadingMore[column] = true
  try {
    await fetchColumn(column, { append: true })
  } catch (error) {
    notify.error(normalizeError(error).message)
  } finally {
    loadingMore[column] = false
  }
}

async function load() {
  if (!config.value) return
  if (doctype.value === 'Interview') await ensureDefaultCustomers()
  cards.value = []
  for (const column of config.value.columns) {
    pageState[column] = { start: 0, hasMore: true }
    loadingMore[column] = false
  }
  initialLoading.value = true
  loadError.value = ''
  try {
    await Promise.all(config.value.columns.flatMap((column) => [fetchColumn(column), fetchCount(column)]))
  } catch (error) {
    loadError.value = normalizeError(error).message
  } finally {
    initialLoading.value = false
  }
}
watch(doctype, load, { immediate: true })

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return cards.value
  return cards.value.filter((c) => Object.values(c).some((v) => String(v ?? '').toLowerCase().includes(q)))
})

const moving = ref(false)
const reason = reactive({ open: false, card: null, to: '', by: '', text: '' })

async function moveCard(card, to, extra = {}) {
  const field = config.value.statusField
  const from = card[field]
  card[field] = to // optimistic
  moving.value = true
  try {
    await call(config.value.moveMethod, { [config.value.moveArg]: card.name, status: to, ...extra })
    notify.success(`${card.name} moved to ${to}.`)
    loadRoundsFor([card])
    fetchCount(from)
    fetchCount(to)
    return true
  } catch (error) {
    card[field] = from
    notify.error(normalizeError(error).message)
    return false
  } finally {
    moving.value = false
  }
}

function onMove({ card, to }) {
  // Interview's Today column is derived from the round's date - nothing to set.
  if (doctype.value === 'Interview' && to === 'Today') {
    notify.info("'Today' is worked out automatically from the round's date.")
    return
  }
  if (config.value.reasonStatuses?.includes(to)) {
    Object.assign(reason, { open: true, card, to, by: '', text: '' })
    return
  }
  moveCard(card, to)
}

async function submitReason() {
  const ok = await moveCard(reason.card, reason.to, { cancelled_by: reason.by, reason_of_cancel: reason.text.trim() })
  if (ok) reason.open = false
}
</script>

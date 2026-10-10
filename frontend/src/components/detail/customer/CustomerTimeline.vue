<template>
  <div class="mx-auto max-w-4xl">
    <div class="relative mb-3 max-w-xs">
      <span class="lucide-search pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-app-text-muted" />
      <input
        v-model="search"
        type="search"
        placeholder="Search history"
        class="w-full rounded-lg border border-app-border bg-app-panel py-1.5 pl-8 pr-3 text-p-sm text-app-text placeholder:text-app-text-muted focus:border-app-primary focus:outline-none"
      />
    </div>
    <div v-if="groups.length > 1" class="mb-5 flex flex-wrap gap-2">
      <button
        v-for="g in ['All', ...groups]"
        :key="g"
        type="button"
        class="rounded-full border px-3 py-1 text-p-xs font-medium transition-colors"
        :class="(g === 'All' ? !filter : filter === g) ? 'border-app-primary bg-app-primary-tint text-app-primary' : 'border-app-border text-app-text-muted hover:border-app-primary/40'"
        @click="filter = g === 'All' ? '' : g"
      >
        {{ g }} <span class="opacity-70">{{ g === 'All' ? all.length : countOf(g) }}</span>
      </button>
    </div>
    <!-- Fixed width and a minimum height, so switching filters doesn't resize the page (the jerk). -->
    <div class="min-h-[60vh]">
    <!-- Marketing / Interview: the same tables as the Marketing record's History tab. -->
    <CustomerHistoryPanel
      v-if="tableDept"
      :key="tableDept"
      :customer="customer"
      :departments="[tableDept]"
      :exclude="tableDept === 'Marketing' ? ['Interview'] : []"
      :search="search"
    />
    <div v-else-if="timeline.isLoading && !timeline.resource.data" class="flex justify-center py-16">
      <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
    </div>
    <StateBanner v-else-if="timeline.hasError" icon="alert-triangle" title="Couldn't load the history" :description="timeline.errorMessage" />
    <p v-else-if="all.length && !entries.length" class="rounded-xl border border-dashed border-app-border py-8 text-center text-p-sm text-app-text-muted">
      Nothing matches "{{ search }}".
    </p>
    <p v-else-if="!all.length" class="rounded-xl border border-dashed border-app-border py-8 text-center text-p-sm text-app-text-muted">
      Nothing has happened for this customer yet. Sales orders, agreements, payments, portal access, forwards and department work will show up here.
    </p>

    <div v-else class="flex flex-col">
      <div v-for="(entry, index) in entries" :key="index" class="relative flex gap-3" :class="index !== entries.length - 1 ? 'pb-5' : ''">
        <div class="flex flex-col items-center">
          <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full" :class="STYLES[entry.kind].bg">
            <FeatherIcon :name="STYLES[entry.kind].icon" class="h-4 w-4" :class="STYLES[entry.kind].fg" />
          </div>
          <div v-if="index !== entries.length - 1" class="mt-1 w-px flex-1 bg-app-border" />
        </div>

        <div class="min-w-0 flex-1 pb-0.5 pt-1">
          <div class="rounded-xl border border-app-border bg-app-panel px-4 py-3 shadow-sm">
            <div class="flex items-start justify-between gap-2">
              <router-link v-if="entry.link" :to="`/${encodeURIComponent(entry.link[0])}/${encodeURIComponent(entry.link[1])}`" class="text-p-sm font-medium text-app-primary hover:underline">
                {{ entry.title }}
              </router-link>
              <span v-else class="text-p-sm font-medium text-app-text">{{ entry.title }}</span>
              <span class="shrink-0 text-p-xs text-app-text-muted">{{ formatDatetime(entry.ts) }}</span>
            </div>
            <div class="mt-1 flex flex-wrap items-center gap-2 text-p-xs text-app-text-muted">
              <span v-if="entry.detail">{{ entry.detail }}</span>
              <DocStatusBadge v-if="entry.status" :status="entry.status" />
            </div>
          </div>
        </div>
      </div>
    </div>
    </div>
  </div>
</template>

<script setup>
// The customer's History as a timeline (same look as the Notes/Activity feed): sales orders,
// agreements and their signing steps, payments, portal access and forwards - newest first.
// Backed by verp_staffing.crm.api.customer_timeline.
import { computed, ref, watch } from 'vue'
import { FeatherIcon, LoadingIndicator } from 'frappe-ui'
import CustomerHistoryPanel from '@/components/detail/customer/CustomerHistoryPanel.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { useResource } from '@/composables/list/useResource'
import { formatDatetime } from '@/utils/list/formatValue'

defineOptions({ inheritAttrs: false })
const props = defineProps({ customer: { type: String, required: true } })

const STYLES = {
  sales_order: { icon: 'shopping-cart', bg: 'bg-app-primary-tint', fg: 'text-app-primary' },
  agreement: { icon: 'file-text', bg: 'bg-violet-500/15', fg: 'text-violet-500' },
  payment: { icon: 'credit-card', bg: 'bg-emerald-500/15', fg: 'text-emerald-500' },
  portal: { icon: 'key', bg: 'bg-amber-500/15', fg: 'text-amber-500' },
  service: { icon: 'send', bg: 'bg-app-panel-2', fg: 'text-app-text-muted' },
  department: { icon: 'briefcase', bg: 'bg-sky-500/15', fg: 'text-sky-500' },
  candidate_form: { icon: 'user-round', bg: 'bg-rose-500/15', fg: 'text-rose-500' },
}

const timeline = useResource({
  url: 'verp_staffing.crm.api.customer_timeline.get_customer_timeline',
  makeParams: () => ({ customer: props.customer }),
  notifyOnError: false,
  auto: true,
})
watch(() => props.customer, () => timeline.resource.reload())
const all = computed(() => timeline.resource.data || [])
const filter = ref('')
const tableDept = computed(() => (filter.value === 'Marketing' || filter.value === 'Interview' ? filter.value : ''))
// Filter chips come from what's actually in the timeline (Sales Orders, Agreements, ... and each department).
const groups = computed(() => [...new Set(all.value.map((e) => e.group))])
const countOf = (g) => all.value.filter((e) => e.group === g).length
const search = ref('')
const entries = computed(() => {
  const q = search.value.trim().toLowerCase()
  return all.value.filter(
    (e) => (!filter.value || e.group === filter.value) && (!q || [e.title, e.detail, e.status, e.group, e.ts].some((v) => String(v || '').toLowerCase().includes(q))),
  )
})
defineExpose({ reload: () => timeline.resource.reload() })
</script>

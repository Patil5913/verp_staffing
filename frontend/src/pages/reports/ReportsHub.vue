<template>
  <div class="flex h-full flex-col bg-app-bg">
    <SubNavbar title="Reports">
      <AppSearchInput v-model="search" class="w-full" placeholder="Find a report">
      </AppSearchInput>
    </SubNavbar>

    <div class="min-h-0 flex-1 overflow-y-auto px-3 md:px-6 py-5">
      <StateBanner v-if="index.hasError" icon="alert-triangle" title="Couldn't load reports" :description="index.errorMessage" />
      <div v-else-if="index.isLoading && !index.resource.data" class="flex justify-center py-16"><LoadingIndicator class="h-6 w-6 text-app-text-muted" /></div>
      <StateBanner v-else-if="!groups.length" icon="search" title="No reports found" :description="search ? 'Nothing matches that search.' : 'You don\'t have access to any reports.'" />

      <div v-else class="mx-auto flex max-w-6xl flex-col gap-8">
        <section v-for="group in groups" :key="group.name" class="flex flex-col gap-3">
          <h2 class="text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">{{ group.name }}</h2>
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <router-link
              v-for="r in group.reports"
              :key="r.name"
              :to="`/report/${encodeURIComponent(r.name)}`"
              class="group flex items-start gap-3 rounded-xl border border-app-border bg-app-panel p-4 shadow-sm transition-colors hover:border-app-primary/50"
            >
              <span class="flex size-9 shrink-0 items-center justify-center rounded-lg bg-app-primary-tint text-app-primary">
                <span :class="`lucide-${r.icon || 'file-bar-chart'} size-4`" />
              </span>
              <span class="min-w-0">
                <span class="block truncate text-p-base font-medium text-app-text group-hover:text-app-primary">{{ r.name }}</span>
                <span class="mt-0.5 block text-p-sm text-app-text-muted">{{ r.description }}</span>
              </span>
            </router-link>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import AppSearchInput from '@/components/ui/AppSearchInput.vue'
// The reports hub: every report the user may open, grouped by area, so reports
// are findable without knowing which sidebar section holds them (Trial Balance,
// for one, isn't in the sidebar at all).
import { computed, ref } from 'vue'
import { FeatherIcon, LoadingIndicator } from 'frappe-ui'
import StateBanner from '@/components/common/StateBanner.vue'
import SubNavbar from '@/components/common/SubNavbar.vue'
import { useResource } from '@/composables/list/useResource'

const search = ref('')
const index = useResource({ url: 'verp_staffing.utils.reports.get_reports_index', auto: true })

const groups = computed(() => {
  const q = search.value.trim().toLowerCase()
  const map = new Map()
  for (const r of index.resource.data || []) {
    if (q && !`${r.name} ${r.description} ${r.group}`.toLowerCase().includes(q)) continue
    if (!map.has(r.group)) map.set(r.group, [])
    map.get(r.group).push(r)
  }
  return [...map].map(([name, reports]) => ({ name, reports }))
})
</script>

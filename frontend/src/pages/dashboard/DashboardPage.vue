<template>
  <div class="flex h-full flex-col bg-app-bg">
    <DashboardSubNav
      v-model:preset="preset"
      v-model:company="company"
      v-model:custom="custom"
      :sections="sections"
      :section="section"
      :companies="companies"
      :loading="board.isLoading"
      @refresh="load(true)"
    />

    <div class="min-h-0 flex-1 overflow-y-auto px-3 md:px-6 py-4">
      <StateBanner v-if="meta.hasError" icon="alert-triangle" title="Couldn't open the dashboard" :description="meta.errorMessage" />
      <StateBanner v-else-if="board.hasError && !data" icon="alert-triangle" title="Couldn't build this dashboard" :description="board.errorMessage" />
      <div v-else-if="!data" class="flex justify-center py-24"><LoadingIndicator class="h-6 w-6 text-app-text-muted" /></div>

      <div v-else class="mx-auto flex max-w-[1600px] flex-col gap-4" :class="board.isLoading ? 'opacity-70 transition-opacity' : ''">
        <p class="text-p-xs text-app-text-muted">
          {{ formatDay(data.period.from) }} – {{ formatDay(data.period.to) }} · compared with the previous {{ data.period.days }} day{{ data.period.days === 1 ? '' : 's' }}
          <template v-if="data.company && ['overview', 'accounts', 'crm'].includes(section)"> · {{ data.company }}</template>
        </p>

        <DashboardAlerts v-if="data.alerts.length" :alerts="data.alerts" />

        <div v-if="data.kpis.length" class="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-6">
          <DashboardKpi v-for="k in data.kpis" :key="k.id" :kpi="k" :currency="data.currency || ''" />
        </div>

        <div v-if="data.charts.length" class="grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3" style="grid-auto-flow: dense">
          <DashboardChart v-for="c in data.charts" :key="c.id" :chart="c" :currency="data.currency || ''" />
        </div>

        <div v-if="data.tables.length" class="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <DashboardTable v-for="t in data.tables" :key="t.id" :table="t" :currency="data.currency || ''" />
        </div>

        <StateBanner
          v-if="!data.kpis.length && !data.charts.length && !data.tables.length"
          icon="lock"
          title="Nothing to show here"
          description="Either you don't have access to the records behind this section, or there's no data yet."
        />
      </div>
    </div>
  </div>
</template>

<script setup>
// The analytics home: a tab per area of the business (Overview, Accounts, CRM,
// Marketing, Operations), each a board of KPI tiles, charts and tables the
// server assembles for the chosen period (utils/dashboard.py). The page only
// lays the board out — every widget is generic — so a new metric is a server
// change, not a frontend one.
import { LoadingIndicator } from 'frappe-ui'
import StateBanner from '@/components/common/StateBanner.vue'
import DashboardAlerts from '@/components/dashboard/DashboardAlerts.vue'
import DashboardChart from '@/components/dashboard/DashboardChart.vue'
import DashboardKpi from '@/components/dashboard/DashboardKpi.vue'
import DashboardSubNav from '@/components/dashboard/DashboardSubNav.vue'
import DashboardTable from '@/components/dashboard/DashboardTable.vue'
import { useDashboard } from '@/composables/dashboard/useDashboard'
import { formatDay } from '@/utils/dashboard/format'

const { meta, sections, companies, section, preset, custom, company, board, data, load } = useDashboard()
</script>

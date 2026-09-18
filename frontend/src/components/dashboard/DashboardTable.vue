<template>
  <section class="flex min-w-0 flex-col rounded-xl border border-app-border bg-app-panel shadow-sm">
    <header class="flex items-center justify-between gap-2 px-4 pb-2 pt-3">
      <h3 class="text-p-base font-medium text-app-text">{{ table.title }}</h3>
      <router-link v-if="table.href" :to="table.href" class="text-p-xs font-medium text-app-primary hover:underline">View all</router-link>
    </header>

    <p v-if="!table.rows.length" class="px-4 pb-4 text-p-sm text-app-text-muted">Nothing to show.</p>
    <div v-else class="overflow-x-auto">
      <table class="w-full text-p-sm">
        <thead>
          <tr class="border-y border-app-border bg-app-panel-2 text-left text-p-xs uppercase tracking-wide text-app-text-muted">
            <th v-for="c in table.columns" :key="c.key" class="whitespace-nowrap px-4 py-1.5 font-medium" :class="isNum(c) ? 'text-right' : ''">{{ c.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in table.rows" :key="i" class="border-b border-app-border last:border-0">
            <td v-for="c in table.columns" :key="c.key" class="max-w-[16rem] truncate px-4 py-1.5" :class="isNum(c) ? 'text-right tabular-nums' : ''" :title="String(row[c.key] ?? '')">
              <router-link v-if="c.format === 'link' && row._href" :to="row._href" class="font-medium text-app-primary hover:underline">{{ row[c.key] }}</router-link>
              <DocStatusBadge v-else-if="c.format === 'status' && row[c.key]" :status="row[c.key]" />
              <template v-else>{{ cell(row[c.key], c) }}</template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import { formatMetric } from '@/utils/dashboard/format'

const props = defineProps({
  table: { type: Object, required: true },
  currency: { type: String, default: '' },
})

const isNum = (c) => ['number', 'currency', 'percent', 'hours'].includes(c.format)
const cell = (v, c) => (c.format && c.format !== 'link' && c.format !== 'status' ? formatMetric(v, c.format, props.currency) : (v ?? ''))
</script>

<template>
  <!-- The dashboard's own sub navbar: same bar as SubNavbar, but the middle is
  the section tabs (Overview / Accounts / CRM / Marketing / Operations) with
  the period, company and refresh on the right — SubNavbar's fixed three-column
  grid has no room for a row of tabs. -->
  <div class="flex h-11 shrink-0 items-center gap-4 border-b border-app-border bg-app-panel px-6">
    <h1 class="shrink-0 text-p-lg font-medium text-app-text">Dashboard</h1>

    <nav class="[scrollbar-width:none] flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
      <router-link
        v-for="s in sections"
        :key="s.key"
        :to="s.key === 'overview' ? '/dashboard' : `/dashboard/${s.key}`"
        class="inline-flex h-7 shrink-0 items-center gap-1.5 rounded-full px-3 text-p-sm font-medium transition-colors"
        :class="s.key === section ? 'bg-app-primary-tint text-app-primary' : 'text-app-text-muted hover:bg-app-panel-2 hover:text-app-text'"
      >
        <span :class="`lucide-${s.icon} size-3.5`" />{{ s.label }}
      </router-link>
    </nav>

    <div class="flex shrink-0 items-center gap-2">
      <AppLinkField v-if="showCompany" v-model="company" doctype="Company" compact hide-add-new placeholder="Company" class="w-44 shrink-0" />

      <DateRangePicker v-if="preset === 'custom'" v-model="range" placeholder="Pick a range" variant="outline" input-class="!h-7 w-48 !text-p-sm" />
      <AppCombobox v-model="preset" :options="PRESETS" compact placeholder="Period" class="w-36 shrink-0" />

      <Button variant="ghost" icon="refresh-cw" tooltip="Refresh" :loading="loading" @click="$emit('refresh')" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, DateRangePicker } from 'frappe-ui'
import AppCombobox from '@/components/common/AppCombobox.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import { PRESETS } from '@/utils/dashboard/format'

const props = defineProps({
  sections: { type: Array, required: true },
  section: { type: String, required: true },
  companies: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})
defineEmits(['refresh'])

const preset = defineModel('preset', { type: String, required: true })
const company = defineModel('company', { type: String, default: '' })
const custom = defineModel('custom', { type: Object, required: true })

// DateRangePicker speaks "from,to"; the dashboard keeps them as two fields.
const range = computed({
  get: () => (custom.value.from && custom.value.to ? `${custom.value.from},${custom.value.to}` : ''),
  set: (value) => {
    const [from, to] = (value || '').split(',')
    if (from && to) Object.assign(custom.value, { from, to })
  },
})

// Only the money-bearing tabs depend on a company.
const showCompany = computed(() => props.companies.length > 1 && ['overview', 'accounts', 'crm'].includes(props.section))
</script>

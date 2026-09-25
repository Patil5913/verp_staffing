<template>
  <!-- The dashboard's own sub navbar: same bar as SubNavbar, but the middle is
  the section tabs (Overview / Accounts / CRM / Marketing / Operations) with
  the period, company and refresh on the right - SubNavbar's fixed three-column
  grid has no room for a row of tabs. -->
  <div class="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-2 border-b border-app-border bg-app-panel px-3 py-2 md:h-11 md:flex-nowrap md:px-6 md:py-0">
    <h1 class="shrink-0 text-p-lg font-medium text-app-text">Dashboard</h1>

    <nav class="[scrollbar-width:none] order-last flex w-full min-w-0 items-center gap-1 overflow-x-auto md:order-none md:w-auto md:flex-1">
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

    <div class="ml-auto flex min-w-0 flex-wrap items-center justify-end gap-2 md:shrink-0 md:flex-nowrap">
      <AppLinkField v-if="showCompany" v-model="company" doctype="Company" compact hide-add-new placeholder="Company" class="w-36 shrink-0 md:w-44" />

      <AppDatePicker v-if="preset === 'custom'" v-model="range" mode="range" compact placeholder="Pick a range" class="w-60 shrink-0" />
      <AppCombobox v-model="preset" :options="PRESETS" compact placeholder="Period" class="w-36 shrink-0" />

      <AppButton variant="ghost" icon="refresh-cw" tooltip="Refresh" :loading="loading" @click="$emit('refresh')" />
    </div>
  </div>
</template>

<script setup>
import AppButton from '@/components/ui/AppButton.vue'
import { computed } from 'vue'
import AppDatePicker from '@/components/ui/AppDatePicker.vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'
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

// AppDatePicker (range mode) speaks "from,to"; the dashboard keeps them as two fields.
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

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
      <select v-if="showCompany" v-model="company" class="h-7 max-w-[12rem] rounded-md border border-app-border bg-app-bg px-2 text-p-sm text-app-text focus:border-app-primary focus:outline-none" title="Company">
        <option v-for="c in companies" :key="c" :value="c">{{ c }}</option>
      </select>

      <template v-if="preset === 'custom'">
        <input v-model="custom.from" type="date" class="h-7 rounded-md border border-app-border bg-app-bg px-2 text-p-sm text-app-text focus:border-app-primary focus:outline-none" />
        <span class="text-p-xs text-app-text-muted">to</span>
        <input v-model="custom.to" type="date" class="h-7 rounded-md border border-app-border bg-app-bg px-2 text-p-sm text-app-text focus:border-app-primary focus:outline-none" />
      </template>
      <select v-model="preset" class="h-7 rounded-md border border-app-border bg-app-bg px-2 text-p-sm text-app-text focus:border-app-primary focus:outline-none" title="Period">
        <option v-for="p in PRESETS" :key="p.value" :value="p.value">{{ p.label }}</option>
      </select>

      <Button variant="ghost" icon="refresh-cw" tooltip="Refresh" :loading="loading" @click="$emit('refresh')" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button } from 'frappe-ui'
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

// Only the money-bearing tabs depend on a company.
const showCompany = computed(() => props.companies.length > 1 && ['overview', 'accounts', 'crm'].includes(props.section))
</script>

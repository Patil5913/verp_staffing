<template>
  <section class="rounded-xl border border-app-border bg-app-panel p-4 shadow-sm">
    <h3 class="mb-2 flex items-center gap-2 text-p-base font-medium text-app-text"><span class="lucide-bell-ring size-4 text-amber-600" />Needs attention</h3>
    <ul class="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
      <li v-for="a in alerts" :key="a.id">
        <component :is="a.href ? 'router-link' : 'div'" :to="a.href || undefined" class="flex items-center gap-3 rounded-lg border border-app-border bg-app-bg px-3 py-2 transition-colors" :class="a.href ? 'hover:border-app-primary/50' : ''">
          <span class="flex h-7 min-w-7 shrink-0 items-center justify-center gap-1 rounded-full px-2 text-p-sm font-semibold tabular-nums" :class="TONES[a.tone] || TONES.warn"><span :class="`lucide-${alertIcon(a)} size-3.5`" />{{ a.value.toLocaleString() }}</span>
          <span class="min-w-0">
            <span class="block truncate text-p-sm text-app-text">{{ a.label }}</span>
            <span v-if="a.hint" class="block truncate text-p-xs text-app-text-muted">{{ a.hint }}</span>
          </span>
        </component>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { alertIcon } from '@/utils/dashboard/icons'

defineProps({ alerts: { type: Array, required: true } })

const TONES = {
  bad: 'bg-red-500/10 text-red-600',
  warn: 'bg-amber-500/10 text-amber-600',
  info: 'bg-blue-500/10 text-blue-600',
  good: 'bg-green-500/10 text-green-600',
}
</script>

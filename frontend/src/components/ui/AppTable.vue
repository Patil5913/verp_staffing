<template>
  <div class="overflow-x-auto rounded-xl border border-app-border bg-app-panel">
    <table class="w-full text-p-sm">
      <thead>
        <tr class="border-b border-app-border bg-app-panel-2 text-left text-p-xs uppercase tracking-wide text-app-text-muted">
          <th v-for="c in columns" :key="c.key" class="whitespace-nowrap px-4 py-2 font-medium" :class="c.align === 'right' ? 'text-right' : ''">{{ c.label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!rows.length">
          <td :colspan="columns.length" class="px-4 py-8 text-center text-app-text-muted">{{ emptyText }}</td>
        </tr>
        <tr
          v-for="(row, i) in rows"
          :key="i"
          class="border-b border-app-border last:border-0"
          :class="clickable ? 'cursor-pointer hover:bg-app-panel-2' : ''"
          @click="clickable && emit('row-click', row)"
        >
          <td v-for="c in columns" :key="c.key" class="px-4 py-2" :class="c.align === 'right' ? 'text-right tabular-nums' : ''">
            <slot :name="`cell-${c.key}`" :row="row" :value="row[c.key]">{{ row[c.key] ?? '' }}</slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
// Plain read-only data table. Override any cell with a `cell-<key>` slot.
defineProps({
  // [{ key, label, align?: 'left' | 'right' }]
  columns: { type: Array, required: true },
  rows: { type: Array, default: () => [] },
  emptyText: { type: String, default: 'No data.' },
  clickable: { type: Boolean, default: false },
})
const emit = defineEmits(['row-click'])
</script>

<template>
  <div class="flex flex-col gap-2">
    <div class="overflow-x-auto rounded-xl border border-app-border bg-app-panel">
      <table class="w-full text-p-sm">
        <thead>
          <tr class="border-b border-app-border bg-app-panel-2 text-left text-p-xs uppercase tracking-wide text-app-text-muted">
            <th class="w-10 px-3 py-2 font-medium">#</th>
            <th v-for="c in columns" :key="c.key" class="whitespace-nowrap px-3 py-2 font-medium" :class="c.type === 'number' ? 'text-right' : ''">{{ c.label }}</th>
            <th v-if="!disabled" class="w-10" />
          </tr>
        </thead>
        <tbody>
          <tr v-if="!rows.length">
            <td :colspan="columns.length + 2" class="px-4 py-6 text-center text-app-text-muted">No rows yet.</td>
          </tr>
          <tr v-for="(row, i) in rows" :key="i" class="border-b border-app-border last:border-0">
            <td class="px-3 py-1.5 text-app-text-muted">{{ i + 1 }}</td>
            <td v-for="c in columns" :key="c.key" class="px-2 py-1.5">
              <input
                :type="c.type === 'number' ? 'number' : 'text'"
                :value="row[c.key]"
                :disabled="disabled"
                class="h-8 w-full min-w-[6rem] rounded-md border border-transparent bg-transparent px-2 text-p-sm text-app-text outline-none hover:border-app-border focus:border-app-primary disabled:opacity-60"
                :class="c.type === 'number' ? 'text-right tabular-nums' : ''"
                @input="setCell(i, c, $event.target.value)"
              />
            </td>
            <td v-if="!disabled" class="px-2 py-1.5 text-right">
              <AppButton variant="ghost" size="icon" icon="trash-2" @click="removeRow(i)" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="!disabled">
      <AppButton variant="outline" size="sm" icon="plus" @click="addRow">Add Row</AppButton>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'

// Inline-editable child table (rows edited in place). ChildTableField is the
// doctype-driven version that edits a row in a dialog.
const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  // [{ key, label, type?: 'text' | 'number' }]
  columns: { type: Array, required: true },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const rows = computed(() => props.modelValue || [])

const emitRows = (next) => emit('update:modelValue', next)
const addRow = () => emitRows([...rows.value, Object.fromEntries(props.columns.map((c) => [c.key, c.type === 'number' ? 0 : '']))])
const removeRow = (i) => emitRows(rows.value.filter((_, idx) => idx !== i))
const setCell = (i, col, raw) =>
  emitRows(rows.value.map((r, idx) => (idx === i ? { ...r, [col.key]: col.type === 'number' ? Number(raw) : raw } : r)))
</script>

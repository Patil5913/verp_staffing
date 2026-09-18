<template>
  <div class="flex min-h-0 flex-1 gap-3 overflow-x-auto pb-1">
    <section
      v-for="column in columns"
      :key="column"
      class="flex w-72 shrink-0 flex-col rounded-xl border bg-app-panel-2/60 transition-colors"
      :class="overColumn === column ? 'border-app-primary bg-app-primary-tint' : 'border-app-border'"
      @dragover.prevent="overColumn = column"
      @dragleave="overColumn === column && (overColumn = '')"
      @drop.prevent="onDrop(column)"
    >
      <header class="flex items-center justify-between gap-2 px-3 py-2.5">
        <div class="flex min-w-0 items-center gap-2">
          <span class="size-2 shrink-0 rounded-full" :class="dotClass(column)" />
          <h2 class="truncate text-p-sm font-semibold text-app-text">{{ column }}</h2>
        </div>
        <span class="rounded-full bg-app-panel px-2 py-0.5 text-p-xs font-medium text-app-text-muted">{{ grouped[column].length }}</span>
      </header>

      <div class="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-2 pb-2">
        <article
          v-for="card in grouped[column]"
          :key="card.name"
          class="cursor-pointer rounded-lg border border-app-border bg-app-panel p-3 shadow-sm transition-shadow hover:shadow-md"
          :class="dragging === card.name ? 'opacity-50' : ''"
          draggable="true"
          @dragstart="dragging = card.name"
          @dragend="(dragging = ''), (overColumn = '')"
          @click="emit('open', card)"
        >
          <slot name="card" :card="card">
            <p class="truncate text-p-sm font-medium text-app-text">{{ card.name }}</p>
          </slot>
        </article>
        <p v-if="!grouped[column].length" class="rounded-lg border border-dashed border-app-border px-3 py-6 text-center text-p-xs text-app-text-muted">
          Nothing here
        </p>
      </div>
    </section>
  </div>
</template>

<script setup>
// A doctype-agnostic kanban board: cards grouped by `statusField` into fixed
// columns, native drag-and-drop between them. Dropping only *requests* a move
// (emit 'move') — the page decides whether it's allowed and updates the card,
// so a rejected drop simply leaves the card where it was.
import { computed, ref } from 'vue'

const props = defineProps({
  columns: { type: Array, required: true },
  cards: { type: Array, required: true },
  statusField: { type: String, default: 'status' },
})
const emit = defineEmits(['move', 'open'])

const dragging = ref('')
const overColumn = ref('')

const grouped = computed(() => {
  const out = Object.fromEntries(props.columns.map((c) => [c, []]))
  for (const card of props.cards) out[card[props.statusField]]?.push(card)
  return out
})

const DOTS = ['bg-sky-500', 'bg-emerald-500', 'bg-green-600', 'bg-rose-500', 'bg-orange-500', 'bg-violet-500', 'bg-red-600']
const dotClass = (column) => DOTS[props.columns.indexOf(column) % DOTS.length]

function onDrop(column) {
  const card = props.cards.find((c) => c.name === dragging.value)
  dragging.value = ''
  overColumn.value = ''
  if (card && card[props.statusField] !== column) emit('move', { card, to: column })
}
</script>

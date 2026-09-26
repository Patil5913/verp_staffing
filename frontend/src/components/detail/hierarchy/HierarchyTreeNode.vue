<template>
  <li>
    <div
      class="group flex items-center gap-2 rounded-lg border px-2.5 py-2 transition-colors"
      :class="[
        over ? 'border-app-primary bg-app-primary/10 ring-2 ring-app-primary/30' : 'border-app-border bg-app-panel',
        dragging ? 'opacity-40' : '',
      ]"
      draggable="true"
      @dragstart.stop="onDragStart"
      @dragend="dragging = false"
      @dragover.prevent.stop="over = true"
      @dragleave.stop="over = false"
      @drop.prevent.stop="onDrop"
    >
      <FeatherIcon name="menu" class="h-4 w-4 shrink-0 cursor-grab text-app-text-muted" />
      <span class="text-p-sm font-medium text-app-text">{{ node.role }}</span>
      <span v-if="over" class="text-p-xs text-app-primary">Drop to add as a child of {{ node.role }}</span>
      <span v-else-if="!node.children.length" class="text-p-xs text-app-text-muted">No reports</span>
      <div class="ml-auto flex items-center gap-1">
        <select
          v-if="available.length"
          class="h-7 rounded-md border border-app-border bg-app-panel-2 px-1.5 text-p-xs text-app-text-muted"
          @change="onPick"
        >
          <option value="">+ Add child</option>
          <option v-for="r in available" :key="r" :value="r">{{ r }}</option>
        </select>
        <button
          type="button"
          class="rounded p-1 text-app-text-muted hover:bg-app-border hover:text-app-text"
          title="Remove from hierarchy"
          @click="$emit('remove', node.role)"
        >
          <FeatherIcon name="x" class="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
    <ul v-if="node.children.length" class="ml-5 mt-2 flex flex-col gap-2 border-l-2 border-app-border pl-4">
      <HierarchyTreeNode
        v-for="c in node.children"
        :key="c.role"
        :node="c"
        :available="available"
        @move="(...a) => $emit('move', ...a)"
        @remove="(r) => $emit('remove', r)"
      />
    </ul>
  </li>
</template>

<script setup>
import { ref } from 'vue'
import { FeatherIcon } from 'frappe-ui'

const props = defineProps({
  node: { type: Object, required: true },
  available: { type: Array, default: () => [] },
})
const emit = defineEmits(['move', 'remove'])

const over = ref(false)
const dragging = ref(false)

function onDragStart(e) {
  dragging.value = true
  e.dataTransfer.setData('text/plain', props.node.role)
  e.dataTransfer.effectAllowed = 'move'
}
function onDrop(e) {
  over.value = false
  const role = e.dataTransfer.getData('text/plain')
  if (role) emit('move', role, props.node.role)
}
function onPick(e) {
  const role = e.target.value
  e.target.value = ''
  if (role) emit('move', role, props.node.role)
}
</script>

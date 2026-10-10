<template>
  <StateBanner v-if="result.error" icon="alert-triangle" :title="result.title || 'No hierarchy yet'" :description="result.error" />

  <div v-else class="hierarchy-canvas overflow-auto rounded-xl border border-app-border bg-app-panel-2">
    <svg :width="result.width" :height="result.height" class="mx-auto block">
      <defs>
        <filter id="hier-shadow" x="-20%" y="-20%" width="140%" height="160%">
          <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#0f172a" flood-opacity="0.12" />
        </filter>
      </defs>

      <path
        v-for="edge in result.edges"
        :key="edge.id"
        :d="edge.d"
        stroke="#93c5fd"
        stroke-width="2"
        stroke-linecap="round"
        fill="none"
      />

      <g v-for="node in result.nodes.filter((n) => n.isEntry)" :key="node.id" filter="url(#hier-shadow)">
        <rect :x="node.x - 40" :y="node.y - 15" width="80" height="30" rx="15" fill="#2563eb" />
        <path :d="`M ${node.x - 20} ${node.y - 5} l 8 5 l -8 5 z`" fill="#fff" />
        <text :x="node.x - 6" :y="node.y + 4" font-size="12" font-weight="600" fill="#fff">Start</text>
      </g>

      <g v-for="node in result.nodes.filter((n) => !n.isEntry)" :key="node.id" filter="url(#hier-shadow)">
        <rect
          :x="node.x - W / 2"
          :y="node.y - H / 2"
          :width="W"
          :height="H"
          rx="12"
          class="fill-app-panel"
        />
        <rect
          :x="node.x - W / 2"
          :y="node.y - H / 2"
          :width="W"
          :height="H"
          rx="12"
          fill="none"
          :stroke="node.isStart || node.id === highlight ? color(node.level) : 'var(--app-border)'"
          :stroke-width="node.isStart || node.id === highlight ? 2 : 1"
        />
        <rect :x="node.x - W / 2" :y="node.y - H / 2" width="6" :height="H" rx="3" :fill="color(node.level)" />
        <text :x="node.x - W / 2 + 20" :y="node.y - 2" font-size="13" font-weight="600" class="fill-app-text">
          {{ truncate(labels[node.id]?.title || node.id) }}
        </text>
        <text :x="node.x - W / 2 + 20" :y="node.y + 13" font-size="10" class="fill-app-text-muted">
          <template v-if="labels[node.id]">{{ labels[node.id].subtitle }}</template>
          <template v-else>
            {{ node.isStart ? 'Top level' : `Level ${node.level + 1}` }} ·
            {{ node.reports ? `${node.reports} report${node.reports > 1 ? 's' : ''}` : 'No reports' }}
          </template>
        </text>
      </g>
    </svg>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { computeHierarchyDiagram } from '@/utils/detail/hierarchyDiagram'

const W = 160
const H = 46
const PALETTE = ['#2563eb', '#0891b2', '#059669', '#d97706', '#9333ea', '#db2777']

const props = defineProps({
  // Parsed role_hierarchy_json: [{ parent_role, child_roles: [] }, ...]
  data: { type: Array, default: () => [] },
  // Optional: node id -> { title, subtitle } to show instead of the id /
  // level text, and a node id to outline (e.g. employees instead of roles).
  labels: { type: Object, default: () => ({}) },
  highlight: { type: String, default: '' },
})

const result = computed(() => computeHierarchyDiagram(props.data))
const color = (level) => PALETTE[level % PALETTE.length]
const truncate = (t) => (t.length > 17 ? `${t.slice(0, 16)}…` : t)
</script>

<style scoped>
.hierarchy-canvas {
  background-image: radial-gradient(var(--app-border) 1px, transparent 1px);
  background-size: 18px 18px;
  padding: 12px;
}
</style>

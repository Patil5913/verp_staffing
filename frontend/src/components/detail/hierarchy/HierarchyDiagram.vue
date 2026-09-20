<template>
  <StateBanner v-if="result.error" icon="alert-triangle" :title="result.title || 'No hierarchy yet'" :description="result.error" />

  <div v-else class="overflow-auto rounded-lg border border-app-border bg-app-panel-2 p-3">
    <svg :width="result.width" :height="result.height">
      <defs>
        <marker id="hierarchy-arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L0,6 L9,3 z" class="fill-app-text-muted" />
        </marker>
      </defs>

      <path
        v-for="edge in result.edges"
        :key="edge.id"
        :d="edge.d"
        class="stroke-app-text-muted"
        stroke-width="2"
        fill="none"
        marker-end="url(#hierarchy-arrow)"
      />

      <g v-for="node in result.nodes" :key="node.id">
        <rect
          :x="node.x - RECT_WIDTH / 2"
          :y="node.y - RECT_HEIGHT / 2"
          :width="RECT_WIDTH"
          :height="RECT_HEIGHT"
          rx="6"
          ry="6"
          :class="node.isStart ? 'fill-app-primary-tint stroke-app-primary' : 'fill-app-panel stroke-app-border'"
          :stroke-width="node.isStart ? 2 : 1.5"
        />
        <text
          :x="node.x"
          :y="node.y + 5"
          text-anchor="middle"
          font-size="14"
          :font-weight="node.isStart ? 'bold' : 'normal'"
          class="fill-app-text"
        >
          {{ node.id }}
        </text>
      </g>
    </svg>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { computeHierarchyDiagram } from '@/utils/detail/hierarchyDiagram'

const RECT_WIDTH = 150
const RECT_HEIGHT = 40

const props = defineProps({
  // Parsed role_hierarchy_json: [{ parent_role, child_roles: [] }, ...]
  data: { type: Array, default: () => [] },
})

const result = computed(() => computeHierarchyDiagram(props.data))
</script>

<template>
  <div class="mx-auto flex max-w-3xl flex-col gap-4 px-6 py-8">
    <h1 class="text-2xl font-semibold text-app-text">{{ doctype }}</h1>

    <StateBanner
      v-if="roots.hasError"
      icon="alert-triangle"
      title="Couldn't load the tree"
      :description="roots.errorMessage"
    />
    <div v-else-if="roots.isLoading && !nodes.length" class="flex justify-center py-16">
      <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
    </div>
    <StateBanner v-else-if="!nodes.length" icon="folder" title="No records" />

    <div v-else class="rounded-lg border border-app-border bg-app-panel p-4">
      <Tree
        v-for="node in nodes"
        :key="node.value"
        :node="node"
        node-key="value"
        :options="{ rowHeight: '32px', indentWidth: '20px', defaultCollapsed: true }"
      >
        <template #node="{ node: n, toggleCollapsed }">
          <div class="flex cursor-pointer items-center gap-1" @click="onToggle(n, toggleCollapsed, $event)">
            <FeatherIcon
              v-if="n.expandable"
              :name="n._collapsed === false ? 'chevron-down' : 'chevron-right'"
              class="h-3.5 w-3.5 shrink-0 text-app-text-muted"
            />
            <span v-else class="inline-block w-3.5 shrink-0" />
            <span v-if="n.loading" class="text-p-sm text-app-text-muted">Loading…</span>
            <span v-else class="truncate text-p-base text-app-text">{{ n.label }}</span>
          </div>
        </template>
      </Tree>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { call, FeatherIcon, LoadingIndicator, Tree } from 'frappe-ui'
import { useResource } from '@/composables/useResource'
import StateBanner from '@/components/StateBanner.vue'

const route = useRoute()
const doctype = computed(() => route.params.doctype)

const nodes = ref([])

function toNode(raw) {
  return {
    value: raw.value,
    label: raw.title || raw.value,
    expandable: !!raw.expandable,
    children: [],
    loaded: false,
    loading: false,
    _collapsed: true,
  }
}

const roots = useResource({
  url: 'frappe.desk.treeview.get_children',
  makeParams: () => ({ doctype: doctype.value, parent: '' }),
  auto: true,
  onSuccess(data) {
    nodes.value = (data || []).map(toNode)
  },
})

async function onToggle(node, toggleCollapsed, event) {
  if (!node.expandable) {
    toggleCollapsed(event)
    return
  }
  if (!node.loaded) {
    node.loading = true
    try {
      const children = await call('frappe.desk.treeview.get_children', {
        doctype: doctype.value,
        parent: node.value,
      })
      node.children = (children || []).map(toNode)
      node.loaded = true
    } finally {
      node.loading = false
    }
  }
  node._collapsed = !node._collapsed
  toggleCollapsed(event)
}
</script>

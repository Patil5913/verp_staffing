<template>
  <div class="flex h-full flex-col bg-app-bg">
    <SubNavbar :title="doctype">
      <template #left><ViewSwitcher :doctype="doctype" current="tree" /></template>
      <AppSearchInput v-model="search" class="w-full" placeholder="Search">
        <template #suffix>
          <SearchSyntaxPopover :groups="treeSearchSyntaxHelp" @select="search = $event" />
        </template>
      </AppSearchInput>
      <AppButton
        variant="outline"
        theme="red"
        icon="x"
        tooltip="Clear search"
        :disabled="!search"
        @click="search = ''"
      />
      <template #right>
        <AppButton variant="outline" icon="chevrons-down" tooltip="Expand all" @click="tree?.expandAll()" />
        <AppButton variant="outline" icon="chevrons-up" tooltip="Collapse" @click="tree?.collapseAll()" />
        <AppButton variant="surface" icon="refresh-cw" tooltip="Refresh" @click="tree?.reload()" />
      </template>
    </SubNavbar>

    <div class="flex min-h-0 flex-1 flex-col px-3 md:px-6 py-3">
      <DocTreeView
        ref="tree"
        :key="doctype"
        :loader="loadChildren"
        :search="search"
        :name-label="doctype"
        @open="(node) => router.push(`/${encodeURIComponent(doctype)}/${encodeURIComponent(node.value)}`)"
      />
    </div>
  </div>
</template>

<script setup>
import SearchSyntaxPopover from '@/components/common/SearchSyntaxPopover.vue'
import AppSearchInput from '@/components/ui/AppSearchInput.vue'
// Generic tree view for any tree doctype (Company, Item Category, ...) via
// Frappe's stock treeview endpoint. The Account tree has its own page
// (AccountTreePage.vue) - it needs company scoping and balances.
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import SubNavbar from '@/components/common/SubNavbar.vue'
import ViewSwitcher from '@/components/common/ViewSwitcher.vue'
import DocTreeView from '@/components/tree/DocTreeView.vue'

const route = useRoute()
const router = useRouter()
const doctype = computed(() => route.params.doctype)
const tree = ref(null)
const search = ref('')

watch(search, (value, prev) => {
  if (value.trim() && !prev.trim()) tree.value?.expandAll()
})

const treeSearchSyntaxHelp = [
  {
    title: 'Match a field',
    rows: [
      { example: `${doctype.value}=open`, description: 'Scope the match to one column, by its name or column label.' },
      { example: `${doctype.value}="in progress"`, description: 'Quote a value that has spaces.' },
      { example: 'vrugle', description: 'A plain word matches any visible column instead.' },
    ],
  },
  {
    title: 'Combine conditions',
    rows: [
      { example: 'name=vrugle type=Bank', description: 'Multiple fields - all must match (AND).' },
      { example: 'name=vrugle or type=Bank', description: 'Either one can match (OR) instead.' },
    ],
  },
  {
    title: 'Compare & range',
    rows: [
      { example: 'name!=vrugle', description: 'Not equal, also works with >, <, >=, <=.' },
      { example: 'name between a to m', description: 'A range on one field.' },
    ],
  },
]

const loadChildren = (parent) =>
  call('frappe.desk.treeview.get_children', { doctype: doctype.value, parent: parent || '' })
</script>

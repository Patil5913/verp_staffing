<template>
  <div class="flex h-full flex-col bg-app-bg">
    <SubNavbar :title="doctype">
      <template #left><ViewSwitcher :doctype="doctype" current="tree" /></template>
      <TextInput v-model="search" class="w-full" placeholder="Search">
        <template #prefix><FeatherIcon name="search" class="h-4 w-4 text-app-text-muted" /></template>
      </TextInput>
      <template #right>
        <AppButton variant="outline" size="sm" icon="chevrons-down" @click="tree?.expandAll()">Expand all</AppButton>
        <AppButton variant="outline" size="sm" icon="chevrons-up" @click="tree?.collapseAll()">Collapse</AppButton>
        <Button variant="ghost" icon="refresh-cw" tooltip="Refresh" @click="tree?.reload()" />
      </template>
    </SubNavbar>

    <div class="flex min-h-0 flex-1 flex-col px-6 py-3">
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
// Generic tree view for any tree doctype (Company, Item Category, ...) via
// Frappe's stock treeview endpoint. The Account tree has its own page
// (AccountTreePage.vue) — it needs company scoping and balances.
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, call, FeatherIcon, TextInput } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
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

const loadChildren = (parent) =>
  call('frappe.desk.treeview.get_children', { doctype: doctype.value, parent: parent || '' })
</script>

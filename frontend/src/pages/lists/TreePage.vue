<template>
  <div class="flex h-full flex-col bg-app-bg">
    <SubNavbar :title="doctype">
      <template #left><ViewSwitcher :doctype="doctype" current="tree" /></template>
      <AppSearchInput v-model="search" class="w-full" placeholder="Search">
        <template #suffix>
          <Popover trigger="click" placement="bottom-end">
            <template #target="{ togglePopover }">
              <FeatherIcon
                name="info"
                class="h-4 w-4 cursor-pointer text-app-text-muted hover:text-app-primary"
                @click="togglePopover()"
              />
            </template>
            <template #body="{ close }">
              <div
                class="my-2 w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-app-border bg-app-panel shadow-xl"
              >
                <div class="flex items-center gap-2 border-b border-app-border bg-app-panel-2 px-4 py-3">
                  <FeatherIcon name="search" class="h-4 w-4 text-app-primary" />
                  <h4 class="text-p-base font-semibold text-app-text">Search syntax</h4>
                </div>
                <p class="border-b border-app-border px-4 py-2 text-p-xs text-app-text-muted">
                  Click a filter below to apply it to the search bar.
                </p>
                <div class="flex flex-col divide-y divide-app-border">
                  <div v-for="group in treeSearchSyntaxHelp" :key="group.title" class="flex flex-col gap-2.5 px-4 py-3">
                    <p class="text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">{{ group.title }}</p>
                    <div v-for="row in group.rows" :key="row.example" class="flex flex-col gap-1">
                      <button
                        type="button"
                        class="block w-fit max-w-full whitespace-pre-wrap break-words rounded-md bg-app-panel-2 px-2 py-1 text-left font-mono text-p-xs text-app-primary hover:bg-app-primary-tint"
                        @click="search = row.example, close()"
                      >
                        {{ row.example }}
                      </button>
                      <span class="text-p-sm leading-snug text-app-text-muted">{{ row.description }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </Popover>
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
import AppSearchInput from '@/components/ui/AppSearchInput.vue'
// Generic tree view for any tree doctype (Company, Item Category, ...) via
// Frappe's stock treeview endpoint. The Account tree has its own page
// (AccountTreePage.vue) - it needs company scoping and balances.
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call, FeatherIcon, Popover } from 'frappe-ui'
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
      { example: 'parth', description: 'A plain word matches any visible column instead.' },
    ],
  },
  {
    title: 'Combine conditions',
    rows: [
      { example: 'name=parth type=Bank', description: 'Multiple fields - all must match (AND).' },
      { example: 'name=parth or type=Bank', description: 'Either one can match (OR) instead.' },
    ],
  },
  {
    title: 'Compare & range',
    rows: [
      { example: 'name!=parth', description: 'Not equal, also works with >, <, >=, <=.' },
      { example: 'name between a to m', description: 'A range on one field.' },
    ],
  },
]

const loadChildren = (parent) =>
  call('frappe.desk.treeview.get_children', { doctype: doctype.value, parent: parent || '' })
</script>

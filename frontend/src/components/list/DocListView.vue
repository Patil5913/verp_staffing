<template>
  <div class="flex h-full flex-col">
    <!-- Sub navbar: doc name, search, refresh -->
    <div
      class="grid h-11 shrink-0 grid-cols-3 items-center border-b border-app-border bg-app-panel px-6"
    >
      <h1 class="min-w-0 shrink-0 truncate text-p-lg font-medium text-app-text">{{ doctype }}</h1>

      <div class="flex min-w-0 flex-1 items-center gap-2">
        <TextInput
          v-model="searchText"
          class="w-full"
          placeholder='Try: "status=open", "modified between 17 sept to 25 sept"'
        >
          <template #prefix>
            <FeatherIcon name="search" class="h-4 w-4 text-app-text-muted" />
          </template>
          <template #suffix>
            <Popover trigger="hover" :hover-delay="0.15" :leave-delay="0.15" placement="bottom-end">
              <template #target>
                <FeatherIcon
                  name="info"
                  class="h-4 w-4 cursor-help text-app-text-muted hover:text-app-primary"
                />
              </template>
              <template #body>
                <div
                  class="my-2 w-[26rem] overflow-hidden rounded-xl border border-app-border bg-app-panel shadow-xl"
                >
                  <div class="flex items-center gap-2 border-b border-app-border bg-app-panel-2 px-4 py-3">
                    <FeatherIcon name="search" class="h-4 w-4 text-app-primary" />
                    <h4 class="text-p-base font-semibold text-app-text">Search syntax</h4>
                  </div>

                  <div class="flex flex-col divide-y divide-app-border">
                    <div
                      v-for="group in searchSyntaxHelp"
                      :key="group.title"
                      class="flex flex-col gap-2.5 px-4 py-3"
                    >
                      <p class="text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">
                        {{ group.title }}
                      </p>
                      <div v-for="row in group.rows" :key="row.example" class="flex flex-col gap-1">
                        <code
                          class="block w-fit max-w-full whitespace-pre-wrap break-words rounded-md bg-app-panel-2 px-2 py-1 font-mono text-p-xs text-app-primary"
                          >{{ row.example }}</code
                        >
                        <span class="text-p-sm leading-snug text-app-text-muted">{{ row.description }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </template>
            </Popover>
          </template>
        </TextInput>

        <Button
          variant="outline"
          theme="red"
          icon="x"
          tooltip="Clear search"
          :disabled="!hasFilters"
          @click="clearFilters"
        />
      </div>

      <div class="flex items-center justify-end gap-2">
        <AppButton v-if="canCreate" variant="primary" icon="plus" @click="showQuickCreate = true">
          Add New
        </AppButton>
        <AppButton v-if="canDelete && selected.size" variant="danger" icon="trash-2" @click="confirmBulkDelete">
          Delete ({{ selected.size }})
        </AppButton>
        <Button
          v-if="isAdmin"
          variant="ghost"
          icon="settings"
          tooltip="Customize columns"
          @click="showCustomizeColumns = true"
        />
        <Button variant="ghost" icon="refresh-cw" tooltip="Refresh" @click="refresh" />
      </div>
    </div>

    <!-- Scrollable body: permission / error / loading states, or the table -->
    <div class="flex min-h-0 flex-1 flex-col gap-3 px-6 py-3">
      <StateBanner
        v-if="meta.isPermissionError"
        icon="lock"
        title="Permission denied"
        :description="`You don't have access to view ${doctype}.`"
      />
      <StateBanner
        v-else-if="meta.hasError"
        icon="alert-triangle"
        title="Couldn't load this list"
        :description="meta.errorMessage"
      />
      <div v-else-if="meta.isLoading && !meta.resource.data" class="flex justify-center py-16">
        <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
      </div>

      <template v-else>
        <StateBanner
          v-if="docs.isPermissionError"
          icon="lock"
          title="Permission denied"
          :description="`You don't have access to view ${doctype}.`"
        />
        <StateBanner
          v-else-if="docs.hasError"
          icon="alert-triangle"
          title="Couldn't load records"
          :description="docs.errorMessage"
        />

        <div
          v-else
          class="doc-table-scroll max-h-full overflow-auto rounded-lg border border-app-border bg-app-panel"
        >
          <table v-if="rows.length" class="doc-table w-full table-fixed border-collapse">
            <thead>
              <tr>
                <th v-if="canDelete" class="sticky top-0 h-11 w-10 border-b border-app-border bg-app-panel-2 px-3">
                  <Checkbox :model-value="allSelected" @click.stop @update:model-value="toggleSelectAll" />
                </th>
                <th
                  v-for="column in columns"
                  :key="column.key"
                  class="sticky top-0 h-11 cursor-pointer select-none truncate border-b border-app-border bg-app-panel-2 px-3 text-left text-p-base font-semibold text-app-text-muted hover:text-app-text"
                  @click="onSort(column.key)"
                >
                  <span class="inline-flex items-center gap-1">
                    {{ column.label }}
                    <FeatherIcon
                      v-if="sortField === column.key"
                      :name="sortOrder === 'asc' ? 'arrow-up' : 'arrow-down'"
                      class="h-3.5 w-3.5 shrink-0"
                    />
                  </span>
                </th>
                <th v-if="canDelete" class="sticky top-0 h-11 w-12 border-b border-app-border bg-app-panel-2 px-2" />
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in rows"
                :key="row.name"
                class="cursor-pointer hover:bg-app-panel-2"
                @click="openRow(row)"
              >
                <td v-if="canDelete" class="h-11 w-10 border-b border-app-border px-3" @click.stop>
                  <Checkbox
                    :model-value="selected.has(row.name)"
                    @click.stop
                    @update:model-value="toggleSelectRow(row.name)"
                  />
                </td>
                <td
                  v-for="column in columns"
                  :key="column.key"
                  class="h-11 truncate border-b border-app-border px-3 text-base"
                >
                  <Badge
                    v-if="isSelectColumn(column.key)"
                    :label="row[column.key]"
                    :theme="statusBadgeTheme(row[column.key])"
                    size="md"
                  />
                  <span v-else class="truncate">{{ row[column.key] }}</span>
                </td>
                <td v-if="canDelete" class="h-11 w-12 border-b border-app-border px-2 text-center" @click.stop>
                  <Dropdown :options="rowActions(row)" placement="left">
                    <template #default="{ open }">
                      <Button variant="ghost" icon="more-horizontal" :class="open ? 'bg-app-panel-2' : ''" />
                    </template>
                  </Dropdown>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="flex flex-col items-center justify-center gap-1 py-16 text-center">
            <p class="text-p-base font-medium text-app-text">No records</p>
            <p class="text-p-sm text-app-text-muted">No records match your filters yet.</p>
          </div>
        </div>
      </template>
    </div>

    <!-- Footer: page-length dropdown (left) + pagination (right), pinned to the bottom,
         flush with the sidebar's profile footer -->
    <div
      v-if="showFooter"
      class="flex h-[57px] shrink-0 items-center justify-between gap-2 border-t border-app-border bg-app-panel px-6"
    >
      <FormControl
        type="select"
        :model-value="String(pageLength)"
        :options="pageLengthOptions"
        @update:model-value="setPageLength(Number($event))"
        class="!w-20"
      />
      <span class="text-p-sm text-app-text-muted">
        {{ totalCount }} record{{ totalCount === 1 ? '' : 's' }}
      </span>
      <Pagination :page="page" :page-count="pageCount" @update:page="setPage" />
    </div>

    <CustomizeColumnsDialog
      v-if="isAdmin"
      v-model="showCustomizeColumns"
      :doctype="doctype"
      :fields="docfields"
      :list-fields="listFields"
      :columns-customized="columnsCustomized"
      @saved="onColumnsSaved"
    />

    <QuickCreateDialog v-if="showQuickCreate" v-model="showQuickCreate" :doctype="doctype" @created="refresh" />

    <Dialog
      v-model="showDeleteDialog"
      :options="{
        title: pendingDelete.length > 1 ? `Delete ${pendingDelete.length} records?` : 'Delete this record?',
        message: `This permanently deletes ${pendingDelete.length > 1 ? 'these records' : 'this record'}. This can't be undone.`,
        icon: { name: 'trash-2', appearance: 'danger' },
      }"
    >
      <template #actions>
        <AppButton variant="danger" icon="trash-2" :loading="deleting" @click="onConfirmDelete">Delete</AppButton>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, Button, Checkbox, Dialog, Dropdown, FeatherIcon, FormControl, LoadingIndicator, Popover, TextInput } from 'frappe-ui'
import { useDocList } from '@/composables/list/useDocList'
import { useResource } from '@/composables/list/useResource'
import { formatFieldValue } from '@/utils/list/formatValue'
import { statusBadgeTheme } from '@/utils/list/statusTheme'
import { notify } from '@/utils/common/notify'
import AppButton from '@/components/common/AppButton.vue'
import CustomizeColumnsDialog from './CustomizeColumnsDialog.vue'
import QuickCreateDialog from './QuickCreateDialog.vue'
import Pagination from './Pagination.vue'
import StateBanner from '../common/StateBanner.vue'

const props = defineProps({
  doctype: { type: String, required: true },
})

const router = useRouter()

function openRow(row) {
  // A plain path, not a named route: some doctypes (Lead, User) have their
  // own detail page routed ahead of the generic DocDetail one — see
  // router.js — and this lets vue-router pick whichever one matches instead
  // of this list view having to know which doctypes are customized.
  router.push(`/${encodeURIComponent(props.doctype)}/${encodeURIComponent(row.name)}`)
}

const showQuickCreate = ref(false)

const {
  meta,
  docs,
  page,
  pageCount,
  totalCount,
  pageLength,
  searchText,
  sortField,
  sortOrder,
  setPage,
  setPageLength,
  toggleSortOrder,
  clearFilters,
  refresh,
} = useDocList(props.doctype)

const pageLengthOptions = [15, 30, 50, 100].map((n) => ({ label: String(n), value: String(n) }))

const searchSyntaxHelp = [
  {
    title: 'Match a field',
    rows: [
      { example: 'status=open', description: 'Scope the match to one field, by its name or column label.' },
      { example: 'status="in progress"', description: 'Quote a value that has spaces.' },
      { example: 'parth', description: 'A plain word matches any searchable field instead.' },
    ],
  },
  {
    title: 'Combine conditions',
    rows: [
      { example: 'status=open name=parth', description: 'Multiple fields — all must match (AND).' },
      { example: 'status=open or name=parth', description: 'Either one can match (OR) instead.' },
    ],
  },
  {
    title: 'Compare numbers & dates',
    rows: [
      { example: 'status!=open', description: 'Not equal.' },
      { example: 'modified>=2026-09-17', description: 'Also works with >, <, <=.' },
    ],
  },
  {
    title: 'Date & number ranges',
    rows: [
      {
        example: 'modified between 17 sept to 25 sept',
        description: 'A range on one field — values here don’t need quotes.',
      },
    ],
  },
]

const showFooter = computed(() => {
  if (meta.isPermissionError || meta.hasError) return false
  if (meta.isLoading && !meta.resource.data) return false
  return !docs.isPermissionError && !docs.hasError
})

const hasFilters = computed(() => searchText.value.trim().length > 0)

const docfields = computed(() => meta.resource.data?.fields || [])
const listFields = computed(() => meta.resource.data?.list_fields || [])
const fieldMap = computed(() => Object.fromEntries(docfields.value.map((f) => [f.fieldname, f])))

const isAdmin = computed(() => Boolean(meta.resource.data?.is_admin))
const columnsCustomized = computed(() => Boolean(meta.resource.data?.columns_customized))
const showCustomizeColumns = ref(false)

// set_list_view_columns already returns a fresh get_list_view_meta payload,
// so apply it directly instead of round-tripping another meta fetch —
// avoids a race where docs.resource.reload() below would otherwise read
// list_fields before an async meta reload had resolved.
function onColumnsSaved(data) {
  meta.resource.setData(data)
  docs.resource.reload()
}

const columns = computed(() => listFields.value.map((f) => ({ key: f.fieldname, label: f.label })))

function isSelectColumn(key) {
  return fieldMap.value[key]?.fieldtype === 'Select'
}

function onSort(fieldname) {
  if (sortField.value === fieldname) {
    toggleSortOrder()
  } else {
    sortField.value = fieldname
    sortOrder.value = 'asc'
  }
}

const rows = computed(() =>
  (docs.resource.data || []).map((row) => {
    const displayRow = { name: row.name }
    for (const column of columns.value) {
      displayRow[column.key] = formatFieldValue(row[column.key], fieldMap.value[column.key])
    }
    return displayRow
  }),
)

// Row selection + delete (single-row via the action menu, or bulk via the
// header checkbox) — both funnel through the same confirm dialog and the
// same delete_docs call, list_view.py returns per-name success/failure so a
// permission-restricted row in a bulk selection doesn't silently vanish.
const canDelete = computed(() => Boolean(meta.resource.data?.perms?.delete))
const canCreate = computed(() => Boolean(meta.resource.data?.perms?.create))

const selected = ref(new Set())

// Selection is scoped to the current page's rows — reset whenever the
// visible page changes so stale names from a previous page can't linger.
watch(rows, () => (selected.value = new Set()))

const allSelected = computed(() => rows.value.length > 0 && rows.value.every((row) => selected.value.has(row.name)))

function toggleSelectAll() {
  selected.value = allSelected.value ? new Set() : new Set(rows.value.map((row) => row.name))
}

function toggleSelectRow(name) {
  const next = new Set(selected.value)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  selected.value = next
}

function rowActions(row) {
  return [
    {
      label: 'Delete',
      icon: 'trash-2',
      theme: 'red',
      onClick: () => confirmDelete([row.name]),
    },
  ]
}

const showDeleteDialog = ref(false)
const pendingDelete = ref([])

function confirmDelete(names) {
  pendingDelete.value = names
  showDeleteDialog.value = true
}

function confirmBulkDelete() {
  confirmDelete([...selected.value])
}

const deleteResource = useResource({
  url: 'verp_staffing.utils.list_view.delete_docs',
})
const deleting = computed(() => deleteResource.isLoading)

async function onConfirmDelete() {
  const names = pendingDelete.value
  const result = await deleteResource.resource.submit({ doctype: props.doctype, names })
  if (!result) return // request itself failed; useResource already toasted it

  showDeleteDialog.value = false
  selected.value = new Set()

  if (result.deleted.length) {
    notify.success(`Deleted ${result.deleted.length} record${result.deleted.length > 1 ? 's' : ''}.`)
  }
  if (result.failed.length) {
    notify.error(result.failed.map((f) => f.error).join('\n'))
  }
  refresh()
}
</script>

<style scoped>
.doc-table tbody tr:last-child td {
  border-bottom: none;
}

.doc-table-scroll {
  scrollbar-width: thin;
  scrollbar-color: var(--app-border) transparent;
}

.doc-table-scroll::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.doc-table-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.doc-table-scroll::-webkit-scrollbar-thumb {
  background-color: var(--app-border);
  border-radius: 9999px;
  border: 2px solid var(--app-panel);
  background-clip: padding-box;
}

.doc-table-scroll::-webkit-scrollbar-thumb:hover {
  background-color: var(--app-text-muted);
  background-clip: padding-box;
}

.doc-table-scroll::-webkit-scrollbar-corner {
  background: transparent;
}
</style>

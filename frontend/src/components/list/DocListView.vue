<template>
  <div class="flex h-full flex-col">
    <!-- Sub navbar: doc name, search, filters, refresh -->
    <div
      class="grid h-11 shrink-0 grid-cols-3 items-center border-b border-app-border bg-app-panel px-6"
    >
      <h1 class="min-w-0 shrink-0 truncate text-p-lg font-medium text-app-text">{{ doctype }}</h1>

      <div class="flex min-w-0 items-center justify-center gap-2">
        <TextInput
          v-model="searchText"
          class="w-56 shrink-0"
          placeholder='Search... try "parth OR engineer"'
        >
          <template #prefix>
            <FeatherIcon name="search" class="h-4 w-4 text-app-text-muted" />
          </template>
        </TextInput>

        <DocFilterPanel v-model="filters" :docfields="docfields" />

        <Button
          variant="outline"
          theme="red"
          icon="x"
          tooltip="Clear filters"
          :disabled="!hasFilters"
          @click="clearFilters"
        />
      </div>

      <div class="flex justify-end">
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
                <th
                  v-for="column in columns"
                  :key="column.key"
                  class="sticky top-0 z-10 h-11 cursor-pointer select-none truncate border-b border-app-border bg-app-panel-2 px-3 text-left text-p-base font-semibold text-app-text-muted hover:text-app-text"
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
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.name" class="hover:bg-app-panel-2">
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
      <Pagination :page="page" :page-count="pageCount" @update:page="setPage" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Badge, Button, FeatherIcon, FormControl, LoadingIndicator, TextInput } from 'frappe-ui'
import { useDocList } from '@/composables/list/useDocList'
import { formatFieldValue } from '@/utils/list/formatValue'
import { statusBadgeTheme } from '@/utils/list/statusTheme'
import DocFilterPanel from './DocFilterPanel.vue'
import Pagination from './Pagination.vue'
import StateBanner from '../common/StateBanner.vue'

const props = defineProps({
  doctype: { type: String, required: true },
})

const {
  meta,
  docs,
  page,
  pageCount,
  pageLength,
  filters,
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

const showFooter = computed(() => {
  if (meta.isPermissionError || meta.hasError) return false
  if (meta.isLoading && !meta.resource.data) return false
  return !docs.isPermissionError && !docs.hasError
})

const hasFilters = computed(() => Object.keys(filters.value).length > 0)

const docfields = computed(() => meta.resource.data?.fields || [])
const listFields = computed(() => meta.resource.data?.list_fields || [])
const fieldMap = computed(() => Object.fromEntries(docfields.value.map((f) => [f.fieldname, f])))

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

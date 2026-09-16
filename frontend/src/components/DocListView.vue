<template>
  <div class="flex flex-col gap-3">
    <!-- Toolbar: search, filters, sort -->
    <div class="flex flex-wrap items-center gap-2">
      <TextInput
        v-model="searchText"
        class="min-w-[240px] flex-1"
        placeholder='Search... try "parth OR engineer"'
      >
        <template #prefix>
          <FeatherIcon name="search" class="h-4 w-4 text-app-text-muted" />
        </template>
      </TextInput>

      <DocFilterPanel v-model="filters" :docfields="docfields" />

      <FormControl type="select" v-model="sortField" :options="sortOptions" class="!w-44" />
      <Button
        variant="outline"
        :icon="sortOrder === 'asc' ? 'arrow-up' : 'arrow-down'"
        @click="toggleSortOrder"
      />

      <Button variant="ghost" icon="refresh-cw" @click="refresh" />
    </div>

    <!-- Permission / error / loading states -->
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

      <div v-else class="overflow-hidden rounded-lg border border-app-border bg-app-panel">
        <ListView
          :columns="columns"
          :rows="rows"
          row-key="name"
          :options="listOptions"
        >
          <template #cell="{ column, item }">
            <Badge v-if="isSelectColumn(column.key) && item" :label="item" theme="gray" />
            <div v-else class="truncate text-base">{{ item }}</div>
          </template>
        </ListView>
      </div>

      <div v-if="!docs.hasError" class="flex flex-wrap items-center justify-between gap-2">
        <div class="text-p-base text-app-text-muted">{{ rangeLabel }}</div>
        <Pagination :page="page" :page-count="pageCount" @update:page="setPage" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Badge, Button, FeatherIcon, FormControl, ListView, LoadingIndicator, TextInput } from 'frappe-ui'
import { useDocList } from '@/composables/useDocList'
import { formatFieldValue, formatRelativeTime } from '@/utils/formatValue'
import DocFilterPanel from './DocFilterPanel.vue'
import Pagination from './Pagination.vue'
import StateBanner from './StateBanner.vue'

const props = defineProps({
  doctype: { type: String, required: true },
})

const {
  meta,
  docs,
  page,
  pageCount,
  totalCount,
  pageLength,
  filters,
  searchText,
  sortField,
  sortOrder,
  setPage,
  toggleSortOrder,
  refresh,
} = useDocList(props.doctype)

const docfields = computed(() => meta.resource.data?.fields || [])
const listFields = computed(() => meta.resource.data?.list_fields || [])
const fieldMap = computed(() => Object.fromEntries(docfields.value.map((f) => [f.fieldname, f])))

const sortOptions = computed(() => {
  const options = listFields.value.map((f) => ({ label: f.label, value: f.fieldname }))
  const extras = [
    { label: 'Last Updated', value: 'modified' },
    { label: 'Created On', value: 'creation' },
    { label: 'ID', value: 'name' },
  ]
  for (const extra of extras) {
    if (!options.some((o) => o.value === extra.value)) options.push(extra)
  }
  return options
})

const columns = computed(() => [
  ...listFields.value.map((f) => ({ key: f.fieldname, label: f.label })),
  { key: '_modified', label: 'Last Updated' },
])

function isSelectColumn(key) {
  return fieldMap.value[key]?.fieldtype === 'Select'
}

const rows = computed(() =>
  (docs.resource.data || []).map((row) => {
    const displayRow = { name: row.name }
    for (const column of columns.value) {
      if (column.key === '_modified') {
        displayRow._modified = formatRelativeTime(row.modified)
      } else {
        displayRow[column.key] = formatFieldValue(row[column.key], fieldMap.value[column.key])
      }
    }
    return displayRow
  }),
)

const listOptions = {
  selectable: false,
  showTooltip: true,
  emptyState: {
    title: 'No records',
    description: 'No records match your filters yet.',
  },
}

const rangeLabel = computed(() => {
  if (!totalCount.value) return 'No records'
  const start = (page.value - 1) * pageLength + 1
  const end = Math.min(page.value * pageLength, totalCount.value)
  return `${start}–${end} of ${totalCount.value}`
})
</script>

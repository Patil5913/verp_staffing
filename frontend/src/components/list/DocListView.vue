<template>
  <div class="flex h-full flex-col">
    <!-- Sub navbar: doc name, search, refresh -->
    <div
      class="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-2 border-b border-app-border bg-app-panel px-3 py-2 md:grid md:h-11 md:grid-cols-[minmax(0,1fr)_minmax(0,2.25fr)_minmax(0,1fr)] md:gap-3 md:px-6 md:py-0"
    >
      <div class="flex min-w-0 flex-1 items-center gap-3 md:flex-none">
        <h1
          class="flex min-w-0 shrink-0 items-center gap-1.5 truncate rounded-lg border border-app-primary/15 bg-app-primary-tint px-3 py-1 text-p-lg font-semibold tracking-tight text-app-primary"
        >
          <span :class="['lucide-' + titleIcon, 'size-4', 'shrink-0', 'text-app-primary']" />
          <span class="truncate">{{ doctype }}</span>
        </h1>
        <ViewSwitcher :doctype="doctype" current="list" />
      </div>

      <div class="order-last flex w-full min-w-0 items-center gap-2 md:order-none md:w-full">
        <AppSearchInput
          v-model="searchText"
          class="w-full"
          placeholder='Try: "status=open", "modified between 17 sept to 25 sept"'
        >
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
                  class="my-2 w-[min(26rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-app-border bg-app-panel shadow-xl"
                >
                  <div class="flex items-center gap-2 border-b border-app-border bg-app-panel-2 px-4 py-3">
                    <FeatherIcon name="search" class="h-4 w-4 text-app-primary" />
                    <h4 class="text-p-base font-semibold text-app-text">Search syntax</h4>
                  </div>
                  <p class="border-b border-app-border px-4 py-2 text-p-xs text-app-text-muted">
                    Click a filter below to apply it to the search bar.
                  </p>

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
                        <button
                          type="button"
                          class="block w-fit max-w-full whitespace-pre-wrap break-words rounded-md bg-app-panel-2 px-2 py-1 text-left font-mono text-p-xs text-app-primary hover:bg-app-primary-tint"
                          @click="searchText = row.example, close()"
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
          :disabled="!hasFilters"
          @click="clearFilters"
        />
      </div>

      <div class="ml-auto flex items-center justify-end gap-2">
        <AppButton
          v-if="canDelete && selected.size"
          variant="danger"
          icon="trash-2"
          :tooltip="`Delete (${selected.size})`"
          @click="confirmBulkDelete"
        />
        <AppButton v-if="canCreate" variant="primary" icon="plus" tooltip="Add New" @click="onAddNew" />
        <AppButton
          v-for="action in bulkActions"
          v-show="selected.size"
          :key="action.label"
          variant="outline"
          :icon="action.icon"
          :loading="runningAction === action.label"
          :disabled="!!runningAction"
          @click="runBulkAction(action)"
        >
          {{ action.label }} ({{ selected.size }})
        </AppButton>
        <AppButton
          v-if="isAdmin"
          variant="surface"
          icon="settings"
          tooltip="Customize columns"
          @click="showCustomizeColumns = true"
        />
        <AppButton v-if="doctype === 'Interview'" variant="outline" size="sm" icon="users" @click="showCustomerDialog = true">
          Select Customer
        </AppButton>
        <AppButton variant="surface" icon="refresh-cw" tooltip="Refresh" @click="refresh" />
      </div>
    </div>

    <!-- Scrollable body: permission / error / loading states, or the table -->
    <div class="flex min-h-0 flex-1 flex-col gap-3 px-3 md:px-6 py-3">
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
        <component :is="headerComponent" v-if="headerComponent" ref="headerRef" :doctype="doctype" @filter="(text) => (searchText = text)" />
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
          <div v-if="docs.isLoading && !docs.resource.data" class="flex justify-center py-16">
            <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
          </div>
          <table v-else-if="rows.length" class="doc-table w-full min-w-[42rem] table-fixed border-collapse md:min-w-0">
            <colgroup>
              <col v-if="canDelete" class="w-10" />
              <col v-for="column in columns" :key="column.key" :style="colStyle(column.key)" />
              <col :class="rowActionDefs.length ? 'w-36' : 'w-12'" />
            </colgroup>
            <thead>
              <tr>
                <th v-if="canDelete" class="sticky top-0 h-11 w-10 border-b border-app-border bg-app-panel-2 px-3">
                  <AppCheckbox :model-value="allSelected" :indeterminate="!allSelected && selected.size > 0" @click.stop @update:model-value="toggleSelectAll" />
                </th>
                <th
                  v-for="column in columns"
                  :key="column.key"
                  class="sticky top-0 h-11 cursor-pointer select-none truncate border-b border-r border-app-border bg-app-panel-2 px-3 text-left text-p-base font-semibold text-app-text-muted hover:text-app-text"
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
                  <span
                    class="group absolute right-0 top-0 flex h-full w-2 cursor-col-resize justify-end"
                    @click.stop
                    @mousedown.prevent.stop="startResize($event, column.key)"
                  >
                    <span class="w-0.5 group-hover:bg-app-text-muted" />
                  </span>
                </th>
                <th class="sticky top-0 h-11 border-b border-app-border bg-app-panel-2 px-2" :class="rowActionDefs.length ? 'w-36' : 'w-12'" />
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
                  <AppCheckbox
                    :model-value="selected.has(row.name)"
                    @click.stop
                    @update:model-value="toggleSelectRow(row.name)"
                  />
                </td>
                <td
                  v-for="column in columns"
                  :key="column.key"
                  class="h-11 truncate border-b border-r border-app-border px-3 text-base"
                >
                  <AppBadge
                    v-if="isDocstatusColumn(column.key) && listStatusColumn(doctype, rawRowByName[row.name])"
                    :label="listStatusColumn(doctype, rawRowByName[row.name]).label"
                    :theme="listStatusColumn(doctype, rawRowByName[row.name]).theme"
                    size="md"
                  />
                  <AppBadge
                    v-else-if="isDocstatusColumn(column.key)"
                    :label="docstatusBadge(row[column.key]).label"
                    :theme="docstatusBadge(row[column.key]).theme"
                    size="md"
                  />
                  <AppBadge
                    v-else-if="isUserStatusColumn(column.key)"
                    :label="userStatusBadge(row[column.key]).label"
                    :theme="userStatusBadge(row[column.key]).theme"
                    size="md"
                  />
                  <AppBadge
                    v-else-if="isSelectColumn(column.key)"
                    :label="row[column.key]"
                    :theme="statusBadgeTheme(row[column.key], { doctype, fieldname: column.key })"
                    size="md"
                  />
                  <span v-else class="truncate">{{ row[column.key] }}</span>
                </td>
                <td class="h-11 border-b border-app-border px-2 text-right" :class="rowActionDefs.length ? 'w-36' : 'w-12 text-center'" @click.stop>
                  <div class="flex items-center justify-end gap-1">
                    <AppButton
                      v-if="primaryRowAction && primaryRowAction.when(row)"
                      variant="outline"
                      size="sm"
                      :icon="primaryRowAction.icon"
                      :loading="runningAction === `${primaryRowAction.label}:${row.name}`"
                      :disabled="!!runningAction"
                      @click="runAction(primaryRowAction, [row.name], `${primaryRowAction.label}:${row.name}`)"
                    >{{ primaryRowAction.label }}</AppButton>
                    <Dropdown v-if="rowActions(row).length" :options="rowActions(row)" placement="left">
                      <template #default="{ open }">
                        <AppButton variant="ghost" icon="more-horizontal" :class="open ? 'bg-app-panel-2' : ''" />
                      </template>
                    </Dropdown>
                  </div>
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
      class="flex h-[57px] shrink-0 items-center justify-between gap-2 border-t border-app-border bg-app-panel px-3 md:px-6"
    >
      <AppCombobox
        :model-value="String(pageLength)"
        :options="pageLengthOptions"
        compact
        class="w-20"
        @update:model-value="setPageLength(Number($event))"
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

    <PersonQuickCreateDialog
      v-if="showQuickCreate && isPersonDoctype"
      v-model="showQuickCreate"
      :doctype="doctype"
      @created="refresh"
    />
    <QuickCreateDialog v-else-if="showQuickCreate" v-model="showQuickCreate" :doctype="doctype" @created="refresh" />

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

    <SelectCustomerDialog v-if="doctype === 'Interview'" v-model="showCustomerDialog" @applied="refresh" />
  </div>
</template>

<script setup>
import AppBadge from '@/components/ui/AppBadge.vue'
import AppSearchInput from '@/components/ui/AppSearchInput.vue'
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'
import { computed, ref, watch } from 'vue'
import { columnWidths } from '@/composables/list/useColumnWidths'
import { useRouter } from 'vue-router'
import { Dialog, Dropdown, FeatherIcon, LoadingIndicator, Popover, call } from 'frappe-ui'
import { useDocList } from '@/composables/list/useDocList'
import { useResource } from '@/composables/list/useResource'
import { useMarketingCustomerFilter } from '@/composables/list/useMarketingCustomerFilter'
import SelectCustomerDialog from './SelectCustomerDialog.vue'
import { formatFieldValue } from '@/utils/list/formatValue'
import { statusBadgeTheme, docstatusBadge, listStatusColumn, hasStatusOverride } from '@/utils/list/statusTheme'
import ViewSwitcher from '@/components/common/ViewSwitcher.vue'
import { BULK_ACTIONS, LIST_HEADERS, NO_MANUAL_CREATE, ROW_ACTIONS } from '@/configs/detail/listOptions'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'
import AppButton from '@/components/ui/AppButton.vue'
import CustomizeColumnsDialog from './CustomizeColumnsDialog.vue'
import QuickCreateDialog from './QuickCreateDialog.vue'
import PersonQuickCreateDialog from '@/components/common/PersonQuickCreateDialog.vue'
import { PERSON_DOCTYPES, STATUS_COLUMN_FIELDS_TO_HIDE } from '@/configs/detail/listOptions'
import Pagination from './Pagination.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { resolveIconName } from '@/utils/layout/sidebarIcons'

// A doctype name's sidebar nav key is normally just its kebab-case form
// ("Sales Invoice" -> "sales-invoice") - see sidebarIcons.js's
// KEY_ICON_OVERRIDES - except the handful listed here whose nav key doesn't
// follow that pattern.
const SIDEBAR_KEY_OVERRIDES = { 'Interview Support': 'interview_support' }
function sidebarKey(doctype) {
  return SIDEBAR_KEY_OVERRIDES[doctype] || doctype.toLowerCase().replace(/\s+/g, '-')
}

const props = defineProps({
  doctype: { type: String, required: true },
})

const router = useRouter()

const titleIcon = computed(() => resolveIconName(null, sidebarKey(props.doctype)))

// Interview's "Select Customer" scoping - same shared selection Kanban/
// Calendar read/write, applied here as an extra get_list filter.
const showCustomerDialog = ref(false)
const { selectedCustomers, ensureDefaultCustomers } = useMarketingCustomerFilter()
const interviewExtraFilters = computed(() =>
  props.doctype === 'Interview' && selectedCustomers.value.length ? [['marketing_link', 'in', selectedCustomers.value]] : [],
)
if (props.doctype === 'Interview') ensureDefaultCustomers()

function openRow(row) {
  // A plain path, not a named route: some doctypes (Lead, User) have their
  // own detail page routed ahead of the generic DocDetail one - see
  // router.js - and this lets vue-router pick whichever one matches instead
  // of this list view having to know which doctypes are customized.
  router.push(`/${encodeURIComponent(props.doctype)}/${encodeURIComponent(row.name)}`)
}

const showQuickCreate = ref(false)
const isPersonDoctype = computed(() => PERSON_DOCTYPES.has(props.doctype))

// Decide quick-dialog-vs-full-form *before* opening anything - meta.resource
// is already loaded by the time this button is clickable, so this is
// synchronous, unlike the generic QuickCreateDialog's own after-the-fact
// check (which used to flash the dialog open for a moment before redirecting
// once it discovered quick_entry was off).
function onAddNew() {
  if (isPersonDoctype.value || meta.resource.data?.quick_entry) {
    showQuickCreate.value = true
  } else {
    router.push(`/${encodeURIComponent(props.doctype)}/new`)
  }
}

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
} = useDocList(props.doctype, { extraFilters: interviewExtraFilters })

const pageLengthOptions = [15, 30, 50, 100].map((n) => ({ label: String(n), value: String(n) }))

// Search-syntax examples, built from this doctype's own visible columns
// instead of hardcoded field names, so "status=open" only shows up when
// this list actually has a status-like column to match against.
const primaryExampleField = computed(() => firstSelectField.value?.fieldname || columns.value[0]?.key || 'name')
const primaryExampleValue = computed(() => fieldOptions(firstSelectField.value || {})[0] || 'value')
const secondaryExampleField = computed(() => {
  const col = columns.value.find((c) => c.key !== primaryExampleField.value)
  return col?.key || 'name'
})
const dateExampleField = computed(() => {
  const dateField = docfields.value.find((f) => ['Date', 'Datetime'].includes(f.fieldtype))
  return dateField?.fieldname || 'modified'
})

const searchSyntaxHelp = computed(() => {
  const field = primaryExampleField.value
  const value = primaryExampleValue.value
  const quotedValue = /\s/.test(value) ? `"${value}"` : value
  const field2 = secondaryExampleField.value
  const dateField = dateExampleField.value

  return [
    {
      title: 'Match a field',
      rows: [
        { example: `${field}=${value}`, description: 'Scope the match to one field, by its name or column label.' },
        { example: `${field}=${quotedValue}`, description: 'Quote a value that has spaces.' },
        { example: value, description: 'A plain word matches any searchable field instead.' },
      ],
    },
    {
      title: 'Combine conditions',
      rows: [
        { example: `${field}=${value} ${field2}=parth`, description: 'Multiple fields - all must match (AND).' },
        { example: `${field}=${value} or ${field2}=parth`, description: 'Either one can match (OR) instead.' },
      ],
    },
    {
      title: 'Compare numbers & dates',
      rows: [
        { example: `${field}!=${value}`, description: 'Not equal.' },
        { example: `${dateField}>=2026-09-17`, description: 'Also works with >, <, <=.' },
      ],
    },
    {
      title: 'Date & number ranges',
      rows: [
        {
          example: `${dateField} between 17 sept to 25 sept`,
          description: 'A range on one field - values here don’t need quotes.',
        },
      ],
    },
  ]
})

const showFooter = computed(() => {
  if (meta.isPermissionError || meta.hasError) return false
  if (meta.isLoading && !meta.resource.data) return false
  return !docs.isPermissionError && !docs.hasError
})

const hasFilters = computed(() => searchText.value.trim().length > 0)

// The first Select field's options, used only to make the search-syntax
// examples below reference a real field/value on this doctype.
const firstSelectField = computed(() => docfields.value.find((f) => f.fieldtype === 'Select' && f.options))
function fieldOptions(field) {
  return (field.options || '').split('\n').map((o) => o.trim()).filter(Boolean)
}

const docfields = computed(() => meta.resource.data?.fields || [])
const listFields = computed(() => meta.resource.data?.list_fields || [])
const fieldMap = computed(() => Object.fromEntries(docfields.value.map((f) => [f.fieldname, f])))

const isAdmin = computed(() => Boolean(meta.resource.data?.is_admin))
const columnsCustomized = computed(() => Boolean(meta.resource.data?.columns_customized))
const showCustomizeColumns = ref(false)

// set_list_view_columns already returns a fresh get_list_view_meta payload,
// so apply it directly instead of round-tripping another meta fetch -
// avoids a race where docs.resource.reload() below would otherwise read
// list_fields before an async meta reload had resolved.
function onColumnsSaved(data) {
  meta.resource.setData(data)
  docs.resource.reload()
}

const isSubmittable = computed(() => Boolean(meta.resource.data?.is_submittable))

// A fixed, non-customizable leading column - not part of list_fields/the
// Customize Columns picker, since it's derived from docstatus rather than a
// real doctype field.
// Column widths live only in module memory: they survive navigating between
// lists but reset on a hard refresh (deliberately not persisted).
function colStyle(key) {
  const w = columnWidths[`${props.doctype}:${key}`]
  return w ? { width: `${w}px` } : {}
}
function startResize(e, key) {
  const startX = e.clientX
  const startW = e.target.closest('th').offsetWidth
  const id = `${props.doctype}:${key}`
  const move = (ev) => { columnWidths[id] = Math.max(60, startW + ev.clientX - startX) }
  const up = () => {
    window.removeEventListener('mousemove', move)
    window.removeEventListener('mouseup', up)
  }
  window.addEventListener('mousemove', move)
  window.addEventListener('mouseup', up)
}

const columns = computed(() => {
  const hideFields = STATUS_COLUMN_FIELDS_TO_HIDE[props.doctype] || new Set()
  const cols = listFields.value.filter((f) => !hideFields.has(f.fieldname)).map((f) => ({ key: f.fieldname, label: f.label }))
  return isSubmittable.value ? [{ key: 'docstatus', label: 'Status' }, ...cols] : cols
})

function isSelectColumn(key) {
  // Customer.overall_status is a Data field carrying status-like text
  // (Pending Verification, Ready, ...), not a Select - it still needs the
  // same badge/color treatment (statusBadgeTheme's DOCTYPE_FIELD_OVERRIDES
  // already has its exact mapping), so badge eligibility can't be gated on
  // fieldtype alone, only on "does the theme resolver have anything to say
  // about it" - a plain Select column trivially always does (falls through
  // its generic keyword vocabulary), one of these fieldtype-agnostic
  // overrides only fires for the specific doctype.fieldname it targets.
  return fieldMap.value[key]?.fieldtype === 'Select' || hasStatusOverride(props.doctype, key)
}

function isUserStatusColumn(key) {
  return (
    ((props.doctype === 'User' || props.doctype === 'Employee') && key === 'enabled') ||
    (props.doctype === 'Role' && key === 'disabled')
  )
}

function userStatusBadge(value) {
  // Role stores "disabled", so its Yes/No is inverted relative to "enabled".
  const active = props.doctype === 'Role' ? value !== 'Yes' : value === 'Yes'
  if (props.doctype === 'User') return { label: value, theme: active ? 'green' : 'red' }
  return { label: active ? 'Active' : 'Inactive', theme: active ? 'green' : 'red' }
}

function isDocstatusColumn(key) {
  return key === 'docstatus' && isSubmittable.value
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

// The raw (unformatted) row a display row came from - needed by
// listStatusColumn (payment_term_row/verification_status aren't
// list_fields, so they never make it into displayRow above).
const rawRowByName = computed(() => Object.fromEntries((docs.resource.data || []).map((r) => [r.name, r])))

// Row selection + delete (single-row via the action menu, or bulk via the
// header checkbox) - both funnel through the same confirm dialog and the
// same delete_docs call, list_view.py returns per-name success/failure so a
// permission-restricted row in a bulk selection doesn't silently vanish.
const canDelete = computed(() => Boolean(meta.resource.data?.perms?.delete))
// CR / Onboardings are only ever created by forwarding a candidate (their desk
// list views hide the New button too) - see listOptions.js.
const canCreate = computed(() => Boolean(meta.resource.data?.perms?.create) && !NO_MANUAL_CREATE.has(props.doctype))

const selected = ref(new Set())

// Doctype-specific extras (listOptions.js): server actions on the ticked rows,
// and a header component (Email Queue's status strip).
const bulkActions = computed(() => BULK_ACTIONS[props.doctype] || [])
const headerComponent = computed(() => LIST_HEADERS[props.doctype] || null)
const headerRef = ref(null)
const runningAction = ref('')

// Send now / Retry ... on one row or every ticked one; the server answers
// { message, failed: [...] } and the list (and its header) reload after.
async function runAction(action, names, busyKey = action.label) {
  runningAction.value = busyKey
  try {
    const res = await call(action.method, { names: JSON.stringify(names) })
    if (res?.failed?.length) notify.error(res.message)
    else notify.success(res?.message || `${action.label} done`)
    refresh()
    headerRef.value?.reload?.()
  } catch (e) {
    notify.error(normalizeError(e).message)
  } finally {
    runningAction.value = ''
  }
}
const runBulkAction = (action) => runAction(action, [...selected.value])

const rowActionDefs = computed(() => ROW_ACTIONS[props.doctype] || [])
const primaryRowAction = computed(() => rowActionDefs.value[0] || null)

// Selection is scoped to the current page's rows - reset whenever the
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
  // the row's other server actions (Retry, ...), then Delete
  const extras = rowActionDefs.value
    .slice(1)
    .filter((action) => action.when(row))
    .map((action) => ({ label: action.label, icon: action.icon, onClick: () => runAction(action, [row.name], `${action.label}:${row.name}`) }))
  return [
    ...extras,
    { label: 'Edit', icon: 'edit', onClick: () => openRow(row) },
    ...(canCreate.value ? [{ label: 'Duplicate', icon: 'copy', onClick: () => duplicateRow(row) }] : []),
    ...(canDelete.value ? [{ label: 'Delete', icon: 'trash-2', theme: 'red', onClick: () => confirmDelete([row.name]) }] : []),
  ]
}

// Opens a new, unsaved record pre-filled with this one's scalar fields - the
// /new page takes defaults from the query string (see useDocDetail) - so the
// user can edit before saving. Child tables aren't carried over.
const SKIP_ON_DUPLICATE = ['name', 'owner', 'creation', 'modified', 'modified_by', 'docstatus', 'idx', 'amended_from']
async function duplicateRow(row) {
  try {
    const source = await call('frappe.client.get', { doctype: props.doctype, name: row.name })
    const query = {}
    for (const [key, value] of Object.entries(source)) {
      if (SKIP_ON_DUPLICATE.includes(key) || key.startsWith('_')) continue
      if (value === null || value === undefined || typeof value === 'object') continue
      query[key] = value
    }
    router.push({ path: `/${encodeURIComponent(props.doctype)}/new`, query })
  } catch (e) {
    notify.error(e?.messages?.[0] || e?.message || 'Could not duplicate this record.')
  }
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

<template>
  <div class="flex flex-col gap-3 rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-p-base font-medium text-app-text">{{ table.label }}<span v-if="table.reqd" class="text-red-600"> *</span></h3>
        <p class="text-p-sm text-app-text-muted">
          {{ rows.length }} {{ rows.length === 1 ? 'row' : 'rows' }}
        </p>
      </div>
      <AppButton v-if="!disabled && !atMaxRows" variant="outline" size="sm" icon="plus" @click="openRow(null)">
        Add Row
      </AppButton>
    </div>

    <div v-if="rows.length" class="flex flex-col gap-2">
      <div
        v-for="(row, idx) in rows"
        :key="idx"
        class="group flex cursor-pointer items-center gap-4 rounded-lg border border-app-border bg-app-panel-2/40 px-4 py-3 transition-colors hover:border-app-primary/40 hover:bg-app-panel-2"
        @click="openRow(idx)"
      >
        <div class="grid min-w-0 flex-1 grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-4">
          <div v-for="col in previewColumns" :key="col.fieldname" class="min-w-0">
            <p class="truncate text-p-xs text-app-text-muted">{{ col.label }}</p>
            <TruncatedText
              v-if="isWide(col)"
              :text="formatCell(col, row[col.fieldname])"
              class="text-p-sm text-app-text"
            />
            <p v-else class="truncate text-p-sm text-app-text">{{ formatCell(col, row[col.fieldname]) }}</p>
          </div>
        </div>
        <AppButton
          v-if="!disabled"
          variant="ghost"
          size="icon"
          icon="trash-2"
          class="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
          @click.stop="removeRow(idx)"
        />
      </div>
    </div>
    <div v-else class="rounded-lg border border-dashed border-app-border py-8 text-center text-p-sm text-app-text-muted">
      No rows yet.
    </div>

    <Dialog v-model="dialogOpen" :options="{ title: dialogTitle, size: dialogSize }">
      <template #body-content>
        <div class="flex flex-wrap gap-3">
          <div
            v-for="col in visibleColumns"
            :key="col.fieldname"
            :class="isWide(col) ? 'w-full' : 'w-[calc(50%-0.375rem)]'"
          >
            <!-- A read-only field nobody has filled in (e.g. the candidate's own feedback)
                 says so, instead of an empty disabled box. -->
            <div v-if="col.read_only && emptyReadOnlyTexts[col.fieldname] && !draft[col.fieldname]" class="flex flex-col gap-1.5">
              <label class="text-p-sm font-medium text-app-text-muted">{{ col.label }}</label>
              <p class="rounded-lg border border-app-border bg-app-panel-2/40 px-3 py-2 text-p-sm text-app-text-muted">{{ emptyReadOnlyTexts[col.fieldname] }}</p>
            </div>
            <FieldControl
              v-else
              :field="col"
              :model-value="draft[col.fieldname]"
              :link-query="resolvedLinkQueries?.[col.fieldname]"
              :disabled="disabled || col.read_only"
              show-errors
              @update:model-value="(v) => onFieldInput(col.fieldname, v)"
              @file-meta="(f) => onFileMeta(col.fieldname, f)"
            />
            <!-- Live, per-field guidance (e.g. must be MM-YYYY) as it is typed, not only once Done is clicked. -->
            <p v-if="fieldProblems[col.fieldname]" class="mt-1 text-p-xs text-red-600">{{ fieldProblems[col.fieldname] }}</p>
            <p
              v-if="col.fieldname === 'description'"
              class="mt-1 text-p-xs"
              :class="descriptionCharCount >= DESCRIPTION_MIN_LENGTH ? 'text-app-text-muted' : 'text-amber-600'"
            >
              {{ descriptionCharCount }} / {{ DESCRIPTION_MIN_LENGTH }} characters minimum
            </p>
          </div>
          <p v-if="rowError" class="w-full text-p-sm text-red-600">{{ rowError }}</p>
        </div>
      </template>
      <template #actions>
        <AppButton variant="primary" :loading="validating" @click="commitRow">Done</AppButton>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, inject, provide, ref } from 'vue'
import { siteNowIso, siteTodayIso } from '@/utils/common/siteTime'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import TruncatedText from '@/components/ui/TruncatedText.vue'
import FieldControl from './FieldControl.vue'
import { dependsOnPasses } from '@/utils/detail/dependsOn'
import { DESCRIPTION_MIN_LENGTH, rowFieldProblem } from '@/utils/detail/fieldProblems'

const props = defineProps({
  table: { type: Object, required: true },
  rows: { type: Array, required: true },
  disabled: { type: Boolean, default: false },
  // { <link column>: { query?, filters? } } - see FieldControl's linkQuery.
  // Either a static object, or a function of the row currently being
  // edited - (draft, rows, editingIndex) => { <col>: {query?, filters?} } -
  // for a column whose valid options depend on another field in the same
  // row (e.g. Role depends on that row's own Department) or on sibling
  // rows (e.g. "don't offer a role already used in another row").
  linkQueries: { type: [Object, Function], default: null },
  // Optional cross-field validation beyond a single column's own reqd/
  // fieldtype rules - (draft, rows, editingIndex) => error string | null.
  // Blocks "Done" and shows the message inline when it returns one.
  validateRow: { type: Function, default: null },
  // Column fieldnames to always keep out of the dialog - e.g. Sales
  // Order's Income Account, meant to be fetched and set automatically
  // (onFieldChange below), never picked by hand.
  hiddenColumns: { type: Array, default: () => [] },
  // Cross-field row logic beyond a plain value assignment - mirrors the old
  // desk child-table row event handlers (Sales Order's Items Table: picking
  // an Item sets Type to "Sales", fetches its UOM and the company's default
  // Income Account). (fieldname, value, draft) => a patch object merged
  // into draft, or a Promise resolving to one for an async lookup.
  onFieldChange: { type: Function, default: null },
  // Per-column field patches (e.g. { document: { accept: '.pdf,.jpg,.png' } })
  // merged onto the backend-provided column meta - for restrictions/config
  // that only apply to this particular table's use of a shared child
  // doctype (e.g. Resume/Proof Of Work's "Document References" table).
  fieldOverrides: { type: Object, default: () => ({}) },
  // { fieldname: 'text' } - shown in the row dialog in place of an empty read-only field.
  emptyReadOnlyTexts: { type: Object, default: () => ({}) },
  // Called with (fieldname, fileMeta, draft) after an Attach/Attach Image
  // upload succeeds - fileMeta is the uploaded File doc (file_name,
  // file_url, ...). Returns a patch object merged into draft, e.g. to
  // auto-fill Document Title from the uploaded filename.
  onFileMeta: { type: Function, default: null },
  // Caps the table at this many rows - hides "Add Row" once reached (e.g.
  // Resume's resume_table only ever holds one row; validate_resume_
  // submission enforces the same limit server-side, this is just the UI
  // half so the button doesn't invite an add that would fail on save).
  maxRows: { type: Number, default: null },
  // Dialog width (frappe-ui Dialog `size`) — 'xl' fits most tables, but a wide one (e.g. the
  // portal's education/experience/address tables) can ask for more room.
  dialogSize: { type: String, default: 'xl' },
})
const emit = defineEmits(['update:rows'])

// The row being edited first, then whatever the parent document offers.
const parentCurrencyDocs = inject('fieldCurrencyDocs', null)
provide('fieldCurrencyDocs', () => [draft.value, ...(parentCurrencyDocs?.() || [])])

const atMaxRows = computed(() => props.maxRows != null && props.rows.length >= props.maxRows)

const resolvedLinkQueries = computed(() =>
  typeof props.linkQueries === 'function'
    ? props.linkQueries(draft.value, props.rows, editingIndex.value)
    : props.linkQueries,
)

// e.g. Lead Past Experience's End Month: depends_on "eval:
// !doc.is_currently_working" in its own doctype JSON, ignored here until now
// - every column rendered unconditionally regardless of what the doctype
// itself declares.
const visibleColumns = computed(() =>
  props.table.columns
    .filter((col) => !props.hiddenColumns.includes(col.fieldname) && dependsOnPasses(col, draft.value))
    .map((col) => (props.fieldOverrides[col.fieldname] ? { ...col, ...props.fieldOverrides[col.fieldname] } : col)),
)

async function onFieldInput(fieldname, value) {
  draft.value[fieldname] = value
  if (props.onFieldChange) {
    const patch = await props.onFieldChange(fieldname, value, draft.value)
    if (patch) Object.assign(draft.value, patch)
  }
  liveCheck(fieldname)
}

// A per-field message (MM-YYYY, grade range, and so on) as soon as that field changes.
// Distinct from rowError (the single message a full validateRow check returns), which still
// runs on Done.
const fieldProblems = ref({})
function liveCheck(fieldname) {
  const problem = rowFieldProblem(props.table.fieldname, fieldname, draft.value[fieldname])
  fieldProblems.value = { ...fieldProblems.value, [fieldname]: problem || '' }
}

async function onFileMeta(fieldname, fileMeta) {
  if (!props.onFileMeta) return
  const patch = await props.onFileMeta(fieldname, fileMeta, draft.value)
  if (patch) Object.assign(draft.value, patch)
}

const previewColumns = computed(() => props.table.columns.slice(0, 4))
const descriptionCharCount = computed(() => String(draft.value.description ?? '').replace(/\s/g, '').length)

function isWide(col) {
  return ['Small Text', 'Long Text', 'Text Editor'].includes(col.fieldtype)
}

function formatCell(col, value) {
  if (value === null || value === undefined || value === '') return '-'
  if (col.fieldtype === 'Check') return value ? 'Yes' : 'No'
  return String(value)
}

const dialogOpen = ref(false)
const editingIndex = ref(null)
const draft = ref({})

const dialogTitle = computed(() =>
  editingIndex.value === null ? `Add ${props.table.label}` : `Edit ${props.table.label}`,
)

// Frappe's two dynamic default tokens - everything else is a literal
// default value, applied as-is.
function resolveDefault(raw) {
  if (raw === 'Now') return siteNowIso()
  if (raw === 'Today') return siteTodayIso()
  return raw
}

function openRow(idx) {
  editingIndex.value = idx
  if (idx === null) {
    // A new row starts blank in the browser - Desk applies each column's
    // own `default` when a row is added; this didn't, so a column like
    // Document References' `date` (default "Now", read_only) showed empty
    // instead of the current time.
    draft.value = Object.fromEntries(
      props.table.columns.filter((c) => c.default != null && c.default !== '').map((c) => [c.fieldname, resolveDefault(c.default)]),
    )
  } else {
    draft.value = { ...props.rows[idx] }
  }
  rowError.value = ''
  fieldProblems.value = {}
  dialogOpen.value = true
}

const rowError = ref('')
const validating = ref(false)

async function commitRow() {
  if (Object.values(fieldProblems.value).some(Boolean)) {
    rowError.value = 'Please fix the highlighted field before continuing.'
    return
  }
  if (props.validateRow) {
    validating.value = true
    try {
      rowError.value = (await props.validateRow(draft.value, props.rows, editingIndex.value)) || ''
    } finally {
      validating.value = false
    }
    if (rowError.value) return
  }

  const rows = [...props.rows]
  if (editingIndex.value === null) {
    rows.push({ ...draft.value })
  } else {
    rows[editingIndex.value] = { ...draft.value }
  }
  emit('update:rows', rows)
  dialogOpen.value = false
}

function removeRow(idx) {
  const rows = [...props.rows]
  rows.splice(idx, 1)
  emit('update:rows', rows)
}
</script>

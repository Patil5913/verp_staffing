<template>
  <div class="flex flex-col gap-5">
    <!-- Steps indicator -->
    <div class="flex items-center justify-center gap-2">
      <template v-for="(s, i) in STEPS" :key="s">
        <span
          class="flex size-6 items-center justify-center rounded-full text-2xs font-semibold"
          :class="i <= step ? 'bg-app-primary text-white' : 'bg-app-panel-2 text-app-text-muted'"
        >{{ i + 1 }}</span>
        <span class="hidden text-p-xs sm:inline" :class="i === step ? 'font-medium text-app-text' : 'text-app-text-muted'">{{ s }}</span>
        <span v-if="i < STEPS.length - 1" class="h-px w-5 bg-app-border sm:w-8" />
      </template>
    </div>

    <div v-if="errorMessage" class="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-p-sm text-red-700 dark:text-red-300">
      {{ errorMessage }}
    </div>

    <!-- Step 1: What do you want to import -->
    <div v-if="step === 0" class="flex flex-col gap-4">
      <div class="rounded-lg border border-app-border bg-app-panel-2 p-3 text-p-xs text-app-text-muted">
        <p class="font-medium text-app-text">How this works</p>
        <ol class="mt-1 list-decimal pl-4">
          <li>Pick what you're bringing in below.</li>
          <li>Download a spreadsheet template with the right column headings already filled in.</li>
          <li>Add your data to it (in Excel, Google Sheets, or any spreadsheet program) without changing the headings, then upload it back here.</li>
          <li>We'll show you a preview before anything is saved, so you can catch mistakes first.</li>
        </ol>
      </div>
      <p class="text-p-sm text-app-text-muted">Choose what kind of records you're bringing in.</p>
      <div v-if="loadingDoctypes" class="flex justify-center py-8"><LoadingIndicator class="h-5 w-5 text-app-text-muted" /></div>
      <template v-else>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <button
            v-for="opt in doctypes.suggested"
            :key="opt.doctype"
            type="button"
            class="flex items-start gap-3 rounded-xl border p-4 text-left transition-colors"
            :class="form.doctype === opt.doctype ? 'border-app-primary bg-app-primary/5' : 'border-app-border bg-app-panel hover:border-app-primary/40'"
            @click="chooseDoctype(opt.doctype)"
          >
            <span class="mt-0.5 size-5 shrink-0 text-app-primary" :class="opt.icon" />
            <span>
              <span class="block text-p-sm font-medium text-app-text">{{ opt.label }}</span>
              <span class="block text-p-xs text-app-text-muted">{{ opt.description }}</span>
            </span>
          </button>
        </div>

        <div class="rounded-lg border border-app-border">
          <button type="button" class="flex w-full items-center justify-between px-4 py-2.5 text-left text-p-sm font-medium text-app-text" @click="showOther = !showOther">
            Something else
            <span class="size-4 text-app-text-muted" :class="showOther ? 'lucide-chevron-up' : 'lucide-chevron-down'" />
          </button>
          <div v-if="showOther" class="border-t border-app-border p-4">
            <AppInput
              type="select"
              label="Doctype"
              placeholder="Search for a record type"
              :options="doctypes.other.map((d) => ({ label: d.label, value: d.doctype }))"
              :model-value="doctypes.other.some((d) => d.doctype === form.doctype) ? form.doctype : ''"
              @update:model-value="chooseDoctype"
            />
          </div>
        </div>
      </template>

      <div class="flex justify-end pt-1">
        <AppButton :disabled="!form.doctype" icon="arrow-right" @click="step = 1">Next</AppButton>
      </div>
    </div>

    <!-- Step 2: Get the template & upload -->
    <div v-else-if="step === 1" class="flex flex-col gap-4">
      <div class="rounded-lg border border-app-border bg-app-panel-2 p-4">
        <p class="text-p-sm font-medium text-app-text">1. Download a spreadsheet template</p>
        <p class="mt-1 text-p-xs text-app-text-muted">
          It already has the right column headings for {{ selectedLabel }}. Fields marked <span class="font-semibold text-app-text">*</span> are required - leaving them blank will stop that row from importing.
        </p>
        <div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <AppInput type="select" label="Include" :options="exportRecordOptions" v-model="templateOptions.exportRecords" />
          <AppInput type="select" label="File format" :options="fileTypeOptions" v-model="templateOptions.fileType" />
        </div>

        <div class="mt-3 rounded-lg border border-app-border bg-app-panel">
          <button type="button" class="flex w-full items-center justify-between px-3 py-2 text-left text-p-xs font-medium text-app-text" @click="showFieldPicker = !showFieldPicker">
            Choose which columns to include ({{ selectedFieldCount }} selected)
            <span class="size-4 text-app-text-muted" :class="showFieldPicker ? 'lucide-chevron-up' : 'lucide-chevron-down'" />
          </button>
          <div v-if="showFieldPicker" class="border-t border-app-border p-3">
            <p class="mb-2 text-p-xs text-app-text-muted">Leave out any column you don't plan to fill in - fewer columns is easier to work with. Required fields can't be left out.</p>
            <div v-if="loadingFields" class="flex justify-center py-4"><LoadingIndicator class="h-4 w-4 text-app-text-muted" /></div>
            <template v-else>
              <div class="mb-2 flex gap-2">
                <button type="button" class="text-p-xs font-medium text-app-primary hover:underline" @click="selectAllFields">Select all</button>
                <span class="text-app-text-muted">·</span>
                <button type="button" class="text-p-xs font-medium text-app-primary hover:underline" @click="selectMandatoryFields">Required fields only</button>
              </div>
              <div class="grid grid-cols-1 gap-x-4 gap-y-1.5 sm:grid-cols-2">
                <label v-for="f in templateFields.fields" :key="f.fieldname" class="flex items-center gap-2 text-p-xs text-app-text">
                  <input type="checkbox" :disabled="f.reqd" :checked="selectedFields.has(f.fieldname)" @change="toggleField(f.fieldname)" />
                  {{ f.label }}<span v-if="f.reqd" class="text-red-600">*</span>
                </label>
              </div>
              <template v-for="table in templateFields.child_tables" :key="table.fieldname">
                <p class="mb-1 mt-3 text-p-xs font-medium text-app-text">{{ table.label }}</p>
                <div class="grid grid-cols-1 gap-x-4 gap-y-1.5 sm:grid-cols-2">
                  <label v-for="f in table.fields" :key="f.fieldname" class="flex items-center gap-2 text-p-xs text-app-text">
                    <input type="checkbox" :disabled="f.reqd" :checked="selectedChildFields[table.fieldname]?.has(f.fieldname)" @change="toggleChildField(table.fieldname, f.fieldname)" />
                    {{ f.label }}<span v-if="f.reqd" class="text-red-600">*</span>
                  </label>
                </div>
              </template>
            </template>
          </div>
        </div>

        <AppButton class="mt-3" variant="outline" icon="download" @click="downloadTemplate">Download Template</AppButton>
      </div>

      <div class="rounded-lg border border-app-border bg-app-panel-2 p-4">
        <p class="text-p-sm font-medium text-app-text">2. Bring your filled-in spreadsheet back</p>
        <div class="mt-2 flex gap-1 rounded-lg bg-app-panel p-1 text-p-xs">
          <button
            type="button"
            class="flex-1 rounded-md px-3 py-1.5 font-medium transition-colors"
            :class="sourceMode === 'file' ? 'bg-app-primary text-white' : 'text-app-text-muted hover:text-app-text'"
            @click="switchSourceMode('file')"
          >Upload a file</button>
          <button
            type="button"
            class="flex-1 rounded-md px-3 py-1.5 font-medium transition-colors"
            :class="sourceMode === 'sheet' ? 'bg-app-primary text-white' : 'text-app-text-muted hover:text-app-text'"
            @click="switchSourceMode('sheet')"
          >Paste a Google Sheets link</button>
        </div>

        <template v-if="sourceMode === 'file'">
          <p class="mt-3 text-p-xs text-app-text-muted">
            CSV or Excel (.xlsx) files are supported. Upload the same file you downloaded above, with your data added below the header row - don't rename, delete or reorder the columns.
          </p>
          <FileUploader
            :upload-args="{ private: 1 }"
            file-types=".csv,.xlsx,.xls"
            @success="onFileUploaded"
            @failure="() => (errorMessage = 'Could not upload that file. Please try again.')"
          >
            <template #default="{ uploading, progress, openFileSelector }">
              <AppButton class="mt-3" :loading="uploading || creatingImport" @click="openFileSelector">
                {{ uploading ? `Uploading ${progress}%` : creatingImport ? 'Reading your file...' : uploadedFile ? 'Replace file' : 'Choose File' }}
              </AppButton>
            </template>
          </FileUploader>
          <p v-if="uploadedFile" class="mt-2 text-p-xs text-app-text-muted">📎 {{ uploadedFile.file_name }}</p>
        </template>

        <template v-else>
          <p class="mt-3 text-p-xs text-app-text-muted">
            The sheet must be shared as "Anyone with the link can view" (or edit), same as Frappe's own Google Sheets import.
          </p>
          <div class="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
            <AppInput
              class="flex-1"
              label="Google Sheets link"
              placeholder="https://docs.google.com/spreadsheets/..."
              v-model="sheetUrl"
              :error="sheetUrlError"
              @update:model-value="sheetUrlError = ''"
            />
            <AppButton :loading="creatingImport" @click="useSheetUrl">Use this link</AppButton>
          </div>
          <p v-if="sheetLinkVerified" class="mt-2 flex items-center gap-1 text-p-xs text-green-700 dark:text-green-400">
            <span class="lucide-check-circle-2 size-3.5" /> Link looks good - taking you to the preview...
          </p>
        </template>
      </div>

      <div class="flex justify-between pt-1">
        <AppButton variant="outline" @click="step = 0">Back</AppButton>
        <AppButton v-if="sourceMode === 'file'" :disabled="!dataImportName" icon="arrow-right" @click="step = 2">Next</AppButton>
      </div>
    </div>

    <!-- Step 3: Preview & confirm -->
    <div v-else-if="step === 2" class="flex flex-col gap-4">
      <p class="text-p-sm text-app-text-muted">Here's what we found in your file. Check that it looks right before importing.</p>

      <div v-if="warnings.length" class="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-p-sm text-red-700 dark:text-red-300">
        <p class="flex items-center gap-1.5 font-medium"><span class="lucide-alert-triangle size-4 shrink-0" /> These need to be fixed before you can import:</p>
        <ul class="mt-1 list-disc pl-5 text-p-xs">
          <li v-for="(w, i) in warnings.slice(0, 8)" :key="i">
            {{ w.row ? `Row ${w.row}: ` : '' }}{{ w.message }}
          </li>
        </ul>
        <p v-if="warnings.length > 8" class="mt-1 text-p-xs">...and {{ warnings.length - 8 }} more.</p>
        <p class="mt-2 text-p-xs">Fix these in your spreadsheet, then upload the corrected file again.</p>
        <AppButton class="mt-2" variant="outline" size="sm" icon="arrow-left" @click="step = 1">Upload a corrected file</AppButton>
      </div>

      <div class="rounded-lg border border-app-border">
        <button type="button" class="flex w-full items-center justify-between px-4 py-2.5 text-left text-p-sm font-medium text-app-text" @click="showColumnMapper = !showColumnMapper">
          <span>
            Column mapping
            <span v-if="unmappedColumnCount" class="ml-1 text-p-xs font-normal text-amber-700 dark:text-amber-400">({{ unmappedColumnCount }} column{{ unmappedColumnCount === 1 ? '' : 's' }} not mapped - won't be imported)</span>
          </span>
          <span class="size-4 text-app-text-muted" :class="showColumnMapper ? 'lucide-chevron-up' : 'lucide-chevron-down'" />
        </button>
        <div v-if="showColumnMapper" class="border-t border-app-border p-3">
          <p class="mb-3 text-p-xs text-app-text-muted">
            We matched each column in your spreadsheet to a field here automatically. If something looks wrong, or a column wasn't matched, pick the right field for it below.
          </p>
          <div class="flex flex-col gap-2">
            <div v-for="col in mappedColumns" :key="col.index" class="grid grid-cols-1 items-center gap-2 sm:grid-cols-[1fr_auto_1fr]">
              <div class="truncate text-p-xs font-medium text-app-text" :title="col.headerTitle">{{ col.headerTitle || 'Untitled column' }}</div>
              <span class="hidden size-3.5 shrink-0 text-app-text-muted sm:inline lucide-arrow-right" />
              <AppInput
                type="select"
                :options="fieldOptions"
                :model-value="pendingColumnMap[col.index] ?? col.currentValue"
                @update:model-value="(v) => (pendingColumnMap[col.index] = v)"
              />
            </div>
          </div>
          <div class="mt-3 flex justify-end">
            <AppButton size="sm" :loading="remapping" :disabled="!hasPendingColumnChanges" @click="applyColumnMapping">Apply Mapping</AppButton>
          </div>
        </div>
      </div>

      <div v-if="previewRows.length" class="overflow-x-auto rounded-lg border border-app-border">
        <table class="min-w-full text-p-xs">
          <thead class="bg-app-panel-2">
            <tr>
              <th v-for="col in previewColumns" :key="col" class="whitespace-nowrap px-3 py-2 text-left font-medium text-app-text">{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in previewRows.slice(0, 5)" :key="i" class="border-t border-app-border">
              <td v-for="(cell, j) in row" :key="j" class="whitespace-nowrap px-3 py-2 text-app-text-muted">{{ cell }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="totalRows" class="text-p-xs text-app-text-muted">{{ totalRows }} record{{ totalRows === 1 ? '' : 's' }} will be imported.</p>

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <label class="flex items-start gap-2 rounded-lg border border-app-border p-3 text-p-sm text-app-text">
          <input type="radio" class="mt-0.5" value="Insert New Records" v-model="form.importType" />
          <span>
            Add as new records
            <span class="block text-p-xs text-app-text-muted">Use this the first time you're bringing this data in.</span>
          </span>
        </label>
        <label class="flex items-start gap-2 rounded-lg border border-app-border p-3 text-p-sm text-app-text">
          <input type="radio" class="mt-0.5" value="Update Existing Records" v-model="form.importType" />
          <span>
            Update existing records
            <span class="block text-p-xs text-app-text-muted">Use this to fix or add details to records already in the system - each row's "ID" column must match an existing record.</span>
          </span>
        </label>
      </div>

      <div class="flex justify-between pt-1">
        <AppButton variant="outline" @click="step = 1">Back</AppButton>
        <AppButton
          icon="upload"
          :loading="starting"
          :disabled="warnings.length > 0"
          :tooltip="warnings.length ? 'Fix the issues above first' : ''"
          @click="startImport"
        >Start Import</AppButton>
      </div>
    </div>

    <!-- Step 4: Running -->
    <div v-else-if="step === 3" class="flex flex-col items-center gap-3 rounded-xl border border-app-border bg-app-panel p-10 text-center">
      <LoadingIndicator class="h-6 w-6 text-app-primary" />
      <p class="text-p-base font-medium text-app-text">Importing your data...</p>
      <p class="text-p-sm text-app-text-muted">This can take a minute for larger files. Please don't close this page.</p>
    </div>

    <!-- Step 5: Result -->
    <div v-else-if="step === 4" class="flex flex-col gap-4">
      <div class="flex items-center gap-3 rounded-lg border p-4" :class="result.failed ? 'border-amber-400/40 bg-amber-400/10' : 'border-green-500/40 bg-green-500/10'">
        <span class="size-6 shrink-0" :class="result.failed ? 'lucide-alert-triangle text-amber-600' : 'lucide-check-circle-2 text-green-600'" />
        <div>
          <p class="text-p-sm font-medium text-app-text">
            {{ result.success }} of {{ result.total }} record{{ result.total === 1 ? '' : 's' }} imported successfully
          </p>
          <p v-if="result.failed" class="text-p-xs text-app-text-muted">{{ result.failed }} row{{ result.failed === 1 ? '' : 's' }} had a problem - see below.</p>
        </div>
      </div>

      <div v-if="result.failures?.length" class="flex flex-col gap-2">
        <p class="text-p-sm font-medium text-app-text">What went wrong</p>
        <div v-for="(f, i) in result.failures.slice(0, 10)" :key="i" class="rounded-lg border border-app-border bg-app-panel-2 p-3 text-p-xs">
          <span class="font-medium text-app-text">Row{{ f.rows?.length > 1 ? 's' : '' }} {{ (f.rows || []).join(', ') || '-' }}:</span>
          <span class="text-app-text-muted"> {{ (f.messages || []).join(' ') || 'Unknown error.' }}</span>
        </div>
      </div>

      <div class="flex justify-end gap-2 pt-1">
        <AppButton variant="outline" @click="reset">Import More Data</AppButton>
        <AppButton v-if="props.onDone" @click="props.onDone">Done</AppButton>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { call, LoadingIndicator, FileUploader } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

// Reusable "import your data" flow: choose what to import, download a
// template, upload the filled-in file, preview it in plain language, run
// the import, show results. Wraps Frappe's own Data Import doctype (see
// verp_staffing/setup/data_import_api.py) so nothing about importing is
// reimplemented here - only the guided, non-technical presentation is.
//
// Used both as its own page (DataImportPage.vue, linked from the profile
// menu) and inline as an optional step in the setup wizard - pass `onDone`
// to get a "Done" button after a successful import.
const props = defineProps({
  onDone: { type: Function, default: null },
})

const STEPS = ['What to import', 'Upload file', 'Preview', 'Importing', 'Done']
const step = ref(0)
const errorMessage = ref('')
const showOther = ref(false)
const loadingDoctypes = ref(true)
const creatingImport = ref(false)
const starting = ref(false)

const doctypes = reactive({ suggested: [], other: [] })
const form = reactive({ doctype: '', importType: 'Insert New Records' })
const sourceMode = ref('file') // 'file' | 'sheet'
const sheetUrl = ref('')
const sheetUrlError = ref('')
const sheetLinkVerified = ref(false)
const uploadedFile = ref(null)
const dataImportName = ref('')
const previewColumns = ref([])
const previewRows = ref([])
const rawColumns = ref([]) // every uploaded column, matched or not - see applyPreview
const warnings = ref([])
const totalRows = ref(0)
const result = reactive({ total: 0, success: 0, failed: 0, failures: [] })

// Column mapper: lets someone override how a spreadsheet column maps to a
// field (see remap_data_import_columns) - both to fix a wrong auto-match and
// to manually map a column Frappe's own header-matching missed entirely
// (e.g. a header that doesn't exactly match a field's label/fieldname), which
// otherwise just silently disappears from the import with no explanation.
const showColumnMapper = ref(false)
const remapping = ref(false)
const pendingColumnMap = reactive({})

const selectedLabel = computed(() => {
  const all = [...doctypes.suggested, ...doctypes.other]
  return all.find((d) => d.doctype === form.doctype)?.label || form.doctype
})

// "Don't Import" first, then every field on the doctype itself, then each
// child table's fields labelled with their table - same value scheme
// Frappe's own Map Columns dialog uses ("fieldname" / "tablefield.fieldname"),
// so remap_data_import_columns can hand it straight to the Importer as-is.
const fieldOptions = computed(() => {
  const options = [{ label: "Don't Import", value: "Don't Import" }]
  for (const f of templateFields.fields) options.push({ label: f.label, value: f.fieldname })
  for (const t of templateFields.child_tables) {
    for (const f of t.fields) options.push({ label: `${f.label} (${t.label})`, value: `${t.fieldname}.${f.fieldname}` })
  }
  return options
})

// Reconstructs the value fieldOptions above would use for a column that's
// already matched (or not) - so the dropdown starts on what's actually
// happening, not blank. col.df.parent is the child DOCTYPE name for a
// child-table match (not the parent's table fieldname), so it's resolved
// against child_doctype from get_template_fields.
function currentMappedValue(col) {
  if (!col.df) return "Don't Import"
  if (col.df.parent === form.doctype) return col.df.fieldname
  const table = templateFields.child_tables.find((t) => t.child_doctype === col.df.parent)
  return table ? `${table.fieldname}.${col.df.fieldname}` : "Don't Import"
}

const mappedColumns = computed(() =>
  rawColumns.value.map((col, index) => ({
    index,
    headerTitle: col.header_title,
    currentValue: currentMappedValue(col),
  }))
)

const unmappedColumnCount = computed(() => mappedColumns.value.filter((c) => c.currentValue === "Don't Import").length)

const hasPendingColumnChanges = computed(() =>
  Object.entries(pendingColumnMap).some(
    ([index, value]) => value !== mappedColumns.value[index]?.currentValue
  )
)

async function applyColumnMapping() {
  const changes = Object.fromEntries(
    Object.entries(pendingColumnMap).filter(([index, value]) => value !== mappedColumns.value[index]?.currentValue)
  )
  if (!Object.keys(changes).length) return
  remapping.value = true
  errorMessage.value = ''
  try {
    const r = await call('verp_staffing.setup.data_import_api.remap_data_import_columns', {
      data_import: dataImportName.value,
      column_map: changes,
    })
    applyPreview(r.preview)
    Object.keys(pendingColumnMap).forEach((k) => delete pendingColumnMap[k])
  } catch (e) {
    errorMessage.value = normalizeError(e).message
  } finally {
    remapping.value = false
  }
}

onMounted(async () => {
  try {
    Object.assign(doctypes, await call('verp_staffing.setup.data_import_api.get_importable_doctypes'))
  } catch (e) {
    errorMessage.value = normalizeError(e).message
  } finally {
    loadingDoctypes.value = false
  }
})

function chooseDoctype(doctype) {
  form.doctype = doctype
  errorMessage.value = ''
}

function switchSourceMode(mode) {
  sourceMode.value = mode
  sheetUrlError.value = ''
  sheetLinkVerified.value = false
  errorMessage.value = ''
}

// Mirrors Frappe's own "Export Data" dialog options (Blank Template / All
// Records / 5 Records) - Excel is the default format since that's what most
// non-technical users open a spreadsheet in.
const exportRecordOptions = [
  { label: 'Blank template (no data)', value: 'blank_template' },
  { label: 'All records', value: 'all' },
  { label: 'First 5 records', value: '5_records' },
]
const fileTypeOptions = [
  { label: 'Excel (.xlsx)', value: 'Excel' },
  { label: 'CSV', value: 'CSV' },
]
const templateOptions = reactive({ exportRecords: 'blank_template', fileType: 'Excel' })

// Field picker: which columns end up in the downloaded template. Starts with
// everything selected (required fields always stay selected, checkbox
// disabled) - "Required fields only" is there for someone who'd rather trim
// it down themselves.
const showFieldPicker = ref(false)
const loadingFields = ref(false)
const templateFields = reactive({ fields: [], child_tables: [] })
const selectedFields = ref(new Set())
const selectedChildFields = reactive({})

const selectedFieldCount = computed(
  () => selectedFields.value.size + Object.values(selectedChildFields).reduce((n, s) => n + s.size, 0)
)

watch(
  () => form.doctype,
  async (doctype) => {
    showFieldPicker.value = false
    templateFields.fields = []
    templateFields.child_tables = []
    selectedFields.value = new Set()
    Object.keys(selectedChildFields).forEach((k) => delete selectedChildFields[k])
    if (!doctype) return
    loadingFields.value = true
    try {
      const r = await call('verp_staffing.setup.data_import_api.get_template_fields', { doctype })
      templateFields.fields = r.fields
      templateFields.child_tables = r.child_tables
      selectedFields.value = new Set(r.fields.map((f) => f.fieldname))
      r.child_tables.forEach((t) => {
        selectedChildFields[t.fieldname] = new Set(t.fields.map((f) => f.fieldname))
      })
    } catch (e) {
      errorMessage.value = normalizeError(e).message
    } finally {
      loadingFields.value = false
    }
  }
)

function toggleField(fieldname) {
  const field = templateFields.fields.find((f) => f.fieldname === fieldname)
  if (field?.reqd) return
  const next = new Set(selectedFields.value)
  next.has(fieldname) ? next.delete(fieldname) : next.add(fieldname)
  selectedFields.value = next
}

function toggleChildField(tableFieldname, fieldname) {
  const table = templateFields.child_tables.find((t) => t.fieldname === tableFieldname)
  const field = table?.fields.find((f) => f.fieldname === fieldname)
  if (field?.reqd) return
  const set = selectedChildFields[tableFieldname] || new Set()
  set.has(fieldname) ? set.delete(fieldname) : set.add(fieldname)
  selectedChildFields[tableFieldname] = new Set(set)
}

function selectAllFields() {
  selectedFields.value = new Set(templateFields.fields.map((f) => f.fieldname))
  templateFields.child_tables.forEach((t) => {
    selectedChildFields[t.fieldname] = new Set(t.fields.map((f) => f.fieldname))
  })
}

function selectMandatoryFields() {
  selectedFields.value = new Set(templateFields.fields.filter((f) => f.reqd).map((f) => f.fieldname))
  templateFields.child_tables.forEach((t) => {
    selectedChildFields[t.fieldname] = new Set(t.fields.filter((f) => f.reqd).map((f) => f.fieldname))
  })
}

function downloadTemplate() {
  const childFields = Object.fromEntries(
    Object.entries(selectedChildFields).map(([k, v]) => [k, [...v]])
  )
  const params = new URLSearchParams({
    doctype: form.doctype,
    export_records: templateOptions.exportRecords,
    file_type: templateOptions.fileType,
    fields: JSON.stringify([...selectedFields.value]),
    child_fields: JSON.stringify(childFields),
  })
  window.open(`/api/method/verp_staffing.setup.data_import_api.download_template?${params}`, '_blank')
}

async function onFileUploaded(file) {
  uploadedFile.value = file
  await createDataImport({ import_file: file.file_url })
}

// Same shape check as Frappe's own validate_google_sheets_url - catches an
// obviously wrong paste (not a link, a different Google product, a share
// dialog's "people" link, ...) before spending a round trip on it.
function isLikelyGoogleSheetsUrl(url) {
  try {
    const u = new URL(url)
    return u.protocol === 'https:' && u.hostname === 'docs.google.com' && u.pathname.includes('/spreadsheets/')
  } catch {
    return false
  }
}

async function useSheetUrl() {
  const url = sheetUrl.value.trim()
  sheetUrlError.value = ''
  sheetLinkVerified.value = false
  if (!url) {
    sheetUrlError.value = 'Paste a Google Sheets link first.'
    return
  }
  if (!isLikelyGoogleSheetsUrl(url)) {
    sheetUrlError.value = "That doesn't look like a Google Sheets link. It should look like https://docs.google.com/spreadsheets/d/...."
    return
  }
  const ok = await createDataImport({ google_sheets_url: url })
  if (ok) {
    // Confirm the link actually worked before whisking them away - a beat
    // of positive feedback, then straight to the preview (no extra click).
    sheetLinkVerified.value = true
    setTimeout(() => {
      if (sheetLinkVerified.value) step.value = 2
    }, 700)
  }
}

async function createDataImport(source) {
  errorMessage.value = ''
  creatingImport.value = true
  try {
    const r = await call('verp_staffing.setup.data_import_api.start_data_import_wizard', {
      doctype: form.doctype,
      ...source,
    })
    dataImportName.value = r.data_import
    applyPreview(r.preview)
    return true
  } catch (e) {
    errorMessage.value = normalizeError(e).message
    if (source.import_file) uploadedFile.value = null
    if (source.google_sheets_url) sheetUrlError.value = normalizeError(e).message
    return false
  } finally {
    creatingImport.value = false
  }
}

function applyPreview(preview) {
  const columns = (preview?.columns || []).filter((c) => !c.skip_import)
  previewColumns.value = columns.map((c) => c.header_title)
  previewRows.value = (preview?.data || []).map((row) => row.filter((_, i) => !preview.columns[i]?.skip_import))
  warnings.value = (preview?.warnings || []).filter((w) => w.type !== 'info')
  totalRows.value = (preview?.data || []).length
  // preview.columns[0] is the synthetic "Sr. No" column (see
  // get_data_for_import_preview) - not a real uploaded column, so it's
  // excluded here same as it's not offered in the mapper.
  rawColumns.value = (preview?.columns || []).slice(1)
}

async function startImport() {
  // Frappe's own Importer silently no-ops (never sets a final status) when
  // non-info warnings exist - the button above is disabled for the same
  // reason, this is just the belt-and-braces guard against calling it anyway.
  if (warnings.value.length > 0) return
  starting.value = true
  errorMessage.value = ''
  step.value = 3
  try {
    await call('verp_staffing.setup.data_import_api.run_data_import_wizard', {
      data_import: dataImportName.value,
      import_type: form.importType,
    })
    await pollStatus()
  } catch (e) {
    step.value = 2
    errorMessage.value = normalizeError(e).message
  } finally {
    starting.value = false
  }
}

async function pollStatus() {
  for (let i = 0; i < 150; i++) {
    const s = await call('verp_staffing.setup.data_import_api.get_data_import_wizard_status', { data_import: dataImportName.value })
    if (['Success', 'Partial Success', 'Error', 'Timed Out'].includes(s.status)) {
      Object.assign(result, s)
      step.value = 4
      return
    }
    await new Promise((r) => setTimeout(r, 2000))
  }
  errorMessage.value = 'Import is taking longer than expected. Refresh to check its progress.'
  step.value = 2
}

function reset() {
  form.doctype = ''
  showFieldPicker.value = false
  sourceMode.value = 'file'
  sheetUrl.value = ''
  sheetUrlError.value = ''
  sheetLinkVerified.value = false
  uploadedFile.value = null
  dataImportName.value = ''
  previewColumns.value = []
  previewRows.value = []
  rawColumns.value = []
  showColumnMapper.value = false
  Object.keys(pendingColumnMap).forEach((k) => delete pendingColumnMap[k])
  warnings.value = []
  totalRows.value = 0
  Object.assign(result, { total: 0, success: 0, failed: 0, failures: [] })
  errorMessage.value = ''
  step.value = 0
}
</script>

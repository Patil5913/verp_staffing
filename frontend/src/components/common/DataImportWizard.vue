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
      <p class="text-p-sm text-app-text-muted">Choose what kind of records you're bringing in. You'll upload a spreadsheet next.</p>
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
        <p class="text-p-sm font-medium text-app-text">1. Download a blank spreadsheet</p>
        <p class="mt-1 text-p-xs text-app-text-muted">It already has the right column headings for {{ selectedLabel }} - fill it in and come back to upload it.</p>
        <AppButton class="mt-3" variant="outline" icon="download" @click="downloadTemplate">Download Template</AppButton>
      </div>

      <div class="rounded-lg border border-app-border bg-app-panel-2 p-4">
        <p class="text-p-sm font-medium text-app-text">2. Upload your filled-in spreadsheet</p>
        <p class="mt-1 text-p-xs text-app-text-muted">CSV or Excel (.xlsx) files are supported.</p>
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
      </div>

      <div class="flex justify-between pt-1">
        <AppButton variant="outline" @click="step = 0">Back</AppButton>
        <AppButton :disabled="!dataImportName" icon="arrow-right" @click="step = 2">Next</AppButton>
      </div>
    </div>

    <!-- Step 3: Preview & confirm -->
    <div v-else-if="step === 2" class="flex flex-col gap-4">
      <p class="text-p-sm text-app-text-muted">Here's what we found in your file. Check that it looks right before importing.</p>

      <div v-if="warnings.length" class="rounded-lg border border-amber-400/40 bg-amber-400/10 p-3 text-p-sm text-amber-800 dark:text-amber-300">
        <p class="font-medium">A few things to double-check:</p>
        <ul class="mt-1 list-disc pl-5 text-p-xs">
          <li v-for="(w, i) in warnings.slice(0, 8)" :key="i">
            {{ w.row ? `Row ${w.row}: ` : '' }}{{ w.message }}
          </li>
        </ul>
        <p v-if="warnings.length > 8" class="mt-1 text-p-xs">...and {{ warnings.length - 8 }} more.</p>
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
            <span class="block text-p-xs text-app-text-muted">Use this to fix or add details to records already in the system.</span>
          </span>
        </label>
      </div>

      <div class="flex justify-between pt-1">
        <AppButton variant="outline" @click="step = 1">Back</AppButton>
        <AppButton icon="upload" :loading="starting" @click="startImport">Start Import</AppButton>
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
import { computed, onMounted, reactive, ref } from 'vue'
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
const uploadedFile = ref(null)
const dataImportName = ref('')
const previewColumns = ref([])
const previewRows = ref([])
const warnings = ref([])
const totalRows = ref(0)
const result = reactive({ total: 0, success: 0, failed: 0, failures: [] })

const selectedLabel = computed(() => {
  const all = [...doctypes.suggested, ...doctypes.other]
  return all.find((d) => d.doctype === form.doctype)?.label || form.doctype
})

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

function downloadTemplate() {
  window.open(
    `/api/method/verp_staffing.setup.data_import_api.download_template?doctype=${encodeURIComponent(form.doctype)}&export_records=blank_template&file_type=CSV`,
    '_blank'
  )
}

async function onFileUploaded(file) {
  uploadedFile.value = file
  errorMessage.value = ''
  creatingImport.value = true
  try {
    const r = await call('verp_staffing.setup.data_import_api.start_data_import_wizard', {
      doctype: form.doctype,
      import_file: file.file_url,
    })
    dataImportName.value = r.data_import
    applyPreview(r.preview)
  } catch (e) {
    errorMessage.value = normalizeError(e).message
    uploadedFile.value = null
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
}

async function startImport() {
  starting.value = true
  errorMessage.value = ''
  step.value = 3
  try {
    await call('verp_staffing.setup.data_import_api.run_data_import_wizard', { data_import: dataImportName.value })
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
  uploadedFile.value = null
  dataImportName.value = ''
  previewColumns.value = []
  previewRows.value = []
  warnings.value = []
  totalRows.value = 0
  Object.assign(result, { total: 0, success: 0, failed: 0, failures: [] })
  errorMessage.value = ''
  step.value = 0
}
</script>

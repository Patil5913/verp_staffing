<template>
  <SectionCard :title="title" :subtitle="subtitle">
    <p v-if="!customer" class="py-4 text-center text-p-sm text-app-text-muted">No customer selected.</p>
    <div v-else-if="displayFields.isLoading || (records.isLoading && !records.resource.data)" class="flex justify-center py-6">
      <LoadingIndicator class="h-5 w-5 text-app-text-muted" />
    </div>
    <p v-else-if="!fields.length" class="py-4 text-center text-p-sm text-app-text-muted">
      No fields are configured to show here for {{ displayKey }}. An administrator can set them in ERP Configuration.
    </p>
    <p v-else-if="!(records.resource.data || []).length" class="py-4 text-center text-p-sm text-app-text-muted">
      No records found.
    </p>

    <div v-else class="flex flex-col gap-4">
      <div
        v-for="record in records.resource.data"
        :key="record.name"
        class="overflow-hidden rounded-lg border border-app-border"
      >
        <dl class="divide-y divide-app-border">
          <div
            v-for="field in record.fields"
            :key="field.fieldname"
            class="grid grid-cols-1 gap-1 px-4 py-2.5 sm:grid-cols-[220px_1fr] sm:gap-4"
          >
            <dt class="text-p-sm font-medium text-app-text-muted">{{ field.label }}</dt>
            <dd class="min-w-0 break-words text-p-sm text-app-text">
              <!-- File fields (Attach, or a Link-to-File like Visa Copy/EAD
              Card/Driving Licence/Old Resume) — writable ones always show
              (even with no file yet) so the upload control is reachable;
              readonly ones with no file just show the empty state.
              reusable.js's file rendering is fieldtype-driven, not just
              Attach — isFile() below matches that. -->
              <div v-if="isFile(field) && isWritable(field)" class="flex flex-wrap items-center gap-2">
                <a v-if="field.value" :href="fileHref(field)" target="_blank" rel="noopener" class="min-w-0 truncate text-app-primary hover:underline">
                  📎 {{ fileLabel(field) }}
                </a>
                <span v-else class="text-app-text-muted">No file attached</span>
                <FileUploader @success="(f) => onUpload(record, field, f)">
                  <template #default="{ uploading, progress, openFileSelector }">
                    <AppButton variant="outline" size="sm" :loading="uploading" @click="openFileSelector">
                      {{ uploading ? `Uploading ${progress}%` : field.value ? 'Replace' : 'Upload' }}
                    </AppButton>
                  </template>
                </FileUploader>
              </div>
              <template v-else-if="!field.value">—</template>
              <a v-else-if="isFile(field)" :href="fileHref(field)" target="_blank" rel="noopener" class="text-app-primary hover:underline">
                📎 {{ fileLabel(field) }}
              </a>

              <!-- email: click to compose, same as reusable.js's
              open-email-composer handler (a mailto: link here — no
              in-app composer in this SPA). -->
              <a v-else-if="field.fieldname === 'email'" :href="`mailto:${field.value}`" class="font-medium text-app-primary hover:underline">
                {{ field.value }}
              </a>

              <!-- LinkedIn-style URL fields: the raw value itself is the
              link text (reusable.js special-cases personal_linkedin/
              marketing_linkedin the same way — generalized here to any
              *linkedin* fieldname). -->
              <a
                v-else-if="field.fieldname.toLowerCase().includes('linkedin')"
                :href="field.value.startsWith('http') ? field.value : `https://${field.value}`"
                target="_blank"
                rel="noopener"
                class="font-medium text-app-primary hover:underline"
              >
                {{ field.value }}
              </a>

              <!-- Any other Link field: value is another doctype's record
              name — link to it. -->
              <router-link
                v-else-if="field.fieldtype === 'Link' && field.options"
                :to="`/${encodeURIComponent(field.options)}/${encodeURIComponent(field.value)}`"
                class="font-medium text-app-primary hover:underline"
              >
                {{ field.value }}
              </router-link>

              <template v-else-if="isLong(display(field))">
                {{ truncate(display(field)) }}&hellip;
                <button type="button" class="font-medium text-app-primary hover:underline" @click="openViewMore(field.label, display(field))">
                  View more
                </button>
              </template>
              <template v-else>{{ display(field) || '—' }}</template>
            </dd>
          </div>
        </dl>

        <div v-for="table in record.tables" :key="table.fieldname" class="border-t border-app-border">
          <p class="bg-app-panel-2 px-4 py-2 text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">
            {{ table.label }}
          </p>
          <div v-if="table.rows.length" class="overflow-x-auto">
            <table class="w-full text-left text-p-sm">
              <thead class="text-p-xs text-app-text-muted">
                <tr>
                  <th v-for="col in table.columns" :key="col.fieldname" class="whitespace-nowrap px-4 py-1.5 font-medium">
                    {{ col.label }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in table.rows" :key="i" class="border-t border-app-border">
                  <td v-for="col in table.columns" :key="col.fieldname" class="px-4 py-1.5 text-app-text">
                    <template v-if="isLong(row[col.fieldname])">
                      {{ truncate(row[col.fieldname]) }}&hellip;
                      <button type="button" class="font-medium text-app-primary hover:underline" @click="openViewMore(col.label, row[col.fieldname])">
                        View more
                      </button>
                    </template>
                    <template v-else>{{ row[col.fieldname] ?? '—' }}</template>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="px-4 py-3 text-p-sm text-app-text-muted">No rows.</p>
        </div>
      </div>
    </div>
  </SectionCard>

  <!-- Ported from customer_history.js's render_truncated_text (80-char
  inline clamp) — here as a dialog instead of the desk's inline expand,
  since this panel's fields/tables are dense enough that an inline
  expansion would push everything else around. -->
  <Dialog v-model="viewMoreOpen" :options="{ title: viewMoreLabel, size: 'lg' }">
    <template #body-content>
      <p class="whitespace-pre-wrap text-p-sm text-app-text">{{ viewMoreText }}</p>
    </template>
  </Dialog>
</template>

<script setup>
// The customer's Lead Detail Form data, limited to the fields ERP
// Configuration allows this department to see — the desk form's
// "customer details / lead details" HTML block. `displayKey` is the
// department (doctype) name that config is keyed by.
import { computed, reactive, ref, watch } from 'vue'
import { LoadingIndicator, FileUploader, Dialog, call } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import { useCustomerContext } from '@/composables/detail/useCustomerContext'
import { formatFieldValue } from '@/utils/list/formatValue'
import { notify } from '@/utils/common/notify'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  customer: { type: String, default: '' },
  detail: { type: Object, default: null },
  displayKey: { type: String, default: '' },
  // ...or the field on the record whose value is the key (Other Services
  // are keyed by their `service` item, not by doctype).
  displayKeyField: { type: String, default: '' },
  // Overrides the ERP Configuration allowlist with a fixed fieldname list
  // (CR / Onboardings show a hardcoded set).
  fixedFields: { type: Array, default: null },
  title: { type: String, default: 'Customer Details' },
  subtitle: { type: String, default: '' },
})

const customer = computed(() => props.customer || props.detail?.values.customer || '')
const displayKey = computed(() => props.displayKey || props.detail?.values[props.displayKeyField] || '')
const { fields: configured, writableFields, displayFields, records } = useCustomerContext(customer, displayKey, computed(() => props.fixedFields))
const fields = computed(() => (props.fixedFields ? [...new Set([...props.fixedFields, ...writableFields.value])] : [...new Set([...configured.value, ...writableFields.value])]))

// reusable.js's file rendering keys off fieldtype, not just Attach — Visa
// Copy/EAD Card/Driving Licence/Old Resume are Link-to-File fields (a
// desk convention for "an upload, referenced by the File doc's name
// rather than a plain Attach field's raw URL" — see FieldControl.vue's
// own isLinkToFile), which this panel previously never recognized as a
// file field at all.
const FILE_TYPES = ['Attach', 'Attach Image']
const isLinkToFile = (f) => f.fieldtype === 'Link' && f.options === 'File'
const isFile = (f) => FILE_TYPES.includes(f.fieldtype) || isLinkToFile(f)
const isWritable = (f) => writableFields.value.includes(f.fieldname)
const fileName = (url) => decodeURIComponent(String(url).split('/').pop())
const display = (f) => (f.fieldtype === 'Text Editor' ? String(f.value ?? '').replace(/<[^>]+>/g, ' ') : formatFieldValue(f.value, f))

// Link-to-File stores the File doc's *name*, not a URL — resolve each one's
// actual file_url/file_name once and cache by that name, same as
// FieldControl.vue's linkedFile resource does for a single field.
const resolvedFiles = reactive({})
async function resolveFile(fileDocName) {
  if (!fileDocName || resolvedFiles[fileDocName]) return
  resolvedFiles[fileDocName] = { url: '', name: '', loading: true }
  try {
    const file = await call('frappe.client.get', { doctype: 'File', name: fileDocName })
    resolvedFiles[fileDocName] = { url: file?.file_url || '', name: file?.file_name || '', loading: false }
  } catch {
    resolvedFiles[fileDocName] = { url: '', name: '', loading: false }
  }
}
watch(
  () => records.resource.data,
  (data) => {
    for (const record of data || []) {
      for (const field of record.fields || []) {
        if (isLinkToFile(field) && field.value) resolveFile(field.value)
      }
    }
  },
  { immediate: true },
)
function fileHref(field) {
  if (!isLinkToFile(field)) return field.value
  return resolvedFiles[field.value]?.url || ''
}
function fileLabel(field) {
  if (!isLinkToFile(field)) return fileName(field.value)
  return resolvedFiles[field.value]?.name || field.value
}

// customer_history.js's render_truncated_text: 80 characters, same as the
// desk widget this panel otherwise mirrors.
const TRUNCATE_LIMIT = 80
const isLong = (text) => String(text ?? '').length > TRUNCATE_LIMIT
const truncate = (text) => String(text ?? '').slice(0, TRUNCATE_LIMIT)

const viewMoreOpen = ref(false)
const viewMoreLabel = ref('')
const viewMoreText = ref('')
function openViewMore(label, text) {
  viewMoreLabel.value = label
  viewMoreText.value = String(text ?? '')
  viewMoreOpen.value = true
}

// Saves straight through save_reference_detail_view (same endpoint the
// Candidate Profile tab uses) — a self-contained write, independent of
// the host page's own Save button, since this panel otherwise stays a
// read-only display widget.
async function onUpload(record, field, fileMeta) {
  // Link-to-File stores the File doc's name (matches FieldControl.vue's
  // isLinkToFile write path); a plain Attach field stores the raw URL.
  const value = isLinkToFile(field) ? fileMeta.name : fileMeta.file_url
  try {
    await call('verp_staffing.utils.detail_view.save_reference_detail_view', {
      reference_doctype: 'Customer',
      reference_name: customer.value,
      values: { [field.fieldname]: value },
      access_key: displayKey.value,
    })
    field.value = value
    if (isLinkToFile(field)) resolvedFiles[value] = { url: fileMeta.file_url, name: fileMeta.file_name || '', loading: false }
    notify.success('File uploaded.')
  } catch (e) {
    notify.error(e?.messages?.[0] || 'Failed to save the file.')
  }
}
</script>

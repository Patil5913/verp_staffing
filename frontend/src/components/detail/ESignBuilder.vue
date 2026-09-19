<template>
  <div v-if="!pdfUrl" class="rounded-xl border border-dashed border-app-border p-8 text-center text-p-sm text-app-text-muted">
    Upload the original PDF (Details tab) and save — then place signature fields here.
  </div>

  <div v-else class="flex h-[calc(100vh-190px)] min-h-[540px] overflow-hidden rounded-xl border border-app-border bg-app-panel shadow-sm">
    <!-- Recipients + tools -->
    <aside class="flex w-60 shrink-0 flex-col gap-5 overflow-y-auto border-r border-app-border p-4">
      <div>
        <p class="mb-2 text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">Recipients</p>
        <div class="flex flex-col gap-1.5">
          <button
            v-for="email in recipients"
            :key="email"
            type="button"
            class="flex items-center gap-2 rounded-lg border px-2.5 py-2 text-left text-p-sm transition-colors"
            :class="email === activeRecipient ? 'border-app-primary bg-app-primary-tint' : 'border-app-border hover:border-app-primary/40'"
            @click="activeRecipient = email"
          >
            <span class="size-2.5 shrink-0 rounded-full" :style="{ background: colorFor(email) }" />
            <span class="min-w-0 flex-1 truncate text-app-text">{{ email }}</span>
            <span class="text-p-xs text-app-text-muted">{{ countFor(email) }}</span>
          </button>
          <p v-if="!recipients.length" class="text-p-xs text-app-text-muted">Add a recipient to start placing fields.</p>
        </div>
        <div v-if="!disabled" class="mt-2 flex gap-1.5">
          <input
            v-model="newEmail"
            type="email"
            placeholder="signer@email.com"
            class="h-8 min-w-0 flex-1 rounded-lg border border-app-border bg-app-panel px-2.5 text-p-sm text-app-text focus:border-app-primary focus:outline-none"
            @keyup.enter="addRecipient"
          />
          <AppButton size="sm" variant="outline" icon="plus" @click="addRecipient" />
        </div>
      </div>

      <div>
        <p class="mb-2 text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">Fields</p>
        <div class="flex flex-col gap-1.5">
          <div
            v-for="tool in TOOLS"
            :key="tool.type"
            class="flex cursor-grab select-none items-center gap-2 rounded-lg border border-app-border bg-app-panel px-3 py-2 text-p-sm font-medium text-app-text transition-colors hover:border-app-primary hover:bg-app-primary-tint"
            :class="!activeRecipient || disabled ? 'pointer-events-none opacity-50' : ''"
            :draggable="!disabled && !!activeRecipient"
            @dragstart="dragging = tool.type"
            @dragend="dragging = null"
          >
            <span :class="`lucide-${tool.icon} size-4 text-app-text-muted`" />{{ tool.label }}
          </div>
        </div>
        <p class="mt-2 text-p-xs text-app-text-muted">Drag a field onto the page for the selected recipient.</p>
      </div>
    </aside>

    <!-- Pages -->
    <div class="flex-1 overflow-auto bg-app-panel-2 p-6">
      <div v-if="loading" class="flex justify-center py-16"><LoadingIndicator class="h-6 w-6 text-app-text-muted" /></div>
      <StateBanner v-else-if="error" icon="alert-triangle" title="Couldn't load this PDF" :description="error" />

      <div
        v-for="page in pages"
        :key="page.number"
        class="relative mx-auto mb-5 bg-white shadow"
        :style="{ width: page.width + 'px', height: page.height + 'px' }"
        @click="selectedKey = null"
      >
        <img :src="page.dataUrl" class="block size-full" />
        <div class="absolute inset-0" @dragover.prevent @drop="onDrop(page, $event)">
          <template v-for="row in rowsOnPage(page.number)" :key="keyOf(row)">
            <img
              v-if="row.signed && row.signature_image"
              :src="row.signature_image"
              class="absolute object-contain"
              :style="boxStyle(row)"
            />
            <div
              v-else
              class="absolute flex cursor-move items-center overflow-hidden rounded border-2 text-p-xs font-semibold"
              :class="keyOf(row) === selectedKey ? 'ring-2 ring-offset-1' : ''"
              :style="{ ...boxStyle(row), borderColor: colorFor(row.signer_email), background: colorFor(row.signer_email) + '22', color: colorFor(row.signer_email), '--tw-ring-color': colorFor(row.signer_email) }"
              @mousedown="startMove(row, page, $event)"
              @click.stop="selectedKey = keyOf(row)"
            >
              <span v-if="row.field_type === 'checkbox'" class="lucide-check-square mx-auto size-4" />
              <span v-else class="truncate px-1.5">{{ row.field_label || row.placeholder_text || labelFor(row.field_type) }}</span>
              <button
                v-if="!disabled"
                type="button"
                class="absolute right-0 top-0 flex size-4 items-center justify-center rounded-bl bg-red-500 text-[10px] text-white"
                @mousedown.stop
                @click.stop="removeRow(row)"
              >
                ✕
              </button>
              <span
                v-if="!disabled && row.field_type !== 'checkbox'"
                class="absolute bottom-0 right-0 size-2.5 cursor-se-resize"
                :style="{ background: colorFor(row.signer_email) }"
                @mousedown.stop="startResize(row, page, $event)"
              />
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- Properties -->
    <aside v-if="selected" class="flex w-72 shrink-0 flex-col gap-3 overflow-y-auto border-l border-app-border p-4">
      <div class="flex items-center justify-between">
        <h4 class="text-p-base font-medium capitalize text-app-text">{{ selected.field_type }} field</h4>
        <AppButton variant="ghost" size="icon" icon="x" @click="selectedKey = null" />
      </div>
      <div class="flex flex-col gap-1.5">
        <label class="text-p-sm font-medium text-app-text-muted">Recipient</label>
        <AppCombobox :model-value="selected.signer_email" :options="recipients" :disabled="disabled" placeholder="Select a recipient" @update:model-value="(v) => patch(selected, { signer_email: v })" />
      </div>
      <template v-if="selected.field_type !== 'checkbox'">
        <FormControl label="Field label" :model-value="selected.field_label" :disabled="disabled" required @update:model-value="(v) => patch(selected, { field_label: v })" />
        <FormControl label="Placeholder text" :model-value="selected.placeholder_text" :disabled="disabled" @update:model-value="(v) => patch(selected, { placeholder_text: v })" />
        <FormControl
          v-if="selected.field_type !== 'signature'"
          type="number"
          label="Font size"
          :model-value="selected.font_size || 12"
          :disabled="disabled"
          @update:model-value="(v) => patch(selected, { font_size: String(Number(v) || 12) })"
        />
      </template>
    </aside>
  </div>
</template>

<script setup>
// The E Sign document editor, ported from e_sign.js: the original PDF is
// rendered page by page and each recipient's fields (signature / text / date
// / number / checkbox) are dragged onto it, moved and resized in
// page-relative percentages — the same x/y/width/height_percent the server
// uses to draw the final PDF. Rows live in the hidden `signature_fields`
// table: read from the detail's hiddenTables until edited, then written into
// `values` so the page's normal Save persists them.
import { computed, ref } from 'vue'
import { LoadingIndicator, FormControl } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import AppCombobox from '@/components/common/AppCombobox.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { usePdfPages } from '@/composables/detail/usePdfPages'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  locked: { type: Boolean, default: false },
})

const TOOLS = [
  { type: 'signature', label: 'Signature', icon: 'pen-tool' },
  { type: 'text', label: 'Text', icon: 'type' },
  { type: 'date', label: 'Date', icon: 'calendar' },
  { type: 'number', label: 'Number', icon: 'hash' },
  { type: 'checkbox', label: 'Checkbox', icon: 'check-square' },
]
const PALETTE = ['#2563eb', '#dc2626', '#16a34a', '#d97706', '#7c3aed', '#0891b2', '#db2777', '#4b5563']
const SIZES = { checkbox: [3.5, 2.6], signature: [24, 6], default: [22, 4] }

const pdfUrl = computed(() => props.detail.values.original_pdf || '')
const { pages, loading, error } = usePdfPages(pdfUrl)
const disabled = computed(() => props.locked || !props.detail.canWrite.value)

const rows = computed(() => props.detail.values.signature_fields ?? props.detail.hiddenTables.signature_fields ?? [])
const setRows = (next) => (props.detail.values.signature_fields = next)

let seq = 0
const keyOf = (row) => row.name || row.__key || (row.__key = `new-${++seq}`)
const rowsOnPage = (n) => rows.value.filter((r) => Number(r.page_number) === n)
const patch = (row, changes) => setRows(rows.value.map((r) => (keyOf(r) === keyOf(row) ? { ...r, ...changes, __key: keyOf(row) } : r)))
const removeRow = (row) => setRows(rows.value.filter((r) => keyOf(r) !== keyOf(row)))

// Recipients are whoever has a field, plus anyone added here who doesn't yet.
const extra = ref([])
const recipients = computed(() => [...new Set([...rows.value.map((r) => r.signer_email).filter(Boolean), ...extra.value])])
const activeRecipient = ref('')
const newEmail = ref('')
const colorFor = (email) => PALETTE[Math.max(0, recipients.value.indexOf(email)) % PALETTE.length]
const countFor = (email) => rows.value.filter((r) => r.signer_email === email).length
const labelFor = (type) => TOOLS.find((t) => t.type === type)?.label || type

function addRecipient() {
  const email = newEmail.value.trim().toLowerCase()
  if (!/^\S+@\S+\.\S+$/.test(email)) return
  if (!recipients.value.includes(email)) extra.value.push(email)
  activeRecipient.value = email
  newEmail.value = ''
}
if (!activeRecipient.value && recipients.value.length) activeRecipient.value = recipients.value[0]

const selectedKey = ref(null)
const selected = computed(() => rows.value.find((r) => keyOf(r) === selectedKey.value) || null)

const boxStyle = (row) => ({
  left: `${row.x_percent}%`,
  top: `${row.y_percent}%`,
  width: `${row.width_percent}%`,
  height: `${row.height_percent}%`,
  fontSize: `${(Number(row.font_size) || 12) * 1.2}px`,
})

const dragging = ref(null)
function onDrop(page, event) {
  if (disabled.value || !dragging.value || !activeRecipient.value) return
  const rect = event.currentTarget.getBoundingClientRect()
  const [w, h] = SIZES[dragging.value] || SIZES.default
  const row = {
    page_number: page.number,
    x_percent: Math.min(100 - w, Math.max(0, ((event.clientX - rect.left) / rect.width) * 100)),
    y_percent: Math.min(100 - h, Math.max(0, ((event.clientY - rect.top) / rect.height) * 100)),
    width_percent: w,
    height_percent: h,
    signer_email: activeRecipient.value,
    field_type: dragging.value,
    field_label: '',
    placeholder_text: '',
    font_size: '12',
  }
  setRows([...rows.value, row])
  selectedKey.value = keyOf(row)
}

// Move / resize: pointer deltas in page pixels -> percent of the page.
let session = null
function track(row, page, event, mode) {
  if (disabled.value || event.button !== 0) return
  session = { key: keyOf(row), page, mode, startX: event.pageX, startY: event.pageY, orig: { ...row } }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
  event.preventDefault()
}
const startMove = (row, page, e) => track(row, page, e, 'move')
const startResize = (row, page, e) => track(row, page, e, 'resize')
function onMove(event) {
  if (!session) return
  const { key, page, mode, startX, startY, orig } = session
  const dx = ((event.pageX - startX) / page.width) * 100
  const dy = ((event.pageY - startY) / page.height) * 100
  const changes =
    mode === 'move'
      ? {
          x_percent: Math.max(0, Math.min(100 - orig.width_percent, orig.x_percent + dx)),
          y_percent: Math.max(0, Math.min(100 - orig.height_percent, orig.y_percent + dy)),
        }
      : {
          width_percent: Math.max(4, Math.min(100 - orig.x_percent, orig.width_percent + dx)),
          height_percent: Math.max(2, Math.min(100 - orig.y_percent, orig.height_percent + dy)),
        }
  setRows(rows.value.map((r) => (keyOf(r) === key ? { ...r, ...changes, __key: key } : r)))
}
function onUp() {
  session = null
  window.removeEventListener('mousemove', onMove)
  window.removeEventListener('mouseup', onUp)
}
</script>

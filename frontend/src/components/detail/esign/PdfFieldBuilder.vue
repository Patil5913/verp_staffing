<template>
  <div v-if="!pdfUrl" class="rounded-lg border border-dashed border-app-border p-6 text-center text-p-sm text-app-text-muted">
    Upload a PDF template above to start building.
  </div>

  <div v-else class="relative flex h-[calc(100dvh-220px)] flex-col md:flex-row min-h-[520px] overflow-hidden rounded-lg md:h-[calc(100dvh-320px)] border border-app-border">
    <!-- Toolbox -->
    <div class="flex max-h-44 w-full shrink-0 flex-col gap-4 overflow-y-auto border-b border-app-border bg-app-panel p-4 md:max-h-none md:w-56 md:border-b-0 md:border-r">
      <p class="text-p-xs text-app-text-muted md:hidden">Dragging fields onto the page needs a mouse; use a tablet or desktop to place them.</p>
      <div>
        <div class="mb-2 text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">Standard Fields</div>
        <div class="flex flex-col gap-1.5">
          <div
            v-for="tool in STANDARD_TOOLS"
            :key="tool.type"
            class="builder-tool"
            :draggable="!disabled"
            @dragstart="draggingTool = tool.type"
            @dragend="draggingTool = null"
          >
            {{ tool.icon }} {{ tool.label }}
          </div>
        </div>
      </div>

      <div>
        <div class="mb-2 text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">Customer Fields</div>
        <div
          class="builder-tool"
          :draggable="!disabled"
          @dragstart="draggingTool = 'Signature'"
          @dragend="draggingTool = null"
        >
          ✍ Signature
        </div>
      </div>

      <div class="mt-auto flex flex-col gap-2 border-t border-app-border pt-4">
        <AppButton :disabled="disabled" @click="emit('save')">Save Template</AppButton>
        <AppButton variant="outline" :disabled="disabled || !localFields.length" @click="clearAll">Clear</AppButton>
      </div>
    </div>

    <!-- PDF pages -->
    <div class="flex-1 overflow-auto bg-app-panel-2 p-6">
      <div v-if="loadingPdf" class="flex justify-center py-16">
        <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
      </div>
      <StateBanner v-else-if="pdfError" icon="alert-triangle" title="Couldn't load this PDF" :description="pdfError" />

      <div
        v-for="page in pages"
        :key="page.number"
        class="pdf-page-container"
        :style="{ width: page.width + 'px', height: page.height + 'px' }"
        @click="selectedFieldId = null"
      >
        <img :src="page.dataUrl" class="pdf-page-img" />
        <div class="fields-layer" @dragover.prevent @drop="onDrop(page.number, $event)">
          <div
            v-for="field in fieldsOnPage(page.number)"
            :key="field.field_id"
            class="pdf-field"
            :class="{ selected: field.field_id === selectedFieldId }"
            :style="fieldStyle(field)"
            @pointerdown="onFieldMouseDown(field, $event)"
            @click.stop="selectedFieldId = field.field_id"
          >
            <div class="pdf-field-preview" :style="previewStyle(field)">
              {{ field.builder_placeholder || PREVIEW_VALUES[field.type] || field.name }}
            </div>
            <button v-if="!disabled" type="button" class="field-close" @click.stop="removeField(field.field_id)">
              ✕
            </button>
            <div v-if="!disabled" class="resize-handle" @pointerdown.stop="onResizeMouseDown(field, $event)" />
          </div>
        </div>
      </div>
    </div>

    <!-- Properties -->
    <div v-if="selectedField" class="absolute inset-x-0 bottom-0 z-20 flex max-h-[60%] flex-col gap-3 overflow-y-auto border-t border-app-border bg-app-panel p-4 shadow-2xl md:static md:max-h-none md:w-80 md:shrink-0 md:border-l md:border-t-0 md:shadow-none">
      <div class="flex items-center justify-between">
        <h4 class="text-p-base font-medium text-app-text">Properties</h4>
        <AppButton variant="ghost" size="icon" icon="x" @click="selectedFieldId = null" />
      </div>

      <FieldControl
        :field="NAME_FIELD"
        :disabled="disabled"
        :model-value="selectedField.name"
        @update:model-value="(v) => updateSelectedField('name', v)"
      />

      <template v-if="selectedField.type !== 'Signature'">
        <FieldControl
          :field="PLACEHOLDER_FIELD"
          :disabled="disabled"
          :model-value="selectedField.builder_placeholder"
          @update:model-value="(v) => updateSelectedField('builder_placeholder', v)"
        />
        <FieldControl
          :field="FONT_SIZE_FIELD"
          :disabled="disabled"
          :model-value="selectedField.font_size"
          @update:model-value="(v) => updateSelectedField('font_size', Number(v) || 12)"
        />
        <FieldControl
          :field="LINE_HEIGHT_FIELD"
          :disabled="disabled"
          :model-value="selectedField.line_height"
          @update:model-value="(v) => updateSelectedField('line_height', Number(v) || 1.2)"
        />
        <p v-if="lineHeightWarning" class="text-p-xs text-red-600">{{ lineHeightWarning }}</p>
      </template>

      <div class="rounded-lg border border-app-border bg-app-panel-2 p-3 text-p-xs leading-relaxed text-app-text-muted">
        💡 <strong>Quick tips</strong><br />
        • Reuse the same Name on multiple fields to auto-fill the same value in all of them.<br />
        • Preview Text is only shown here in the builder, not in the final document.<br />
        • Drag a field to move it, or its corner handle to resize it.
      </div>
    </div>
  </div>

  <Dialog v-model="showCreateDialog" :options="{ title: `Create ${newFieldType} Field` }">
    <template #body-content>
      <div class="flex flex-col gap-3">
        <FieldControl :field="NAME_FIELD" v-model="draft.name" show-errors />
        <template v-if="newFieldType !== 'Signature'">
          <FieldControl :field="PLACEHOLDER_FIELD" v-model="draft.placeholder" />
          <FieldControl :field="FONT_SIZE_FIELD" v-model.number="draft.font_size" />
          <FieldControl :field="LINE_HEIGHT_FIELD" v-model.number="draft.line_height" />
        </template>
      </div>
    </template>
    <template #actions>
      <AppButton @click="confirmCreateField">Create Field</AppButton>
    </template>
  </Dialog>
</template>

<script setup>
// Ports the old desk pdf_agreement_template.js drag-and-drop field builder
// onto this app's own components (AppButton/Dialog/FieldControl/
// StateBanner) instead of hand-built jQuery/HTML — same pdf.js rendering,
// same field shape (field_id/name/type/page/x/y/width/height/font_size/
// line_height/builder_placeholder), same drag-to-place + drag-to-move +
// corner-handle resize interactions, just as native Vue state/events
// instead of jQuery. The "Show Form Tour" walkthrough was left out — it
// was UX sugar on top of the same builder, not core behavior.
import { computed, ref, watch } from 'vue'
import { Dialog, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import FieldControl from '@/components/detail/FieldControl.vue'
import { usePdfPages } from '@/composables/detail/usePdfPages'
import { notify } from '@/utils/common/notify'

const props = defineProps({
  pdfUrl: { type: String, default: '' },
  modelValue: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'save'])

const PREVIEW_FONT_SCALE = 1.5
const PREVIEW_VALUES = {
  Text: 'Acme Corporation Private Limited',
  Number: '₹ 12,45,000',
  Rich_Text: 'Net 30 days from invoice date',
  Date: '31 March 2026',
  Signature: 'Johnathan Smith',
}
const STANDARD_TOOLS = [
  { type: 'Text', icon: '📝', label: 'Text' },
  { type: 'Number', icon: '🔢', label: 'Number' },
  { type: 'Date', icon: '📅', label: 'Date' },
  { type: 'Rich_Text', icon: '📄', label: 'Text Editor' },
]

const NAME_FIELD = { fieldname: 'name', label: 'Field Name', fieldtype: 'Data', reqd: 1 }
const PLACEHOLDER_FIELD = { fieldname: 'placeholder', label: 'Preview Text', fieldtype: 'Data' }
const FONT_SIZE_FIELD = { fieldname: 'font_size', label: 'Font Size', fieldtype: 'Int' }
const LINE_HEIGHT_FIELD = { fieldname: 'line_height', label: 'Line Height', fieldtype: 'Float' }

// ── Local working copy of the fields array ─────────────────────────────────
const localFields = ref([])
watch(
  () => props.modelValue,
  (val) => {
    localFields.value = (val || []).map((f) => ({ ...f }))
  },
  { immediate: true },
)
function emitUpdate() {
  emit(
    'update:modelValue',
    localFields.value.map((f) => ({ ...f })),
  )
}

function fieldsOnPage(pageNumber) {
  return localFields.value.filter((f) => f.page === pageNumber)
}

const selectedFieldId = ref(null)
const selectedField = computed(() => localFields.value.find((f) => f.field_id === selectedFieldId.value) || null)

const lineHeightWarning = computed(() => {
  const f = selectedField.value
  if (!f) return ''
  const estimated = Math.round((f.font_size || 0) * (f.line_height || 0))
  const box = Math.round(f.height || 0)
  if (estimated <= box) return ''
  return `This line height may cause wrapped text to overflow the box (~${estimated}px needed vs ${box}px available). Consider lowering it or resizing the field.`
})

function updateSelectedField(key, value) {
  if (!selectedField.value) return
  selectedField.value[key] = value
  emitUpdate()
}

function fieldStyle(field) {
  return {
    top: `${field.y}px`,
    left: `${field.x}px`,
    width: `${field.width || 150}px`,
    height: `${field.height || 30}px`,
  }
}
function previewStyle(field) {
  return {
    fontSize: `${(field.font_size || 12) * PREVIEW_FONT_SCALE}px`,
    lineHeight: field.line_height || 1.2,
  }
}

function removeField(id) {
  localFields.value = localFields.value.filter((f) => f.field_id !== id)
  if (selectedFieldId.value === id) selectedFieldId.value = null
  emitUpdate()
}
function clearAll() {
  localFields.value = []
  selectedFieldId.value = null
  emitUpdate()
}

// ── Drag a tool from the toolbox onto a page to create a field ─────────────
const draggingTool = ref(null)
const showCreateDialog = ref(false)
const newFieldType = ref('')
const newFieldDropPos = ref(null)
const draft = ref({ name: '', placeholder: '', font_size: 12, line_height: 1.2 })

function onDrop(pageNumber, event) {
  if (props.disabled || !draggingTool.value) return
  const rect = event.currentTarget.getBoundingClientRect()
  newFieldType.value = draggingTool.value
  newFieldDropPos.value = { page: pageNumber, x: event.clientX - rect.left, y: event.clientY - rect.top }
  draft.value = { name: '', placeholder: '', font_size: 12, line_height: 1.2 }
  showCreateDialog.value = true
}

function confirmCreateField() {
  if (!draft.value.name?.trim()) {
    notify.error('Field Name is required.')
    return
  }
  const page = pages.value.find((p) => p.number === newFieldDropPos.value.page)
  const field = {
    field_id: `fld_${Math.random().toString(36).slice(2, 10)}`,
    name: draft.value.name.trim(),
    type: newFieldType.value,
    page: newFieldDropPos.value.page,
    x: Math.round(newFieldDropPos.value.x),
    y: Math.round(newFieldDropPos.value.y),
    width: 150,
    height: 30,
    font_size: draft.value.font_size || 12,
    line_height: draft.value.line_height || 1.2,
    font_family: 'helv',
    wrap: true,
    overflow: 'warn',
    builder_placeholder: draft.value.placeholder || '',
    page_width: page?.width || 0,
    page_height: page?.height || 0,
  }
  localFields.value.push(field)
  emitUpdate()
  showCreateDialog.value = false
  selectedFieldId.value = field.field_id
}

// ── Move an existing field by dragging its body ─────────────────────────────
let dragSession = null
function onFieldMouseDown(field, event) {
  if (props.disabled || event.button !== 0) return
  dragSession = { field, startX: event.pageX, startY: event.pageY, origX: field.x, origY: field.y }
  window.addEventListener('pointermove', onFieldMouseMove)
  window.addEventListener('pointerup', onFieldMouseUp)
  event.preventDefault()
}
function onFieldMouseMove(event) {
  if (!dragSession) return
  const { field, startX, startY, origX, origY } = dragSession
  const page = pages.value.find((p) => p.number === field.page)
  const maxLeft = (page?.width || 0) - (field.width || 150)
  const maxTop = (page?.height || 0) - (field.height || 30)
  field.x = Math.max(0, Math.min(origX + (event.pageX - startX), maxLeft))
  field.y = Math.max(0, Math.min(origY + (event.pageY - startY), maxTop))
}
function onFieldMouseUp() {
  if (!dragSession) return
  dragSession = null
  window.removeEventListener('pointermove', onFieldMouseMove)
  window.removeEventListener('pointerup', onFieldMouseUp)
  emitUpdate()
}

// ── Resize an existing field via its corner handle ──────────────────────────
let resizeSession = null
function onResizeMouseDown(field, event) {
  if (props.disabled) return
  resizeSession = { field, startX: event.pageX, startY: event.pageY, startWidth: field.width || 150, startHeight: field.height || 30 }
  window.addEventListener('pointermove', onResizeMouseMove)
  window.addEventListener('pointerup', onResizeMouseUp)
  event.preventDefault()
}
function onResizeMouseMove(event) {
  if (!resizeSession) return
  const { field, startX, startY, startWidth, startHeight } = resizeSession
  field.width = Math.max(40, startWidth + (event.pageX - startX))
  field.height = Math.max(20, startHeight + (event.pageY - startY))
}
function onResizeMouseUp() {
  if (!resizeSession) return
  resizeSession = null
  window.removeEventListener('pointermove', onResizeMouseMove)
  window.removeEventListener('pointerup', onResizeMouseUp)
  emitUpdate()
}

// pdf.js page rendering lives in usePdfPages, shared with the E Sign builder.
const { pages, loading: loadingPdf, error: pdfError } = usePdfPages(computed(() => props.pdfUrl))
</script>

<style scoped>
.builder-tool {
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--app-border);
  background: var(--app-panel);
  font-size: 13px;
  font-weight: 500;
  color: var(--app-text);
  cursor: grab;
  user-select: none;
  transition: 0.15s;
}
.builder-tool:hover {
  border-color: var(--app-primary);
  background: var(--app-primary-tint);
}

.pdf-page-container {
  position: relative;
  margin: 0 auto 18px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
  background: #fff;
}
.pdf-page-img {
  width: 100%;
  height: 100%;
  display: block;
}
.fields-layer {
  position: absolute;
  inset: 0;
}

.pdf-field {
  position: absolute;
  display: flex;
  align-items: center;
  border: 2px dashed var(--app-text-muted);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  cursor: move;
  overflow: hidden;
  touch-action: none;
}
.pdf-field.selected {
  border-color: var(--app-primary);
  background: var(--app-primary-tint);
  box-shadow: 0 0 0 3px var(--app-primary-tint);
}
.pdf-field-preview {
  padding: 2px;
  width: 100%;
  height: 100%;
  overflow: hidden;
  white-space: normal;
  color: #111;
}
.field-close {
  position: absolute;
  top: -10px;
  right: -10px;
  width: 20px;
  height: 20px;
  border-radius: 999px;
  background: #ef4444;
  color: #fff;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: 0.15s;
}
.pdf-field:hover .field-close,
.pdf-field.selected .field-close {
  opacity: 1;
}
.resize-handle {
  position: absolute;
  right: -6px;
  bottom: -6px;
  width: 12px;
  height: 12px;
  /* a finger needs a bigger target than a cursor */
}
@media (pointer: coarse) {
  .resize-handle {
    right: -10px;
    bottom: -10px;
    width: 22px;
    height: 22px;
  }
}
.resize-handle {
  border-radius: 3px;
  background: var(--app-primary);
  cursor: nwse-resize;
  touch-action: none;
}
</style>

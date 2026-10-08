<template>
  <div class="flex flex-col gap-4">
      <div class="flex max-w-md flex-col gap-1.5">
        <label class="text-p-sm font-medium text-app-text-muted">Template</label>
        <AppCombobox v-model="template" :options="templateOptions" placeholder="Select template…" />
      </div>

      <div v-if="loadingTemplate" class="flex justify-center py-6"><LoadingIndicator class="h-5 w-5 text-app-text-muted" /></div>
      <div v-else-if="blocks.length" class="flex flex-col gap-4 border-t border-app-border pt-4">
        <p class="text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">Template fields</p>
        <div v-for="b in blocks" :key="keyOf(b)" :class="b.type === 'Rich_Text' ? 'w-full' : b.type === 'Text' ? 'max-w-3xl' : 'max-w-md'">
          <label class="mb-1.5 block text-p-sm font-medium text-app-text-muted">{{ b.label || b.name }}</label>
          <TextEditor
            v-if="b.type === 'Rich_Text'"
            class="agreement-editor"
            :content="values[keyOf(b)] || ''"
            :fixed-menu="EDITOR_BUTTONS"
            editor-class="min-h-[120px] max-h-[600px] resize-y overflow-auto rounded-b-lg border border-t-0 border-app-border px-3 py-2 text-p-sm"
            @change="(html) => (values[keyOf(b)] = html)"
          />
          <AppInput v-else :type="b.type === 'Number' ? 'number' : b.type === 'Date' ? 'date' : 'text'" :placeholder="`Enter ${b.label || b.name}…`" :model-value="values[keyOf(b)] || ''" @update:model-value="(v) => (values[keyOf(b)] = v)" />
        </div>
      </div>
    <div v-if="template" class="flex flex-wrap gap-2">
      <AppButton variant="outline" icon="eye" @click="preview">Preview</AppButton>
    </div>
  </div>
</template>

<script setup>
import AppInput from '@/components/ui/AppInput.vue'
// Pick a Pdf Agreement Template and fill its Text / Number / Date / rich-text
// blocks (de-duplicated by type+name, as on desk). Shared by the Sales Order
// Agreements tab and the E Sign "Use Template" action; the parent reads
// `template` and `payload()` through the component ref.
import { computed, h, reactive, ref, watch } from 'vue'
import { call, LoadingIndicator, TextEditor } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'
import { useResource } from '@/composables/list/useResource'

// The only formatting an agreement's rich-text field offers: bold, italic, underline,
// strike-through, font colour, ordered / unordered lists, table controls, left / right /
// justify alignment. (frappe-ui has no Justify button, so it is defined here.)
const AlignJustify = { render: () => h('span', { class: 'lucide-align-justify size-4' }) }
const JUSTIFY_BUTTON = {
  label: 'Align Justify',
  icon: AlignJustify,
  action: (editor) => editor.chain().focus().setTextAlign('justify').run(),
  isActive: (editor) => editor.isActive({ textAlign: 'justify' }),
}
const EDITOR_BUTTONS = [
  'Bold', 'Italic', 'Underline', 'Strikethrough',
  'Separator',
  'Bullet List', 'Numbered List',
  'Separator',
  ['InsertTable', 'AddColumnBefore', 'AddColumnAfter', 'DeleteColumn', 'AddRowBefore', 'AddRowAfter', 'DeleteRow', 'MergeCells', 'SplitCell', 'ToggleHeaderRow', 'DeleteTable'],
  'Separator',
  'Align Left', 'Align Right', JUSTIFY_BUTTON,
]

// ── builder ───────────────────────────────────────────────────────────
const templates = useResource({
  url: 'frappe.client.get_list',
  params: { doctype: 'Pdf Agreement Template', filters: { is_active: 1 }, fields: ['name', 'title'], limit_page_length: 100 },
  notifyOnError: false,
  auto: true,
})

const template = ref('')
const templateOptions = computed(() => (templates.resource.data || []).map((t) => ({ label: t.title || t.name, value: t.name })))
const blocks = ref([])
const values = reactive({})
const loadingTemplate = ref(false)
// Same key the server reads back: "<type>::<name>".
const keyOf = (b) => `${b.type}::${b.name}`

watch(template, async (name) => {
  blocks.value = []
  Object.keys(values).forEach((k) => delete values[k])
  if (!name) return
  loadingTemplate.value = true
  try {
    const tpl = await call('frappe.client.get', { doctype: 'Pdf Agreement Template', name })
    let parsed = []
    try {
      parsed = JSON.parse(tpl.fields_json || '[]')
    } catch {
      parsed = []
    }
    const seen = new Set()
    blocks.value = parsed.filter((b) => {
      if (!b.name || !b.type || !['Text', 'Number', 'Date', 'Rich_Text'].includes(b.type)) return false
      const key = `${b.type.trim().toLowerCase()}|${b.name.trim().toLowerCase()}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  } finally {
    loadingTemplate.value = false
  }
})

const payload = () => JSON.stringify(Object.fromEntries(blocks.value.map((b) => [keyOf(b), String(values[keyOf(b)] ?? '').trim()])))

const reset = () => (template.value = '')
defineExpose({ template, payload, reset })

// The preview endpoint answers with a PDF download, so it's a plain form POST
// into a new tab rather than an XHR.
function preview() {
  const form = document.createElement('form')
  form.method = 'POST'
  form.action = '/api/method/verp_staffing.crm.api.agreement.preview_agreement'
  form.target = '_blank'
  form.style.display = 'none'
  for (const [name, value] of Object.entries({ template: template.value, data: payload(), csrf_token: window.csrf_token })) {
    const input = document.createElement('input')
    input.type = 'hidden'
    input.name = name
    input.value = value
    form.appendChild(input)
  }
  document.body.appendChild(form)
  form.submit()
  document.body.removeChild(form)
}

</script>

<style>
/* Keep the whole toolbar inside the card: wrap onto a second row instead of running past it. */
.agreement-editor > .overflow-x-auto {
  display: flex;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  overflow-x: visible;
}
.agreement-editor > .overflow-x-auto > div {
  flex-wrap: wrap;
  width: 100%;
  min-width: 0;
}
.agreement-editor {
  width: 100%;
  max-width: 100%;
  min-width: 0;
}
</style>

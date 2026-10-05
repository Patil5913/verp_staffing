<template>
  <SectionCard :title="title" subtitle="Rendered from what is in the form now - save is not needed.">
    <div class="mb-3 flex flex-wrap items-end gap-2">
      <template v-if="!isEmail">
        <AppInput class="min-w-48" type="select" label="Show with" :options="modeOptions" v-model="mode" />
        <div v-if="mode === 'latest'" class="min-w-48 flex-1">
          <AppLinkField
            :doctype="previewDoctype"
            label="Record name (optional, else the latest)"
            placeholder="Latest"
            :disabled="!previewDoctype"
            v-model="reference"
          />
        </div>
      </template>
      <AppButton variant="solid" icon="eye" :loading="loading" @click="run">Preview</AppButton>
    </div>
    <p v-if="error" class="text-p-sm text-red-600">{{ error }}</p>
    <template v-else-if="result">
      <p v-if="result.subject !== undefined" class="mb-2 text-p-sm"><span class="text-app-text-muted">Subject: </span><span class="font-medium text-app-text">{{ result.subject || '-' }}</span></p>
      <p v-if="result.reference" class="mb-2 text-2xs text-app-text-muted">Using {{ result.reference }}</p>
      <iframe :srcdoc="frameDoc" sandbox="" class="h-[70vh] w-full rounded-lg border border-app-border bg-white" />
    </template>
  </SectionCard>
</template>

<script setup>
import { computed, ref } from 'vue'
import { call } from 'frappe-ui'
import SectionCard from '@/components/common/SectionCard.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import { normalizeError } from '@/utils/common/errors'

const props = defineProps({
  kind: { type: String, required: true }, // 'email' | 'print'
  detail: { type: Object, required: true },
  doctype: { type: String, default: '' },
  name: { type: String, default: '' },
  locked: { type: Boolean, default: false },
})

const isEmail = props.kind === 'email'
const title = isEmail ? 'Preview' : 'Print preview'
const modeOptions = [
  { label: 'Latest saved record', value: 'latest' },
  { label: 'Sample data', value: 'sample' },
  { label: 'Field names (e.g. {{ total_amount }})', value: 'placeholders' },
]
const mode = ref('latest')
const reference = ref('')
// Print formats are always for one doctype.
const previewDoctype = computed(() => props.detail.values.doc_type || '')
const loading = ref(false)
const error = ref('')
const result = ref(null)

const frameDoc = computed(() => `<!doctype html><meta charset="utf-8"><body style="font-family:sans-serif;margin:16px">${result.value?.html || ''}</body>`)

async function run() {
  const v = props.detail.values
  loading.value = true
  error.value = ''
  try {
    result.value = isEmail
      ? await call('verp_staffing.utils.template_preview.preview_email_template', {
          subject: v.subject, response: v.response, response_html: v.response_html, use_html: v.use_html ? 1 : 0,
        })
      : await call('verp_staffing.utils.template_preview.preview_print_format', {
          doc_type: v.doc_type, html: v.html, css: v.css, reference_name: reference.value || undefined, name: props.name, mode: mode.value,
        })
  } catch (e) {
    result.value = null
    error.value = normalizeError(e).message
  } finally {
    loading.value = false
  }
}
</script>

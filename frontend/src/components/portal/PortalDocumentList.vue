<template>
  <div>
    <ul class="divide-y divide-app-border">
      <li v-for="doc in data.lead_documents" :key="doc.field" class="flex flex-wrap items-center justify-between gap-3 py-3">
        <span class="flex min-w-0 items-center gap-3">
          <span class="flex size-9 shrink-0 items-center justify-center rounded-lg" :class="has(doc) ? 'bg-green-500/10 text-green-600' : 'bg-amber-500/10 text-amber-600'">
            <span :class="has(doc) ? 'lucide-file-check' : 'lucide-file-up'" class="size-5" />
          </span>
          <span class="min-w-0">
            <span class="block text-p-sm font-medium text-app-text">{{ doc.label }}</span>
            <span class="block truncate text-2xs text-app-text-muted">{{ docNames[doc.field] ?? doc.uploaded_file_name ?? 'Not uploaded yet' }}</span>
          </span>
        </span>
        <span class="flex items-center gap-2">
          <AppButton v-if="has(doc)" variant="outline" size="sm" icon="download" @click="download(doc.field)">Download</AppButton>
          <AppButton :variant="has(doc) ? 'outline' : 'primary'" size="sm" icon="upload" :loading="busy === doc.field" @click="pick(doc.field)">{{ has(doc) ? 'Update' : 'Upload' }}</AppButton>
        </span>
      </li>
    </ul>
    <input ref="fileInput" type="file" class="hidden" @change="onFile" />
  </div>
</template>

<script setup>
// The customer's own documents with upload/download; used on the dashboard and the Documents page.
// Icon classes for Tailwind: lucide-file-check lucide-file-up
import { ref } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import { usePortal } from '@/composables/portal/usePortal'
import { notify } from '@/utils/common/notify'

const { data, uploadDocument, docNames } = usePortal()
const fileInput = ref(null)
const busy = ref('')
let field = ''

const has = (doc) => Boolean(doc.file_name || docNames[doc.field])
const download = (f) => {
  window.location.href = `/verp/portal/documents/${encodeURIComponent(f)}/download`
}
const pick = (f) => {
  field = f
  fileInput.value?.click()
}

async function onFile(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  busy.value = field
  try {
    await uploadDocument(field, file)
    notify.success('Document uploaded.')
  } catch (err) {
    notify.error(err.message)
  } finally {
    busy.value = ''
  }
}
</script>

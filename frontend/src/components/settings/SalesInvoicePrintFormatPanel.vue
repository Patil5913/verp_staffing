<template>
  <div class="flex flex-col gap-4 px-3 py-4 md:px-6">
    <div class="flex items-center justify-between gap-3">
      <p class="text-p-sm text-app-text-muted">
        The layout used whenever a Sales Invoice is printed. Edit the Jinja template below, then preview it against a real invoice.
      </p>
      <AppButton :disabled="!isDirty" :loading="detail.save.isLoading" @click="onSave">Save Print Format</AppButton>
    </div>
    <DocDetailView
      doctype="Print Format"
      :detail="detail"
      :fieldnames="['html', 'css']"
      :field-overrides="{ html: { rows: 30 }, css: { rows: 20 } }"
    />
    <TemplatePreview kind="print" doctype="Print Format" name="Verp Sales Invoice" :detail="detail" />
  </div>
</template>

<script setup>
// Edits the Verp Sales Invoice print format from inside ERP Configuration. Reuses the
// generic doc detail loader, field grid and preview used by the Print Format detail page.
import { ref } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import TemplatePreview from '@/components/detail/templates/TemplatePreview.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'

const { detail, isDirty, onSave } = useDetailPageController(ref('Print Format'), ref('Verp Sales Invoice'))
</script>

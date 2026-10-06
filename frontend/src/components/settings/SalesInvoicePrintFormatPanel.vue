<template>
  <div class="flex h-full flex-col gap-4 overflow-y-auto px-3 py-4 md:px-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex gap-1 rounded-lg bg-app-panel-2 p-1">
        <button
          v-for="t in subTabs"
          :key="t.key"
          type="button"
          class="rounded-md px-3 py-1.5 text-p-sm font-medium transition-colors"
          :class="activeSub === t.key ? 'bg-app-panel text-app-text shadow-sm' : 'text-app-text-muted hover:text-app-text'"
          @click="activeSub = t.key"
        >{{ t.label }}</button>
      </div>
      <AppButton :disabled="!isDirty" :loading="detail.save.isLoading" @click="onSave">Save Print Format</AppButton>
    </div>

    <template v-if="activeSub === 'format'">
      <DocDetailView
        v-for="section in formatSections"
        :key="section.title"
        doctype="Print Format"
        :detail="detail"
        :title="section.title"
        :fieldnames="section.fieldnames"
        :field-overrides="section.fieldOverrides ? section.fieldOverrides() : {}"
      />
    </template>

    <TemplatePreview v-else kind="print" doctype="Print Format" name="Verp Sales Invoice" :detail="detail" />
  </div>
</template>

<script setup>
// Edits the Verp Sales Invoice print format from inside ERP Configuration. Uses the same
// field sections as the Print Format detail page (printFormatConfig), plus its preview.
import { ref } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import TemplatePreview from '@/components/detail/templates/TemplatePreview.vue'
import { printFormatConfig } from '@/configs/detail/templates'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'

const { detail, isDirty, onSave } = useDetailPageController(ref('Print Format'), ref('Verp Sales Invoice'))

const subTabs = [
  { key: 'format', label: 'Format' },
  { key: 'preview', label: 'Preview' },
]
const activeSub = ref('format')
const formatSections = printFormatConfig.tabs.find((t) => t.key === 'details').sections
</script>

<template>
  <div class="flex min-h-full justify-center px-4 py-8">
    <div class="w-full max-w-3xl">
      <div class="mb-6">
        <h1 class="text-xl font-semibold text-app-text">Import Data</h1>
        <p class="mt-1 text-p-sm text-app-text-muted">Bring your existing spreadsheets into the system, step by step.</p>
      </div>
      <div class="rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
        <DataImportWizard />
      </div>
    </div>
  </div>
</template>

<script setup>
// Standalone home for the reusable import wizard, linked from the profile
// menu (ProfileMenu.vue) rather than the sidebar - importing data is an
// occasional admin task, not everyday navigation. The same DataImportWizard
// also runs inline inside SetupWizardPage.vue as an optional step.
import DataImportWizard from '@/components/common/DataImportWizard.vue'
</script>

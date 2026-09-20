<template>
  <Teleport to="body">
    <Transition name="ucd-fade">
      <div v-if="state.open" class="fixed inset-0 z-[100] flex items-center justify-center px-4">
        <div class="absolute inset-0 bg-black/50 backdrop-blur-[2px]" @click="!state.saving && settle(false)" />

        <div
          class="relative w-full max-w-sm rounded-2xl border border-app-border bg-app-panel p-6 shadow-2xl"
          role="alertdialog"
          aria-modal="true"
        >
          <div class="flex items-start gap-3">
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-500/15">
              <FeatherIcon name="alert-triangle" class="h-5 w-5 text-amber-500" />
            </div>
            <div class="min-w-0 pt-1">
              <h2 class="text-p-lg font-medium text-app-text">{{ state.title }}</h2>
              <p class="mt-1 text-p-sm text-app-text-muted">{{ state.message }}</p>
            </div>
          </div>

          <div class="mt-6 flex flex-wrap justify-end gap-2">
            <AppButton variant="outline" :disabled="state.saving" @click="settle(false)">
              {{ state.cancelLabel }}
            </AppButton>
            <AppButton variant="danger" icon="log-out" :disabled="state.saving" @click="settle(true)">
              {{ state.leaveLabel }}
            </AppButton>
            <AppButton v-if="state.onSave" variant="primary" icon="save" :loading="state.saving" @click="onSaveClick">
              Save
            </AppButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { FeatherIcon } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import { useConfirmDialogState } from '@/utils/common/confirmDialog'

const { state, settle, onSaveClick } = useConfirmDialogState()
</script>

<style scoped>
.ucd-fade-enter-active,
.ucd-fade-leave-active {
  transition: opacity 0.15s ease;
}
.ucd-fade-enter-from,
.ucd-fade-leave-to {
  opacity: 0;
}
</style>

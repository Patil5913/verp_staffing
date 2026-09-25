<template>
  <div class="flex shrink-0 flex-wrap items-center justify-end gap-2">
    <!-- Any record-specific actions (Create Opportunity, Send Reset
    Password Email, Enable/Disable, ...) always go before Save/Delete. -->
    <slot />

    <!-- Rule, enforced structurally rather than by convention: Save is
    always immediately beside Delete, in this order, regardless of what
    else this page adds - a future action added via the slot above can
    never land between them. -->
    <AppButton v-if="showSubmit" variant="primary" icon="check-circle" :loading="submitLoading" @click="$emit('submit')">
      Submit
    </AppButton>
    <AppButton v-if="showCancel" variant="outline" icon="x-circle" @click="$emit('cancel')">Cancel</AppButton>
    <AppButton
      v-if="showSave"
      variant="primary"
      icon="save"
      :disabled="!saveDirty"
      :loading="saveLoading"
      @click="$emit('save')"
    >
      Save
    </AppButton>
    <AppButton v-if="showDelete" variant="danger" icon="trash-2" :loading="deleteLoading" @click="$emit('delete')">
      Delete
    </AppButton>
  </div>
</template>

<script setup>
import AppButton from '@/components/ui/AppButton.vue'

defineProps({
  showSave: { type: Boolean, default: false },
  // Save dims (disabled) until there's an actual unsaved change - flip
  // this from the page's dirty-tracking (see useDocDetail's isDirty).
  saveDirty: { type: Boolean, default: true },
  saveLoading: { type: Boolean, default: false },
  showDelete: { type: Boolean, default: false },
  deleteLoading: { type: Boolean, default: false },
  // Submittable doctypes only - see useDetailPageController's onSubmit /
  // onCancelDoc. Submit sits before Save/Delete like any other page action.
  showSubmit: { type: Boolean, default: false },
  submitLoading: { type: Boolean, default: false },
  showCancel: { type: Boolean, default: false },
})
defineEmits(['save', 'delete', 'submit', 'cancel'])
</script>

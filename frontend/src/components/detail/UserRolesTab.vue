<template>
  <div class="flex flex-col gap-6">
    <StateBanner
      v-if="matrix.hasError"
      icon="alert-triangle"
      title="Couldn't load roles"
      :description="matrix.errorMessage"
    />
    <div v-else-if="matrix.isLoading && !matrix.resource.data" class="flex justify-center py-16">
      <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
    </div>

    <div v-else class="rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
      <div class="mb-4 flex items-center justify-between">
        <div>
          <h2 class="text-p-lg font-medium text-app-text">Roles & Permissions</h2>
          <p class="text-p-sm text-app-text-muted">Every role this user should have access as.</p>
        </div>
        <AppButton v-if="canWrite" size="sm" icon="save" :loading="saving" @click="submit">Save Roles</AppButton>
      </div>

      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label
          v-for="role in allRoles"
          :key="role"
          class="flex items-center gap-2 rounded-lg border border-app-border px-3 py-2 transition-colors"
          :class="canWrite ? 'cursor-pointer hover:border-app-primary/40 hover:bg-app-panel-2' : 'opacity-70'"
        >
          <AppCheckbox :model-value="checked.has(role)" :disabled="!canWrite" @update:model-value="toggle(role)" />
          <span class="truncate text-p-sm text-app-text">{{ role }}</span>
        </label>
      </div>

      <p v-if="!allRoles.length" class="py-8 text-center text-p-sm text-app-text-muted">No roles found.</p>
    </div>
  </div>
</template>

<script setup>
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
import { computed } from 'vue'
import { LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { useUserRoles } from '@/composables/detail/useUserRoles'

const props = defineProps({
  user: { type: String, required: true },
  canWrite: { type: Boolean, default: false },
})

const { matrix, allRoles, checked, toggle, submit, saving } = useUserRoles(
  computed(() => props.user),
)
</script>

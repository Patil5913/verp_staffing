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

      <div class="flex flex-col gap-4">
        <div
          v-for="(section, si) in sections"
          :key="section.label"
          class="flex flex-col gap-2 rounded-lg p-3"
          :style="sectionStyle(si)"
        >
          <button type="button" class="flex items-center gap-2 text-left" @click="toggleSection(section.label)">
            <FeatherIcon :name="isOpen(section.label) ? 'chevron-down' : 'chevron-right'" class="h-4 w-4 text-app-text-muted" />
            <span class="text-p-xs font-semibold uppercase tracking-wide text-app-text">{{ section.label }}</span>
            <AppBadge>{{ sectionSelected(section) }}/{{ section.roles.length }} selected</AppBadge>
          </button>
          <div v-show="isOpen(section.label)" class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            <label
              v-for="role in section.roles"
              :key="role"
              class="flex items-center gap-2 rounded-lg border border-app-border bg-app-panel px-3 py-2 transition-colors"
              :class="canWrite ? 'cursor-pointer hover:border-app-primary/40' : 'opacity-70'"
            >
              <AppCheckbox :model-value="checked.has(role)" :disabled="!canWrite" @update:model-value="toggle(role)" />
              <span class="truncate text-p-sm text-app-text">{{ role }}</span>
            </label>
          </div>
        </div>
      </div>

      <p v-if="!allRoles.length" class="py-8 text-center text-p-sm text-app-text-muted">No roles found.</p>
    </div>
  </div>
</template>

<script setup>
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
import { computed, ref } from 'vue'
import { LoadingIndicator, FeatherIcon } from 'frappe-ui'
import AppBadge from '@/components/ui/AppBadge.vue'
import { groupRolesByModule } from '@/configs/detail/roleModules'
import AppButton from '@/components/ui/AppButton.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { useUserRoles } from '@/composables/detail/useUserRoles'

const props = defineProps({
  user: { type: String, required: true },
  canWrite: { type: Boolean, default: false },
})

// Same tinted, colour-cycled blocks as the ERP Configuration field selector.
const SECTION_RGB = ['37, 99, 235', '5, 150, 105', '217, 119, 6', '124, 58, 237', '225, 29, 72', '8, 145, 178']
const sectionStyle = (i) => {
  const rgb = SECTION_RGB[i % SECTION_RGB.length]
  return {
    backgroundColor: `rgba(${rgb}, 0.12)`,
    border: `1px solid rgba(${rgb}, 0.4)`,
    borderLeft: `5px solid rgb(${rgb})`,
  }
}

const { matrix, allRoles, checked, toggle, submit, saving } = useUserRoles(
  computed(() => props.user),
)

const sections = computed(() => groupRolesByModule(allRoles.value))
// Collapsed by default - only the sections the user is opening are expanded.
const open = ref(new Set())
const isOpen = (label) => open.value.has(label)
function toggleSection(label) {
  const next = new Set(open.value)
  if (next.has(label)) next.delete(label)
  else next.add(label)
  open.value = next
}
const sectionSelected = (section) => section.roles.filter((r) => checked.value.has(r)).length
</script>

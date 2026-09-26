<template>
  <div class="rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
    <div class="mb-4">
      <h2 class="text-p-lg font-medium text-app-text">Assigned Users</h2>
      <p class="text-p-sm text-app-text-muted">Users who currently hold this role.</p>
    </div>
    <StateBanner v-if="users.hasError" icon="alert-triangle" title="Couldn't load users" :description="users.errorMessage" />
    <div v-else-if="users.isLoading && !users.resource.data" class="flex justify-center py-16">
      <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
    </div>
    <div v-else class="flex flex-col gap-2">
      <div
        v-for="u in users.resource.data"
        :key="u.name"
        class="flex items-center gap-3 rounded-lg border border-app-border px-4 py-3"
      >
        <router-link
          :to="{ name: 'DocDetail', params: { doctype: 'User', name: u.name } }"
          class="min-w-0 flex-1 hover:underline"
        >
          <p class="truncate text-p-sm font-medium text-app-text">{{ u.full_name || u.name }}</p>
          <p class="truncate text-p-xs text-app-text-muted">{{ u.name }} · {{ u.user_type }}</p>
        </router-link>
        <AppBadge :theme="u.enabled ? 'green' : 'red'">{{ u.enabled ? 'Active' : 'Inactive' }}</AppBadge>
        <AppButton
          v-if="canWrite"
          variant="danger"
          size="sm"
          icon="user-minus"
          :loading="removing.isLoading && removingUser === u.name"
          @click="onRemove(u.name)"
        >
          Remove Role
        </AppButton>
      </div>
      <p v-if="!users.resource.data?.length" class="py-8 text-center text-p-sm text-app-text-muted">
        No users have this role.
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppBadge from '@/components/ui/AppBadge.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { useResource } from '@/composables/list/useResource'

const props = defineProps({
  role: { type: String, required: true },
  canWrite: { type: Boolean, default: false },
})

const removingUser = ref('')
const removing = useResource({
  url: 'verp_staffing.utils.role_view.remove_role_from_user',
  onSuccess: (data) => users.resource.setData(data),
})
function onRemove(user) {
  removingUser.value = user
  removing.resource.submit({ role: props.role, user })
}

const users = useResource({
  url: 'verp_staffing.utils.role_view.get_role_users',
  makeParams: () => ({ role: props.role }),
  auto: true,
})
</script>

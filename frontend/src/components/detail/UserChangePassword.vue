<template>
  <div class="rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
    <h2 class="text-p-lg font-medium text-app-text">Change Password</h2>
    <p class="mb-4 text-p-sm text-app-text-muted">Set a new password for this user.</p>

    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <FormControl type="password" label="New Password" v-model="newPassword" />
      <FormControl type="password" label="Confirm Password" v-model="confirmPassword" />
    </div>
    <p v-if="mismatch" class="mt-2 text-p-xs text-red-600">Passwords don't match.</p>

    <div class="mt-4 flex justify-end">
      <AppButton icon="key" :disabled="!canSubmit" :loading="saving" @click="onSubmit">Update Password</AppButton>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { FormControl } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'

const props = defineProps({
  user: { type: String, required: true },
})

const newPassword = ref('')
const confirmPassword = ref('')

const mismatch = computed(
  () => Boolean(newPassword.value || confirmPassword.value) && newPassword.value !== confirmPassword.value,
)

const canSubmit = computed(() => newPassword.value.length > 0 && !mismatch.value)

const changePassword = useResource({
  url: 'verp_staffing.utils.user_view.set_new_password',
})
const saving = computed(() => changePassword.isLoading)

async function onSubmit() {
  if (!canSubmit.value) return
  const result = await changePassword.resource.submit({ user: props.user, new_password: newPassword.value })
  if (!result?.ok) return

  newPassword.value = ''
  confirmPassword.value = ''
  notify.success('Password updated.')
}
</script>

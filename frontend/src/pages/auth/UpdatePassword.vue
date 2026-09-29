<template>
  <div class="flex min-h-screen items-center justify-center bg-app-bg px-4">
    <div class="w-full max-w-sm">
      <div class="mb-8 flex flex-col items-center gap-3">
        <img :src="appLogo" :alt="appName" class="h-10 w-auto max-w-[10rem] object-contain" />
        <h1 class="text-xl font-semibold text-app-text">{{ appName }}</h1>
      </div>

      <div class="rounded-lg border border-app-border bg-app-panel p-6">
        <h2 class="mb-1 text-lg font-semibold text-app-text">Set new password</h2>
        <p class="mb-5 text-p-sm text-app-text-muted">Choose a new password for your account.</p>

        <form class="flex flex-col gap-4" @submit.prevent="submit">
          <Password
            label="New password"
            v-model="password"
            autocomplete="new-password"
            :disabled="update.loading"
            required
          />
          <Password
            label="Confirm password"
            v-model="confirm"
            autocomplete="new-password"
            :disabled="update.loading"
            required
          />

          <ErrorMessage :message="errorMessage" />

          <AppButton
            type="submit"
            variant="solid"
            theme="blue"
            class="w-full justify-center"
            :loading="update.loading"
          >
            Update password
          </AppButton>

          <router-link to="/login" class="text-center text-p-sm text-app-text-muted hover:text-app-primary">
            Back to sign in
          </router-link>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import AppButton from '@/components/ui/AppButton.vue'
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ErrorMessage, Password, createResource } from 'frappe-ui'
import { useBranding } from '@/composables/layout/useBranding'

const { appName, appLogo } = useBranding()
const route = useRoute()

const password = ref('')
const confirm = ref('')
const localError = ref('')

// Frappe's own update_password validates the reset key and the password policy, then signs the user in.
const update = createResource({
  url: 'frappe.core.doctype.user.user.update_password',
  makeParams: () => ({ new_password: password.value, key: route.query.key }),
})

const errorMessage = computed(
  () => localError.value || update.error?.messages?.[0] || update.error?.message,
)

async function submit() {
  localError.value = ''
  if (!route.query.key) {
    localError.value = 'This reset link is invalid. Request a new one from the sign-in page.'
    return
  }
  if (password.value !== confirm.value) {
    localError.value = "Passwords don't match."
    return
  }
  let result
  try {
    result = await update.submit()
  } catch {
    return
  }
  // Frappe answers 410 with a message string when the key is invalid or expired.
  if (update.error) return
  // Full reload so the shell picks up the session Frappe just created.
  window.location.href = typeof result === 'string' && result.startsWith('/verp') ? result : '/verp'
}
</script>

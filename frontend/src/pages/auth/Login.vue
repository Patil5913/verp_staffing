<template>
  <div class="flex min-h-screen items-center justify-center bg-app-bg px-4">
    <div class="w-full max-w-sm">
      <div class="mb-8 flex flex-col items-center gap-3">
        <img :src="appLogo" :alt="appName" class="h-10 w-10" />
        <h1 class="text-xl font-semibold text-app-text">{{ appName }}</h1>
      </div>

      <div class="rounded-lg border border-app-border bg-app-panel p-6">
        <template v-if="mode === 'login'">
          <h2 class="mb-1 text-lg font-semibold text-app-text">Sign in</h2>
          <p class="mb-5 text-p-sm text-app-text-muted">
            Use your account to continue.
          </p>

          <form class="flex flex-col gap-4" @submit.prevent="submitLogin">
            <AppInput
              type="text"
              label="Email"
              v-model="form.email"
              autocomplete="username"
              :disabled="login.loading"
              required
            />
            <Password
              label="Password"
              v-model="form.password"
              autocomplete="current-password"
              :disabled="login.loading"
              required
            />

            <ErrorMessage :message="errorMessage" />

            <AppButton
              type="submit"
              variant="solid"
              theme="blue"
              class="w-full justify-center"
              :loading="login.loading"
            >
              Sign in
            </AppButton>

            <button
              type="button"
              class="text-p-sm text-app-text-muted hover:text-app-primary"
              @click="switchToReset"
            >
              Forgot your password?
            </button>
          </form>
        </template>

        <template v-else>
          <h2 class="mb-1 text-lg font-semibold text-app-text">
            Reset password
          </h2>
          <p class="mb-5 text-p-sm text-app-text-muted">
            Enter your account email and we'll send you a reset link.
          </p>

          <form class="flex flex-col gap-4" @submit.prevent="submitReset">
            <AppInput
              type="text"
              label="Email"
              v-model="resetEmail"
              autocomplete="username"
              :disabled="reset.loading"
              required
            />

            <AppButton
              type="submit"
              variant="solid"
              theme="blue"
              class="w-full justify-center"
              :loading="reset.loading"
            >
              Send reset link
            </AppButton>

            <button
              type="button"
              class="text-p-sm text-app-text-muted hover:text-app-primary"
              @click="mode = 'login'"
            >
              Back to sign in
            </button>
          </form>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import AppInput from '@/components/ui/AppInput.vue'
import AppButton from '@/components/ui/AppButton.vue'
import { computed, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  ErrorMessage,
  Password,
  createResource,
} from 'frappe-ui'
import { useBranding } from '@/composables/layout/useBranding'
import { notify } from '@/utils/common/notify'

const { appName, appLogo } = useBranding()

const route = useRoute()
const mode = ref('login')

const form = reactive({ email: '', password: '' })

// Frappe's own `login` whitelisted endpoint validates the credentials,
// creates the session cookie, and loads the user's roles/permissions.
// Nothing about authentication is implemented on our side here - this is
// just a styled form posting to it.
const login = createResource({
  url: 'login',
  makeParams: () => ({ usr: form.email, pwd: form.password }),
})

const errorMessage = computed(
  () => login.error?.messages?.[0] || login.error?.message,
)

async function submitLogin() {
  if (!form.email || !form.password) return
  try {
    await login.submit()
  } catch {
    // login.error is already set and rendered via ErrorMessage above
    return
  }

  // A hard navigation, not router.push: the SPA shell reads window.user /
  // window.full_name from the server on every full page load (see
  // verp_staffing/www/verp.py get_context), so a real reload is what picks
  // up the session Frappe just created.
  const redirectTo = route.query['redirect-to']
  window.location.href =
    typeof redirectTo === 'string' && redirectTo.startsWith('/verp')
      ? redirectTo
      : '/verp'
}

const resetEmail = ref('')

// frappe.core.doctype.user.user.reset_password is Frappe's own, rate-limited,
// allow_guest whitelisted method - it always replies with the same generic
// message whether or not the account exists, so we never learn (or leak)
// anything about the account here either.
const reset = createResource({
  url: 'frappe.core.doctype.user.user.reset_password',
  makeParams: () => ({ user: resetEmail.value }),
  onSuccess() {
    notify.success(
      'If that account exists, a password reset link has been sent to it.',
    )
    mode.value = 'login'
  },
  onError() {
    notify.error('Could not send the reset link. Please try again shortly.')
  },
})

function switchToReset() {
  resetEmail.value = form.email
  mode.value = 'reset'
}

function submitReset() {
  if (!resetEmail.value) return
  reset.submit()
}
</script>

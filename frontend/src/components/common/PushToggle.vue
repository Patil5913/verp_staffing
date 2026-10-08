<template>
  <button
    type="button"
    class="flex size-9 items-center justify-center rounded-lg transition-colors hover:bg-app-panel-2"
    :class="state === 'on' ? 'text-app-primary' : 'text-app-text-muted hover:text-app-text'"
    :aria-label="title"
    :title="title"
    @click="onClick"
  >
    <span :class="state === 'on' ? 'lucide-bell-ring' : state === 'blocked' || state === 'unsupported' ? 'lucide-bell-off' : 'lucide-bell-plus'" class="size-5" />
  </button>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { usePushNotifications } from '@/composables/pwa/usePushNotifications'
import { notify } from '@/utils/common/notify'

// Always visible so it's easy to find: shows whether this device gets message
// notifications, and what to do when it can't.
const { supported, permission, enable, autoPrompt } = usePushNotifications()
onMounted(autoPrompt)

const state = computed(() => {
  if (!supported) return 'unsupported'
  if (permission.value === 'granted') return 'on'
  if (permission.value === 'denied') return 'blocked'
  return 'off'
})
const title = computed(
  () =>
    ({
      on: 'Notifications are on for this device',
      off: 'Turn on message notifications',
      blocked: 'Notifications are blocked in the browser',
      unsupported: 'Notifications are not available here',
    })[state.value],
)

async function onClick() {
  if (state.value === 'on') return notify.success('Notifications are on for this device.')
  if (state.value === 'blocked') return notify.warning('Notifications are blocked. Allow them for this site in your browser settings, then try again.')
  if (state.value === 'unsupported') {
    return notify.warning(
      window.isSecureContext
        ? "This browser doesn't support push notifications. On iPhone, add the app to the Home Screen first."
        : 'Push notifications need a secure (https) connection.',
    )
  }
  try {
    if (await enable()) notify.success('Notifications are on for this device.')
  } catch {
    notify.error("Couldn't turn on notifications.")
  }
}
</script>

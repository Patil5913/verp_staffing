<template>
  <div class="border-t border-app-border p-2">
    <Dropdown :options="menuOptions" side="top" align="start">
      <template #default="{ open }">
        <button
          type="button"
          class="flex w-full items-center gap-2.5 rounded-md p-2 text-left transition-colors"
          :class="[
            collapsed ? 'justify-center' : '',
            open ? 'bg-app-panel-2' : 'hover:bg-app-panel-2',
          ]"
          :title="collapsed ? fullName : undefined"
        >
          <Avatar :image="userImage" :label="fullName" size="md" />
          <template v-if="!collapsed">
            <span class="min-w-0 flex-1">
              <span
                class="block truncate text-p-sm font-medium text-app-text"
              >
                {{ fullName }}
              </span>
              <span
                v-if="userEmail"
                class="block truncate text-2xs text-app-text-muted"
              >
                {{ userEmail }}
              </span>
            </span>
            <span
              class="lucide-chevron-up size-3.5 shrink-0 text-app-text-muted"
            />
          </template>
        </button>
      </template>
    </Dropdown>

    <KeyboardShortcutsDialog v-model="showShortcuts" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Avatar, Dropdown, call } from 'frappe-ui'
import { useTheme } from '@/composables/common/useTheme'
import { notify } from '@/utils/common/notify'
import { useInstallPrompt } from '@/composables/common/useInstallPrompt'
import KeyboardShortcutsDialog from '@/components/overlays/KeyboardShortcutsDialog.vue'

defineProps({
  collapsed: { type: Boolean, default: false },
})

const router = useRouter()
const fullName = window.full_name || window.user || 'User'
const userEmail = window.user && window.user !== fullName ? window.user : ''
const userImage = window.user_image || null

const { preference, setPreference } = useTheme()

const showShortcuts = ref(false)
const { canInstall, showIosHint, install } = useInstallPrompt()

function installApp() {
  if (canInstall.value) install()
  else notify.info('To install: tap the Share button, then "Add to Home Screen".')
}

function openSettings() {
  // The user's own User record, in this app.
  router.push(window.user ? `/User/${encodeURIComponent(window.user)}` : '/')
}

function openSidebarCustomization() {
  router.push('/Sidebar Master')
}

async function logout() {
  notify.info('Logging you out...')
  try {
    await call('logout')
  } finally {
    window.location.href = '/verp/login'
  }
}

// Same as desk's own navbar "Reload": clears this session's server-side
// cache (cached user/roles/bootinfo in Redis — not a whole-site flush; see
// frappe.sessions.clear in apps/frappe/frappe/sessions.py), then does a
// hard reload. Throttled like core so it can't be spammed.
let lastReloadAt = 0
async function reload() {
  const now = Date.now()
  if (now - lastReloadAt < 10000) return
  lastReloadAt = now
  try {
    const message = await call('frappe.sessions.clear')
    notify.success(message || 'Cache cleared.')
  } catch {
    notify.error('Failed to clear cache.')
  } finally {
    window.location.reload()
  }
}

const menuOptions = computed(() => [
  // a customer has no staff user record to edit
  ...(window.is_portal_user ? [] : [{ icon: 'lucide-settings', label: 'My Settings', onClick: openSettings }]),
  ...(window.is_portal_user ? [] : [{ icon: 'lucide-layout-panel-left', label: 'Customize Sidebar', onClick: openSidebarCustomization }]),
  {
    icon: 'lucide-monitor',
    label: 'Theme',
    submenu: [
      {
        label: 'System',
        selected: preference.value === 'system',
        onClick: () => setPreference('system'),
      },
      {
        label: 'Light',
        selected: preference.value === 'light',
        onClick: () => setPreference('light'),
      },
      {
        label: 'Dark',
        selected: preference.value === 'dark',
        onClick: () => setPreference('dark'),
      },
    ],
  },
  {
    group: 'Account',
    items: [
      ...(canInstall.value || showIosHint.value
        ? [{ icon: 'lucide-download', label: 'Install app', onClick: installApp }]
        : []),
      {
        icon: 'lucide-refresh-cw',
        label: 'Reload',
        onClick: reload,
      },
      {
        icon: 'lucide-keyboard',
        label: 'Keyboard Shortcuts',
        onClick: () => (showShortcuts.value = true),
      },
      {
        icon: 'lucide-log-out',
        label: 'Log out',
        onClick: logout,
      },
    ],
  },
])
</script>

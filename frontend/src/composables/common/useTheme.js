import { computed, ref, watchEffect } from 'vue'
import { notify } from '@/utils/common/notify'

const STORAGE_KEY = 'verp-theme'
const VALID_PREFERENCES = ['system', 'light', 'dark']
const PREFERENCE_LABELS = {
  system: 'Using system theme',
  light: 'Switched to light theme',
  dark: 'Switched to dark theme',
}

function getStoredPreference() {
  try {
    let value = localStorage.getItem(STORAGE_KEY)
    return VALID_PREFERENCES.includes(value) ? value : 'system'
  } catch {
    return 'system'
  }
}

// module-level state: one shared theme across the whole app
const preference = ref(getStoredPreference())

const media = window.matchMedia('(prefers-color-scheme: dark)')
const systemPrefersDark = ref(media.matches)
media.addEventListener('change', (e) => {
  systemPrefersDark.value = e.matches
})

// what actually gets applied: 'system' resolves to the OS preference,
// 'light'/'dark' are explicit overrides
const resolvedTheme = computed(() => {
  if (preference.value === 'system') {
    return systemPrefersDark.value ? 'dark' : 'light'
  }
  return preference.value
})

watchEffect(() => {
  document.documentElement.setAttribute('data-theme', resolvedTheme.value)
  try {
    localStorage.setItem(STORAGE_KEY, preference.value)
  } catch {
    // ignore (private browsing / storage disabled)
  }
})

export function useTheme() {
  function setPreference(value) {
    if (VALID_PREFERENCES.includes(value) && value !== preference.value) {
      preference.value = value
      notify.info(PREFERENCE_LABELS[value])
    }
  }

  return { preference, resolvedTheme, setPreference }
}

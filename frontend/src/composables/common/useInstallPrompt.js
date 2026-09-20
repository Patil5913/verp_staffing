import { computed, ref } from 'vue'

// module-level: `beforeinstallprompt` fires once, early, before any component exists
const deferredPrompt = ref(null)
const installed = ref(
  typeof window !== 'undefined' &&
    (window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true),
)

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    deferredPrompt.value = e
  })
  window.addEventListener('appinstalled', () => {
    installed.value = true
    deferredPrompt.value = null
  })
}

const isIos = typeof navigator !== 'undefined' && /iphone|ipad|ipod/i.test(navigator.userAgent)

// Chromium offers a real install prompt; iOS Safari has none, so the UI shows
// "Share → Add to Home Screen" instructions instead.
export function useInstallPrompt() {
  const canInstall = computed(() => !installed.value && !!deferredPrompt.value)
  const showIosHint = computed(() => !installed.value && isIos)

  async function install() {
    const prompt = deferredPrompt.value
    if (!prompt) return
    prompt.prompt()
    await prompt.userChoice
    deferredPrompt.value = null
  }

  return { canInstall, showIosHint, installed, install }
}

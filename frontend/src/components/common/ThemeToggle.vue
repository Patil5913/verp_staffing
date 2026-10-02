<template>
  <div
    class="inline-flex items-center gap-0.5 rounded-md border border-app-border bg-app-panel p-0.5"
  >
    <button
      v-for="opt in options"
      :key="opt.value"
      type="button"
      class="inline-flex h-7 w-7 items-center justify-center rounded transition-colors"
      :class="
        preference === opt.value
          ? 'bg-app-primary text-white'
          : 'text-app-text-muted hover:bg-app-panel-2 hover:text-app-text'
      "
      :aria-label="opt.label"
      :aria-pressed="preference === opt.value"
      @click="setPreference(opt.value)"
    >
      <component :is="opt.icon" class="size-4" />
    </button>
  </div>
</template>

<script setup>
import { useTheme } from '@/composables/common/useTheme'
import LucideMonitor from '~icons/lucide/monitor'
import LucideSun from '~icons/lucide/sun'
import LucideMoon from '~icons/lucide/moon'

const { preference, setPreference } = useTheme()

const options = [
  { value: 'system', label: 'Use system theme', icon: LucideMonitor },
  { value: 'light', label: 'Light theme', icon: LucideSun },
  { value: 'dark', label: 'Dark theme', icon: LucideMoon },
]
</script>

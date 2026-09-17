<template>
  <component
    :is="isInternal ? 'router-link' : 'a'"
    v-bind="isInternal ? { to: internalTo } : { href: route }"
    class="relative flex h-[34px] items-center gap-2.5 rounded-md text-p-sm transition-colors"
    :class="[
      collapsed ? 'justify-center px-0' : 'px-2.5',
      !collapsed && nested ? 'ml-[19px]' : '',
      active
        ? 'font-medium text-app-primary'
        : 'text-app-text hover:bg-app-panel-2',
    ]"
    :style="active ? { backgroundColor: 'var(--app-primary-tint)' } : {}"
    :title="shortcut ? `${label} (${shortcut})` : label"
  >
    <span
      v-if="active && !collapsed"
      class="absolute top-[18%] bottom-[18%] w-[3px] rounded-full bg-app-primary"
      :class="nested ? 'left-0' : 'left-1'"
    />
    <span
      :class="[
        'lucide-' + icon,
        'size-4',
        'shrink-0',
        active ? 'text-app-primary' : 'text-app-text-muted',
      ]"
    />
    <span v-if="!collapsed" class="min-w-0 flex-1 truncate">{{ label }}</span>
  </component>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  route: { type: String, default: '' },
  label: { type: String, required: true },
  icon: { type: String, default: 'circle' },
  shortcut: { type: String, default: '' },
  active: { type: Boolean, default: false },
  nested: { type: Boolean, default: false },
  collapsed: { type: Boolean, default: false },
})

// Pages already ported into this SPA live under /verp and use vue-router;
// everything else still points at the classic desk (/app/...) and needs a
// full browser navigation.
const isInternal = computed(() => props.route?.startsWith('/verp'))

// vue-router's `to` is resolved against the router's own path space, which
// already excludes the `history` base ('/verp' — see router.js); router-link
// re-adds it when building the actual href. Passing the full `/verp/...`
// route straight through would resolve to no route at all and link to a
// doubled "/verp/verp/..." href.
const internalTo = computed(() => props.route.replace(/^\/verp/, '') || '/')
</script>

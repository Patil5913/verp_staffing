<template>
  <component
    :is="isInternal ? 'router-link' : 'a'"
    v-bind="isInternal ? { to: internalTo } : { href: route }"
    class="group relative flex h-[34px] items-center gap-2.5 rounded-md text-p-sm transition-colors"
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
    <!-- Pending Payment Requests: a small red dot while any payment waits for verification. -->
    <span
      v-if="showPendingDot"
      class="size-2 shrink-0 rounded-full bg-red-500"
      :class="collapsed ? 'absolute right-1.5 top-1.5' : ''"
      title="Payments waiting for verification"
    />
    <button
      v-if="showQuickCreate && !collapsed"
      type="button"
      class="flex size-5 shrink-0 items-center justify-center rounded text-app-text-muted opacity-0 transition-opacity hover:bg-app-panel hover:text-app-primary group-hover:opacity-100 focus-visible:opacity-100"
      :title="`New ${doctype}`"
      @click.stop.prevent="onQuickCreate"
      @mousedown.stop
    >
      <span class="lucide-plus size-3.5" />
    </button>
  </component>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { canQuickCreateFromSidebar } from '@/utils/layout/sidebarPlus'
import { usePendingPaymentRequests } from '@/composables/layout/usePendingPaymentRequests'

const props = defineProps({
  route: { type: String, default: '' },
  label: { type: String, required: true },
  icon: { type: String, default: 'circle' },
  shortcut: { type: String, default: '' },
  active: { type: Boolean, default: false },
  nested: { type: Boolean, default: false },
  collapsed: { type: Boolean, default: false },
  // The Doctype this link points at, if any - drives the "+" quick-create
  // action. Left unset for non-Doctype links (Dashboard, Reports, ...) and
  // never set at all for type_2 dropdown parent buttons, which aren't
  // SidebarLink instances in the first place.
  doctype: { type: String, default: '' },
})

const router = useRouter()
const isPendingPaymentLink = computed(() => /pending-pe-requests/.test(props.route || ''))
// Only this one link ever asks for the count.
const pendingCount = computed(() => (isPendingPaymentLink.value ? usePendingPaymentRequests().count.value : 0))
const showPendingDot = computed(() => isPendingPaymentLink.value && pendingCount.value > 0)

const showQuickCreate = computed(() => canQuickCreateFromSidebar(props.doctype))

function onQuickCreate() {
  router.push(`/${encodeURIComponent(props.doctype)}/new`)
}

// Pages already ported into this SPA live under /verp and use vue-router;
// everything else still points at the classic desk (/app/...) and needs a
// full browser navigation.
const isInternal = computed(() => props.route?.startsWith('/verp'))

// vue-router's `to` is resolved against the router's own path space, which
// already excludes the `history` base ('/verp' - see router.js); router-link
// re-adds it when building the actual href. Passing the full `/verp/...`
// route straight through would resolve to no route at all and link to a
// doubled "/verp/verp/..." href.
const internalTo = computed(() => props.route.replace(/^\/verp/, '') || '/')
</script>

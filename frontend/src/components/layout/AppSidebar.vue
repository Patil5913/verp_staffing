<template>
  <!-- Phones: off-canvas drawer (always the full-width variant). md+: the
  collapsible rail beside the content. -->
  <nav
    class="fixed inset-y-0 left-0 z-40 h-full shrink-0 overflow-hidden border-r border-app-border bg-app-panel pb-[env(safe-area-inset-bottom)] pt-[env(safe-area-inset-top)] transition-[width,transform] duration-200 ease-in-out md:static md:z-auto md:translate-x-0 md:pb-0 md:pt-0"
    :class="[sidebarOpen ? 'w-64' : 'w-16', isMobile && !mobileNavOpen ? '-translate-x-full' : 'translate-x-0']"
  >
    <div class="flex h-full flex-col" :class="sidebarOpen ? 'w-64' : 'w-16'">
      <ScrollArea class="flex-1 px-2 py-3">
      <template v-for="cfg in config" :key="cfg.key">
        <!-- type_3: a single flat link, no children -->
        <SidebarLink
          v-if="cfg.parent_type === 'type_3'"
          :route="cfg.route"
          :label="cfg.label"
          :icon="resolveIconName(cfg.icon, cfg.key)"
          :shortcut="cfg.shortcut"
          :active="isRouteActive(cfg.route)"
          :collapsed="!sidebarOpen"
          :doctype="cfg.doctype"
        />

        <!-- type_1: parent itself links somewhere AND always shows children -->
        <div v-else-if="cfg.parent_type === 'type_1'" class="mb-0.5">
          <SidebarLink
            :route="cfg.route"
            :label="cfg.label"
            :icon="resolveIconName(cfg.icon, cfg.key)"
            :shortcut="cfg.shortcut"
            :active="isRouteActive(cfg.route) || groupHasActiveChild(cfg)"
            :collapsed="!sidebarOpen"
            :doctype="cfg.doctype"
          />
          <ul v-if="sidebarOpen && cfg.children?.length" class="mt-0.5">
            <li v-for="child in cfg.children" :key="child.key">
              <SidebarLink
                v-if="navItems[child.key]"
                :route="navItems[child.key].route"
                :label="navItems[child.key].label"
                :icon="resolveIconName(navItems[child.key].icon, child.key)"
                :shortcut="navItems[child.key].shortcut"
                :active="childActive(child.key)"
                :doctype="navItems[child.key].doctype"
                nested
              />
            </li>
          </ul>
        </div>

        <!-- type_2: collapsible group, one open at a time. Expand/collapse
             animates via a grid-template-rows transition (0fr -> 1fr) so it
             smoothly grows/shrinks to fit any number of children, instead of
             snapping open/closed. -->
        <div v-else-if="cfg.parent_type === 'type_2'" class="mb-0.5">
          <button
            type="button"
            class="flex h-[34px] w-full items-center gap-2.5 rounded-md text-p-sm transition-colors"
            :class="[
              sidebarOpen ? 'px-2.5' : 'justify-center px-0',
              parentHighlighted(cfg) ? 'text-app-primary' : 'text-app-text hover:bg-app-panel-2',
            ]"
            :style="parentHighlighted(cfg) ? { backgroundColor: 'var(--app-primary-tint)' } : {}"
            :aria-expanded="isExpanded(cfg)"
            :title="!sidebarOpen ? cfg.label : undefined"
            @click="toggleGroup(cfg)"
          >
            <span
              :class="[
                'lucide-' + resolveIconName(cfg.icon, cfg.key),
                'size-4',
                'shrink-0',
                parentHighlighted(cfg) ? 'text-app-primary' : 'text-app-text-muted',
              ]"
            />
            <template v-if="sidebarOpen">
              <span class="flex-1 truncate text-left">{{ cfg.label }}</span>
              <span
                class="lucide-chevron-down size-3.5 text-app-text-muted transition-transform duration-300"
                :class="{ 'rotate-180': isExpanded(cfg) }"
              />
            </template>
          </button>
          <div
            v-if="sidebarOpen"
            class="grid transition-[grid-template-rows] duration-300 ease-in-out"
            :style="{ gridTemplateRows: isExpanded(cfg) ? '1fr' : '0fr' }"
          >
            <ul
              class="relative ml-[19px] overflow-hidden border-l border-app-border pl-0"
            >
              <li v-for="child in cfg.children || []" :key="child.key" class="pt-0.5">
                <SidebarLink
                  v-if="navItems[child.key]"
                  :route="navItems[child.key].route"
                  :label="navItems[child.key].label"
                  :icon="resolveIconName(navItems[child.key].icon, child.key)"
                  :shortcut="navItems[child.key].shortcut"
                  :active="childActive(child.key)"
                  :doctype="navItems[child.key].doctype"
                  nested
                />
              </li>
            </ul>
          </div>
        </div>
      </template>

      <p
        v-if="loaded && !config.length && sidebarOpen"
        class="px-2.5 py-2 text-p-sm text-app-text-muted"
      >
        No modules available yet.
      </p>
      </ScrollArea>

      <ProfileMenu :collapsed="!sidebarOpen" />
    </div>
  </nav>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useSidebar } from '@/composables/layout/useSidebar'
import { resolveIconName } from '@/utils/layout/sidebarIcons'
import SidebarLink from './SidebarLink.vue'
import ScrollArea from '@/components/ui/ScrollArea.vue'
import ProfileMenu from './ProfileMenu.vue'

const {
  config,
  navItems,
  expandedKey,
  setExpandedKey,
  sidebarOpen: desktopSidebarOpen,
  setSidebarOpen,
  isMobile,
  mobileNavOpen,
  isRouteActive,
  loaded,
} = useSidebar()

// the drawer is never the collapsed icon rail
const sidebarOpen = computed(() => isMobile.value || desktopSidebarOpen.value)

function childActive(childKey) {
  const item = navItems.value[childKey]
  return item ? isRouteActive(item.route) : false
}

function groupHasActiveChild(cfg) {
  return (cfg.children || []).some((c) => childActive(c.key))
}

// Purely the user's own open/closed choice - an active child no longer
// forces this true, so collapsing a dropdown always sticks even while one
// of its links is the current route (see parentHighlighted for how that
// case still shows *where* you are once collapsed).
function isExpanded(cfg) {
  return expandedKey.value === cfg.key
}

// Collapsed but the active route lives inside it - highlight the parent
// button itself as the next best indicator once its children aren't shown.
function parentHighlighted(cfg) {
  return !isExpanded(cfg) && (isRouteActive(cfg.route) || groupHasActiveChild(cfg))
}

function toggleGroup(cfg) {
  // when the sidebar is collapsed to its icon rail, the group's children
  // aren't rendered at all, so a click can't just accordion-toggle - expand
  // the sidebar back to full width and open this group instead
  if (!sidebarOpen.value) {
    setSidebarOpen(true)
    setExpandedKey(cfg.key)
    return
  }
  setExpandedKey(expandedKey.value === cfg.key ? null : cfg.key)
}

// First-ever paint with nothing expanded yet (no persisted choice): open
// whichever group already contains the current route, so a deep link or
// refresh doesn't land with everything closed. Runs once the config loads,
// and never again - it must not override a collapse the user chose
// afterwards just because navigation kept the same active child.
let defaultedOpen = false
watch(
  config,
  (list) => {
    if (defaultedOpen || expandedKey.value || !list.length) return
    const activeGroup = list.find((cfg) => cfg.parent_type === 'type_2' && groupHasActiveChild(cfg))
    if (activeGroup) {
      defaultedOpen = true
      setExpandedKey(activeGroup.key)
    }
  },
  { immediate: true },
)
</script>

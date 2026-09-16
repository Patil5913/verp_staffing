<template>
  <nav
    class="flex h-full w-64 shrink-0 flex-col border-r border-app-border bg-app-panel"
  >
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
        />

        <!-- type_1: parent itself links somewhere AND always shows children -->
        <div v-else-if="cfg.parent_type === 'type_1'" class="mb-0.5">
          <SidebarLink
            :route="cfg.route"
            :label="cfg.label"
            :icon="resolveIconName(cfg.icon, cfg.key)"
            :shortcut="cfg.shortcut"
            :active="isRouteActive(cfg.route) || groupHasActiveChild(cfg)"
          />
          <ul v-if="cfg.children?.length" class="mt-0.5">
            <li v-for="child in cfg.children" :key="child.key">
              <SidebarLink
                v-if="navItems[child.key]"
                :route="navItems[child.key].route"
                :label="navItems[child.key].label"
                :icon="resolveIconName(navItems[child.key].icon, child.key)"
                :shortcut="navItems[child.key].shortcut"
                :active="childActive(child.key)"
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
            class="flex h-[34px] w-full items-center gap-2.5 rounded-md px-2.5 text-p-sm text-app-text transition-colors hover:bg-app-panel-2"
            :aria-expanded="isExpanded(cfg)"
            @click="toggleGroup(cfg)"
          >
            <span
              :class="[
                'lucide-' + resolveIconName(cfg.icon, cfg.key),
                'size-4',
                'text-app-text-muted',
              ]"
            />
            <span class="flex-1 truncate text-left">{{ cfg.label }}</span>
            <span
              class="lucide-chevron-down size-3.5 text-app-text-muted transition-transform duration-300"
              :class="{ 'rotate-180': isExpanded(cfg) }"
            />
          </button>
          <div
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
                  nested
                />
              </li>
            </ul>
          </div>
        </div>
      </template>

      <p
        v-if="loaded && !config.length"
        class="px-2.5 py-2 text-p-sm text-app-text-muted"
      >
        No modules available yet.
      </p>
    </ScrollArea>

    <ProfileMenu />
  </nav>
</template>

<script setup>
import { useSidebar } from '@/composables/useSidebar'
import { resolveIconName } from '@/utils/sidebarIcons'
import SidebarLink from './SidebarLink.vue'
import ScrollArea from './ScrollArea.vue'
import ProfileMenu from './ProfileMenu.vue'

const { config, navItems, expandedKey, setExpandedKey, isRouteActive, loaded } =
  useSidebar()

function childActive(childKey) {
  const item = navItems.value[childKey]
  return item ? isRouteActive(item.route) : false
}

function groupHasActiveChild(cfg) {
  return (cfg.children || []).some((c) => childActive(c.key))
}

function isExpanded(cfg) {
  return groupHasActiveChild(cfg) || expandedKey.value === cfg.key
}

function toggleGroup(cfg) {
  setExpandedKey(expandedKey.value === cfg.key ? null : cfg.key)
}
</script>

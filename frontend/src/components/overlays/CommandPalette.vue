<template>
  <Dialog v-model="open" :options="{ size: 'lg' }">
    <template #body>
      <div class="flex flex-col">
        <div
          class="flex items-center gap-2 border-b border-app-border px-4 py-3"
        >
          <span class="lucide-search size-4 shrink-0 text-app-text-muted" />
          <AppInput
            ref="inputRef"
            v-model="query"
            bare
            placeholder="Search modules, doctypes, reports..."
            class="h-8 flex-1 justify-center"
            @keydown.down.prevent="move(1)"
            @keydown.up.prevent="move(-1)"
            @keydown.enter.prevent="select(activeIndex)"
          />
          <kbd
            class="shrink-0 rounded border border-app-border px-1.5 py-0.5 text-2xs text-app-text-muted"
            >Esc</kbd
          >
        </div>
        <ScrollArea class="max-h-80">
          <ul class="py-2">
            <li
              v-if="!results.length"
              class="px-4 py-6 text-center text-p-sm text-app-text-muted"
            >
              No matches for "{{ query }}"
            </li>
            <li v-for="(item, index) in results" :key="item.key">
              <button
                type="button"
                class="flex w-full items-center gap-2.5 px-4 py-2 text-left text-p-base transition-colors"
                :class="
                  index === activeIndex
                    ? 'text-app-primary'
                    : 'text-app-text hover:bg-app-panel-2'
                "
                :style="
                  index === activeIndex
                    ? { backgroundColor: 'var(--app-primary-tint)' }
                    : {}
                "
                @mouseenter="activeIndex = index"
                @click="select(index)"
              >
                <span
                  :class="[
                    'lucide-' + resolveIconName(item.icon, item.key),
                    'size-4',
                    'shrink-0',
                    'text-app-text-muted',
                  ]"
                />
                <span class="min-w-0 flex-1 truncate">{{ item.label }}</span>
                <kbd
                  v-if="item.shortcut"
                  class="shrink-0 rounded border border-app-border px-1.5 py-0.5 text-2xs text-app-text-muted"
                >
                  {{ item.shortcut }}
                </kbd>
              </button>
            </li>
          </ul>
        </ScrollArea>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import AppInput from '@/components/ui/AppInput.vue'
import { computed, nextTick, ref, watch } from 'vue'
import { Dialog } from 'frappe-ui'
import router from '@/router'
import { useSidebar } from '@/composables/layout/useSidebar'
import { resolveIconName } from '@/utils/layout/sidebarIcons'
import ScrollArea from '../common/ScrollArea.vue'

const open = defineModel({ default: false })

const { flatList } = useSidebar()
const query = ref('')
const activeIndex = ref(0)
const inputRef = ref(null)

const results = computed(() => {
  const q = query.value.trim().toLowerCase()
  const items = !q
    ? flatList.value
    : flatList.value.filter((item) => item.label.toLowerCase().includes(q))
  return items.slice(0, 50)
})

watch(results, () => {
  activeIndex.value = 0
})

watch(open, (isOpen) => {
  if (isOpen) {
    query.value = ''
    activeIndex.value = 0
    nextTick(() => inputRef.value?.focus())
  }
})

function move(delta) {
  if (!results.value.length) return
  activeIndex.value =
    (activeIndex.value + delta + results.value.length) % results.value.length
}

function select(index) {
  const item = results.value[index]
  if (!item?.route) return
  open.value = false
  if (item.route.startsWith('/verp')) {
    // router's path space excludes the '/verp' history base (see
    // SidebarLink.vue) — pushing the full route would double it up.
    router.push(item.route.replace(/^\/verp/, '') || '/')
  } else {
    window.location.href = item.route
  }
}
</script>

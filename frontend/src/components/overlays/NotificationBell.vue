<template>
  <Popover placement="bottom-end" :popover-class="'w-[min(24rem,calc(100vw-1rem))]'">
    <template #target="{ togglePopover, isOpen }">
      <button
        type="button"
        class="relative flex h-10 w-10 items-center md:h-8 md:w-8 justify-center rounded-full text-app-text-muted transition-colors hover:bg-app-panel-2 hover:text-app-text"
        aria-label="Notifications"
        @click="
          () => {
            if (!isOpen) load()
            togglePopover()
          }
        "
      >
        <span class="lucide-bell size-4.5" />
        <span
          v-if="unreadCount"
          class="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-red-500"
        />
      </button>
    </template>

    <template #body="{ close }">
      <div
        class="flex max-h-[28rem] flex-col rounded-lg border border-app-border bg-app-panel shadow-xl"
      >
        <div
          class="flex items-center justify-between border-b border-app-border px-4 py-3"
        >
          <span class="text-p-base font-medium text-app-text">
            Notifications
          </span>
          <button
            v-if="unreadCount"
            type="button"
            class="text-p-sm text-app-primary hover:underline"
            @click="markAllAsRead"
          >
            Mark all as read
          </button>
        </div>

        <ScrollArea class="flex-1">
          <p
            v-if="loading && !notifications.length"
            class="px-4 py-8 text-center text-p-sm text-app-text-muted"
          >
            Loading...
          </p>
          <p
            v-else-if="!notifications.length"
            class="px-4 py-8 text-center text-p-sm text-app-text-muted"
          >
            No notifications yet.
          </p>
          <ul v-else class="divide-y divide-app-border">
            <li v-for="item in notifications" :key="item.name">
              <a
                href="#"
                @click.prevent="onItemClick(item, close)"
                class="flex gap-2.5 px-4 py-3 text-left transition-colors hover:bg-app-panel-2"
              >
                <span
                  class="mt-1.5 size-1.5 shrink-0 rounded-full"
                  :class="item.read ? 'bg-transparent' : 'bg-app-primary'"
                />
                <span class="min-w-0 flex-1">
                  <span
                    class="block text-p-sm text-app-text"
                    v-html="sanitize(item.subject)"
                  />
                  <span class="mt-0.5 block text-2xs text-app-text-muted">
                    {{ fromNow(item.creation) }}
                  </span>
                </span>
              </a>
            </li>
          </ul>
        </ScrollArea>

        <router-link
          to="/notifications"
          class="block border-t border-app-border px-4 py-2.5 text-center text-p-sm text-app-primary hover:bg-app-panel-2"
          @click="close()"
        >
          See all Activity
        </router-link>
      </div>
    </template>
  </Popover>
</template>

<script setup>
import DOMPurify from 'dompurify'
import { dayjs, Popover } from 'frappe-ui'
import { useRouter } from 'vue-router'
import { useNotifications } from '@/composables/layout/useNotifications'
import ScrollArea from '@/components/ui/ScrollArea.vue'

const router = useRouter()
const { notifications, loading, unreadCount, load, markAllAsRead, markAsRead, resolveRoute } =
  useNotifications()

function fromNow(dateString) {
  return dateString ? dayjs(dateString).fromNow() : ''
}

// notification subjects can embed simple formatting (e.g. "<b>X</b>
// commented..."), but are still attacker-influenced content (mentions,
// comments, etc.) - sanitize before v-html, same allowlist frappe-ui's own
// toast uses.
function sanitize(html) {
  return DOMPurify.sanitize(html || '', {
    ALLOWED_TAGS: ['a', 'em', 'strong', 'i', 'b', 'u'],
  })
}

async function onItemClick(item, close) {
  markAsRead(item.name)
  close()
  router.push(await resolveRoute(item))
}
</script>

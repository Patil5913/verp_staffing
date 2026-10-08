<template>
  <div class="flex h-full flex-col bg-app-bg">
    <SubNavbar title="Notifications">
      <template #left>
        <AppTabs v-model="tab" :tabs="TABS" class="!border-0" />
      </template>
      <template #right>
        <AppButton variant="outline" size="sm" icon="check-check" :disabled="!unread" @click="readAll">Mark all as read</AppButton>
        <AppButton variant="ghost" icon="refresh-cw" tooltip="Refresh" :loading="loading" @click="load" />
      </template>
    </SubNavbar>

    <div class="min-h-0 flex-1 overflow-y-auto px-3 md:px-6 py-4">
      <div class="mx-auto flex max-w-3xl flex-col gap-3">
        <div v-if="loading && !items.length" class="flex flex-col gap-3"><AppSkeleton v-for="i in 4" :key="i" variant="block" height="4rem" /></div>
        <StateBanner
          v-else-if="!visible.length"
          icon="bell"
          :title="tab === 'Unread' ? 'You\'re all caught up' : 'No notifications yet'"
          :description="tab === 'Unread' ? 'Nothing unread.' : 'Mentions, assignments and other updates will show up here.'"
        />
        <ul v-else class="divide-y divide-app-border overflow-hidden rounded-xl border border-app-border bg-app-panel">
          <li v-for="n in visible" :key="n.name">
            <a
              href="#"
              class="flex gap-3 px-4 py-3.5 transition-colors hover:bg-app-panel-2"
              @click.prevent="open(n)"
            >
              <span class="mt-2 size-2 shrink-0 rounded-full" :class="n.read ? 'bg-transparent' : 'bg-app-primary'" />
              <span class="min-w-0 flex-1">
                <span class="block text-p-sm text-app-text" v-html="sanitize(n.subject)" />
                <span class="mt-1 flex items-center gap-2 text-p-xs text-app-text-muted">
                  <span>{{ fromNow(n.creation) }}</span>
                  <AppBadge v-if="n.document_type" :label="n.document_type" />
                </span>
              </span>
              <AppButton
                v-if="!n.read"
                variant="ghost"
                size="sm"
                icon="check"
                tooltip="Mark as read"
                class="shrink-0 self-center"
                @click.stop.prevent="read(n)"
              />
            </a>
          </li>
        </ul>

        <div v-if="canLoadMore" class="flex justify-center pt-1">
          <AppButton variant="outline" size="sm" :loading="loading" @click="more">Load more</AppButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// "See all Activity" from the notification bell: the full Notification Log
// for this user, in the app instead of the classic desk list.
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import DOMPurify from 'dompurify'
import { call, dayjs } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import SubNavbar from '@/components/common/SubNavbar.vue'
import AppBadge from '@/components/ui/AppBadge.vue'
import AppSkeleton from '@/components/ui/AppSkeleton.vue'
import AppTabs from '@/components/ui/AppTabs.vue'
import { useNotifications } from '@/composables/layout/useNotifications'

const router = useRouter()
const bell = useNotifications()

const TABS = ['All', 'Unread']
const PAGE = 50
const tab = ref('All')
const items = ref([])
const limit = ref(PAGE)
const loading = ref(false)
const canLoadMore = ref(false)

const unread = computed(() => items.value.filter((n) => !n.read).length)
const visible = computed(() => (tab.value === 'Unread' ? items.value.filter((n) => !n.read) : items.value))

const fromNow = (d) => (d ? dayjs(d).fromNow() : '')
const sanitize = (html) => DOMPurify.sanitize(html || '', { ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'span'], ALLOWED_ATTR: ['href', 'class'] })

async function load() {
  loading.value = true
  try {
    const res = await call('verp_staffing.utils.notification_read.get_logs', { limit: limit.value })
    items.value = res?.notification_logs || []
    canLoadMore.value = items.value.length >= limit.value
  } finally {
    loading.value = false
  }
}
function more() {
  limit.value += PAGE
  load()
}

async function read(n) {
  n.read = 1
  await bell.markAsRead(n.name)
  await load()
}
async function readAll() {
  items.value.forEach((n) => (n.read = 1))
  await bell.markAllAsRead()
  await load()
}
async function open(n) {
  if (!n.read) read(n)
  router.push(await bell.resolveRoute(n))
}

onMounted(load)
</script>

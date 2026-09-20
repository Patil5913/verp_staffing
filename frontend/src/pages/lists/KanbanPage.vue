<template>
  <div class="flex h-full flex-col bg-app-bg">
    <SubNavbar :title="doctype">
      <template #left><ViewSwitcher :doctype="doctype" current="kanban" /></template>
      <AppSearchInput v-model="search" class="w-full" placeholder="Search cards">
      </AppSearchInput>
      <template #right>
        <AppButton variant="ghost" icon="refresh-cw" tooltip="Refresh" @click="load" />
      </template>
    </SubNavbar>

    <div class="flex min-h-0 flex-1 flex-col gap-3 px-3 md:px-6 py-3">
      <StateBanner v-if="!config" icon="columns-3" title="No board for this doctype" />
      <StateBanner v-else-if="cardsResource.hasError" icon="alert-triangle" title="Couldn't load the board" :description="cardsResource.errorMessage" />
      <div v-else-if="cardsResource.isLoading && !cardsResource.resource.data" class="flex justify-center py-16">
        <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
      </div>
      <KanbanBoard
        v-else-if="config"
        :columns="config.columns"
        :cards="filtered"
        :status-field="config.statusField"
        @open="(card) => router.push(`/${encodeURIComponent(doctype)}/${encodeURIComponent(card.name)}`)"
        @move="onMove"
      >
        <template #card="{ card }">
          <p class="truncate text-p-sm font-medium text-app-text">{{ card[config.title] || card.name }}</p>
          <p v-if="card[config.subtitle]" class="truncate text-p-xs text-app-text-muted">{{ card[config.subtitle] }}</p>
          <p v-if="card.customer" class="mt-1 truncate text-p-xs text-app-text-muted">{{ card.customer }}</p>
          <ul v-if="rounds[card.name]?.length" class="mt-2 flex flex-col gap-1 border-t border-app-border pt-2">
            <li v-for="(r, i) in rounds[card.name].slice(-3)" :key="i" class="flex items-center justify-between gap-2 text-p-xs">
              <span class="truncate text-app-text-muted">Round {{ r.round }} · {{ formatDate(r.date_of_interview) || 'no date' }}</span>
              <DocStatusBadge :status="r.status" />
            </li>
            <li v-if="rounds[card.name].length > 3" class="text-p-xs text-app-text-muted">+{{ rounds[card.name].length - 3 }} earlier</li>
          </ul>
        </template>
      </KanbanBoard>
    </div>

    <Dialog v-model="reason.open" :options="{ title: `Mark as ${reason.to}`, size: 'md' }">
      <template #body-content>
        <div class="flex flex-col gap-4">
          <AppInput type="select" label="Cancelled By" v-model="reason.by" :options="['', 'Company', 'Candidate']" required />
          <AppInput type="textarea" label="Reason" v-model="reason.text" required />
        </div>
      </template>
      <template #actions>
        <AppButton :disabled="!reason.by || !reason.text.trim()" :loading="moving" @click="submitReason">Confirm</AppButton>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import AppSearchInput from '@/components/ui/AppSearchInput.vue'
import AppInput from '@/components/ui/AppInput.vue'
// Kanban view of a doctype (today: Interview, ported from interview_list.js).
// Loads every card, groups them by status column, and turns a drag into the
// doctype's own move method — optimistic, rolled back if the server refuses
// (e.g. a round that's already Completed can't be moved again).
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call, Dialog, FeatherIcon, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import SubNavbar from '@/components/common/SubNavbar.vue'
import ViewSwitcher from '@/components/common/ViewSwitcher.vue'
import KanbanBoard from '@/components/list/KanbanBoard.vue'
import { KANBAN } from '@/configs/detail/listOptions'
import { useResource } from '@/composables/list/useResource'
import { formatDate } from '@/utils/list/formatValue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

const route = useRoute()
const router = useRouter()
const doctype = computed(() => route.params.doctype)
const config = computed(() => KANBAN[doctype.value])
const search = ref('')

const cards = ref([])
const rounds = ref({})

const cardsResource = useResource({
  url: 'frappe.client.get_list',
  makeParams: () => ({
    doctype: doctype.value,
    fields: ['name', config.value.statusField, ...config.value.cardFields],
    order_by: 'modified desc',
    limit_page_length: 500,
  }),
  onSuccess(data) {
    cards.value = data || []
    loadRounds()
  },
})

async function loadRounds() {
  if (!config.value?.summaryMethod || !cards.value.length) return
  try {
    rounds.value = await call(config.value.summaryMethod, { names: JSON.stringify(cards.value.map((c) => c.name)) })
  } catch {
    rounds.value = {}
  }
}

function load() {
  if (config.value) cardsResource.resource.submit()
}
watch(doctype, load, { immediate: true })

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return cards.value
  return cards.value.filter((c) => Object.values(c).some((v) => String(v ?? '').toLowerCase().includes(q)))
})

const moving = ref(false)
const reason = reactive({ open: false, card: null, to: '', by: '', text: '' })

async function moveCard(card, to, extra = {}) {
  const field = config.value.statusField
  const from = card[field]
  card[field] = to // optimistic
  moving.value = true
  try {
    await call(config.value.moveMethod, { [config.value.moveArg]: card.name, status: to, ...extra })
    notify.success(`${card.name} moved to ${to}.`)
    loadRounds()
    return true
  } catch (error) {
    card[field] = from
    notify.error(normalizeError(error).message)
    return false
  } finally {
    moving.value = false
  }
}

function onMove({ card, to }) {
  if (config.value.reasonStatuses?.includes(to)) {
    Object.assign(reason, { open: true, card, to, by: '', text: '' })
    return
  }
  moveCard(card, to)
}

async function submitReason() {
  const ok = await moveCard(reason.card, reason.to, { cancelled_by: reason.by, reason_of_cancel: reason.text.trim() })
  if (ok) reason.open = false
}
</script>

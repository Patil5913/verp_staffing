<template>
  <div class="flex flex-col gap-2">
    <div v-if="data?.suspended || data?.muted" class="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-500/10 px-3 py-2 text-p-sm text-amber-800">
      <span class="lucide-triangle-alert mt-0.5 size-4 shrink-0" />
      <span v-if="data.muted">Automatic sending is switched off in the site configuration, so queued mail only goes out with <strong>Send now</strong>.</span>
      <span v-else>Sending is suspended. Queued mail waits until you resume it - or use <strong>Send now</strong> on a message.</span>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <button
        v-for="s in STATUSES"
        :key="s.key"
        type="button"
        class="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-p-sm transition-colors"
        :class="active === s.key ? 'border-app-primary bg-app-primary-tint text-app-primary' : 'border-app-border bg-app-panel text-app-text hover:bg-app-panel-2'"
        @click="pick(s.key)"
      >
        <span class="size-2 rounded-full" :class="s.dot" />
        {{ s.key }}
        <span class="font-semibold tabular-nums">{{ data?.counts?.[s.key] ?? '–' }}</span>
      </button>

      <span class="flex-1" />

      <AppButton v-if="data" variant="outline" size="sm" :icon="data.suspended ? 'play' : 'pause'" :loading="toggling" @click="toggle">
        {{ data.suspended ? 'Resume sending' : 'Suspend sending' }}
      </AppButton>
    </div>
  </div>
</template>

<script setup>
// The header of the Email Queue list: how much is in each state (click one to
// filter the list to it) and the switch that suspends or resumes sending.
import { onMounted, ref } from 'vue'
import { call } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

defineProps({ doctype: { type: String, default: '' } })
const emit = defineEmits(['filter'])

const API = 'verp_staffing.utils.email_queue'
const STATUSES = [
  { key: 'Not Sent', dot: 'bg-slate-400' },
  { key: 'Sending', dot: 'bg-blue-500' },
  { key: 'Sent', dot: 'bg-green-500' },
  { key: 'Partially Sent', dot: 'bg-amber-500' },
  { key: 'Error', dot: 'bg-red-500' },
  { key: 'Expired', dot: 'bg-orange-500' },
]

const data = ref(null)
const active = ref('')
const toggling = ref(false)

async function load() {
  try {
    data.value = await call(`${API}.get_queue_overview`)
  } catch {
    data.value = null
  }
}
onMounted(load)
defineExpose({ reload: load })

function pick(status) {
  active.value = active.value === status ? '' : status
  emit('filter', active.value ? `status=${active.value}` : '')
}

async function toggle() {
  toggling.value = true
  try {
    data.value = await call(`${API}.set_sending`, { enable: data.value.suspended ? 1 : 0 })
    notify.success(data.value.suspended ? 'Sending suspended' : 'Sending resumed')
  } catch (e) {
    notify.error(normalizeError(e).message)
  } finally {
    toggling.value = false
  }
}
</script>

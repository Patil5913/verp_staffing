<template>
  <div class="flex flex-col gap-6">
    <SectionCard title="Signers" :subtitle="`${signers.length} ${signers.length === 1 ? 'recipient' : 'recipients'}`">
      <p v-if="!signers.length" class="py-4 text-center text-p-sm text-app-text-muted">No recipients yet — place fields on the Document tab.</p>
      <div v-else class="overflow-x-auto rounded-lg border border-app-border">
        <table class="w-full text-left text-p-sm">
          <thead class="bg-app-panel-2 text-p-xs text-app-text-muted">
            <tr>
              <th class="px-3 py-2 font-medium">Recipient</th>
              <th class="px-3 py-2 font-medium">Fields</th>
              <th class="px-3 py-2 font-medium">Signed</th>
              <th class="px-3 py-2 font-medium">Emailed</th>
              <th class="px-3 py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in signers" :key="s.email" class="border-t border-app-border">
              <td class="px-3 py-2 text-app-text">{{ s.email }}</td>
              <td class="px-3 py-2">{{ s.total }}</td>
              <td class="px-3 py-2">{{ s.signed }} / {{ s.total }}</td>
              <td class="px-3 py-2 text-app-text-muted">{{ s.emailed || '—' }}</td>
              <td class="px-3 py-2"><DocStatusBadge :status="s.signed === s.total ? 'Signed' : s.emailed ? 'Sent' : 'Pending'" /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </SectionCard>

    <SectionCard title="Audit Log" subtitle="Every visit and signing event, with device details.">
      <p v-if="!log.length" class="py-4 text-center text-p-sm text-app-text-muted">No activity recorded yet.</p>
      <ol v-else class="flex flex-col gap-2">
        <li v-for="(e, i) in log" :key="i" class="rounded-lg border border-app-border bg-app-panel-2/40 px-3 py-2 text-p-sm">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <span class="font-medium text-app-text">{{ e.event_type || 'Activity' }} <span class="font-normal text-app-text-muted">· {{ e.email }}</span></span>
            <span class="text-p-xs text-app-text-muted">{{ e.visited_at }}</span>
          </div>
          <p class="text-p-xs text-app-text-muted">{{ [e.browser, e.os, e.device, e.ip_address].filter(Boolean).join(' · ') }}</p>
          <p v-if="e.event_details" class="mt-1 text-p-xs text-app-text">{{ e.event_details }}</p>
        </li>
      </ol>
    </SectionCard>
  </div>
</template>

<script setup>
// Read-only progress view for a sent E Sign document: who's signed how many
// of their fields, plus the audit trail the signing page records.
import { computed } from 'vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import SectionCard from '@/components/common/SectionCard.vue'

defineOptions({ inheritAttrs: false })
const props = defineProps({ detail: { type: Object, required: true } })

const fields = computed(() => props.detail.hiddenTables.signature_fields || [])
const log = computed(() => [...(props.detail.hiddenTables.activity || [])].reverse())

const signers = computed(() => {
  const map = new Map()
  for (const f of fields.value) {
    if (!f.signer_email) continue
    const s = map.get(f.signer_email) || { email: f.signer_email, total: 0, signed: 0, emailed: '' }
    s.total += 1
    if (Number(f.signed)) s.signed += 1
    s.emailed = s.emailed || f.email_sent_on || ''
    map.set(f.signer_email, s)
  }
  return [...map.values()]
})
</script>

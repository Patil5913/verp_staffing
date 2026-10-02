<template>
  <div v-if="pendingCount" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="fb-title">
    <div class="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-app-border bg-app-panel shadow-xl">
      <div class="border-b border-app-border bg-app-panel-2 px-6 py-4">
        <h2 id="fb-title" class="text-lg font-semibold text-app-text">Pending feedback</h2>
        <p class="mt-1 text-p-sm text-app-text-muted">Please share your feedback below to continue to your portal.</p>
      </div>

      <div class="flex flex-col gap-4 overflow-y-auto bg-app-bg px-6 py-5">
        <SectionCard v-for="r in data.feedback_rounds" :key="r.round_name" :title="r.title">
          <dl class="mb-3 grid grid-cols-2 gap-x-6 gap-y-2 text-p-sm sm:grid-cols-3">
            <div v-for="[label, value] in roundFacts(r)" :key="label">
              <dt class="text-2xs uppercase tracking-wide text-app-text-muted">{{ label }}</dt>
              <dd class="font-medium text-app-text">{{ value || '-' }}</dd>
            </div>
          </dl>
          <AppTextarea v-model="roundText[r.round_name]" label="Your feedback" placeholder="Write your feedback…" :rows="3" />
        </SectionCard>
        <div v-if="data.feedback_rounds?.length" class="flex justify-end">
          <AppButton icon="send" :loading="savingRounds" :disabled="!allRoundsFilled" @click="submitRounds">Submit interview feedback</AppButton>
        </div>

        <h3 v-if="data.pending_feedback_items?.length" class="text-p-sm font-semibold text-app-text">Other pending feedback</h3>
        <SectionCard v-for="item in data.pending_feedback_items" :key="itemKey(item)" :title="item.title" :subtitle="item.doctype">
          <dl class="mb-3 grid grid-cols-2 gap-x-6 gap-y-2 text-p-sm sm:grid-cols-3">
            <div v-for="[label, value] in item.context_lines" :key="label">
              <dt class="text-2xs uppercase tracking-wide text-app-text-muted">{{ label }}</dt>
              <dd class="font-medium text-app-text">{{ value || '-' }}</dd>
            </div>
          </dl>
          <AppTextarea v-model="itemText[itemKey(item)]" label="Your feedback" placeholder="Write your feedback…" :rows="3" />
          <div class="mt-3 flex justify-end">
            <AppButton :loading="savingItem === itemKey(item)" :disabled="!(itemText[itemKey(item)] || '').trim()" @click="submitItem(item)">Submit</AppButton>
          </div>
        </SectionCard>
      </div>
    </div>
  </div>
</template>

<script setup>
// Interview rounds and sessions that have happened but have no feedback yet
// block the portal until they are answered, as the old portal page did.
import { computed, reactive, ref } from 'vue'
import { call } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppTextarea from '@/components/ui/AppTextarea.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import { usePortal } from '@/composables/portal/usePortal'
import { notify } from '@/utils/common/notify'

const { data, pendingCount } = usePortal()
const roundText = reactive({})
const itemText = reactive({})
const savingRounds = ref(false)
const savingItem = ref('')

const itemKey = (i) => `${i.doctype}::${i.docname}::${i.session_row_name || ''}`
const roundFacts = (r) => [['Company', r.company], ['Role', r.role], ['Round', r.round], ['Type', r.type], ['Date', r.date], ['Time', r.time]]
const allRoundsFilled = computed(() => (data.value?.feedback_rounds || []).every((r) => (roundText[r.round_name] || '').trim()))
const errorText = (e) => e?.messages?.[0] || e?.message || 'Something went wrong'

async function submitRounds() {
  savingRounds.value = true
  try {
    const list = data.value.feedback_rounds.map((r) => ({ round_name: r.round_name, feedback: roundText[r.round_name].trim() }))
    await call('verp_staffing.www.customer.save_interview_feedback', { feedback_data: JSON.stringify(list) })
    data.value = { ...data.value, feedback_rounds: [] }
    notify.success('Thanks, your feedback was sent.')
  } catch (e) {
    notify.error(errorText(e))
  } finally {
    savingRounds.value = false
  }
}

async function submitItem(item) {
  savingItem.value = itemKey(item)
  try {
    const args = { doctype: item.doctype, docname: item.docname, feedback: itemText[itemKey(item)].trim() }
    if (item.session_row_name) args.session_row_name = item.session_row_name
    await call('verp_staffing.www.customer.save_customer_feedback', args)
    data.value = { ...data.value, pending_feedback_items: data.value.pending_feedback_items.filter((i) => itemKey(i) !== itemKey(item)) }
    notify.success('Thanks, your feedback was sent.')
  } catch (e) {
    notify.error(errorText(e))
  } finally {
    savingItem.value = ''
  }
}
</script>

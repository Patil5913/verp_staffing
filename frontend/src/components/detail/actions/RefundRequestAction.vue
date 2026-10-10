<template>
  <AppButton v-if="visible" variant="outline" icon="rotate-ccw" @click="openDialog">Refund</AppButton>

  <Dialog v-model="open" :options="{ title: 'Request Refund', size: 'xl' }">
    <template #body-content>
      <div v-if="preview.isLoading && !info" class="flex justify-center py-8">
        <LoadingIndicator class="h-5 w-5 text-app-text-muted" />
      </div>
      <StateBanner v-else-if="loadError" icon="alert-triangle" title="Nothing to refund" :description="loadError" />

      <div v-else-if="info" class="flex flex-col gap-5">
        <!-- what the candidate has paid -->
        <div class="rounded-lg border border-app-border">
          <p class="border-b border-app-border bg-app-panel-2 px-3 py-2 text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">
            Payments received (newest first)
          </p>
          <table class="w-full text-p-sm">
            <tbody>
              <tr v-for="inv in info.invoices" :key="inv.sales_invoice" class="border-t border-app-border first:border-t-0">
                <td class="px-3 py-1.5 text-app-text">{{ inv.sales_invoice }}</td>
                <td class="px-3 py-1.5 text-app-text-muted">{{ inv.receipt }}</td>
                <td class="px-3 py-1.5 text-right tabular-nums">{{ money(inv.paid) }}</td>
                <td class="px-3 py-1.5 text-right text-p-xs text-app-text-muted">can refund {{ money(inv.available) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="grid gap-4 sm:grid-cols-2">
          <AppInput label="Refund amount" type="number" v-model="amount" required :description="`Up to ${money(info.refundable_total)}`" />
          <AppInput label="Transaction fee recovered from the candidate" type="number" v-model="fee" :description="feeHint" />
        </div>

        <!-- the number the candidate will actually receive -->
        <div class="rounded-lg bg-app-panel-2 p-4 text-p-sm">
          <div class="flex justify-between"><span class="text-app-text-muted">Refund amount</span><span class="tabular-nums">{{ money(amountNum) }}</span></div>
          <div class="flex justify-between"><span class="text-app-text-muted">Less: transaction fee recovered</span><span class="tabular-nums">- {{ money(feeNum) }}</span></div>
          <div class="mt-1 flex justify-between border-t border-app-border pt-2 text-p-base font-semibold">
            <span>Amount paid to the candidate</span><span class="tabular-nums">{{ money(netNum) }}</span>
          </div>
          <p v-if="info.paid_from" class="mt-1 text-p-xs text-app-text-muted">
            Paid from {{ info.paid_from }} by default. The accountant can choose another bank account when verifying.
          </p>
        </div>

        <div class="grid gap-4 sm:grid-cols-2">
          <AppInput label="Account holder name" v-model="bank.account_holder_name" required />
          <AppInput label="Bank name" v-model="bank.bank_name" required />
          <AppInput label="Account number" v-model="bank.account_number" required />
          <AppInput label="IFSC / SWIFT / Routing code" v-model="bank.routing_code" />
          <AppInput label="Branch" v-model="bank.branch" />
        </div>
        <AppInput type="textarea" label="Other bank details (optional)" v-model="bank.bank_notes" />
        <AppInput type="textarea" label="Reason for the refund" v-model="reason" required />
      </div>
    </template>
    <template #actions>
      <AppButton v-if="info" icon="send" :loading="creating.isLoading" :disabled="!canSubmit" @click="submit">
        Send for verification
      </AppButton>
    </template>
  </Dialog>
</template>

<script setup>
// CR's "Refund": the CR employee enters the amount and the candidate's bank details; the fee the company absorbed
// on the way in is recovered from the candidate, and the form shows what will actually be paid out. Nothing is
// booked until an accountant verifies the payment entry this creates.
import { computed, nextTick, ref, watch } from 'vue'
import { Dialog, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  name: { type: String, required: true },
  historyField: { type: String, default: 'cr_history' },
  openStatus: { type: [String, Array], default: () => ['Dispute Pending', 'Refund Rejected'] },
})

const rows = computed(() => props.detail.values[props.historyField] || [])
const visible = computed(
  () => !props.detail.isNew.value && rows.value.length && [].concat(props.openStatus).includes(rows.value[rows.value.length - 1].status),
)

const open = ref(false)
const info = ref(null)
const loadError = ref('')
const amount = ref('')
const fee = ref('')
const feeTouched = ref(false)
const suggestedFee = ref(null)
let settingFee = false
const reason = ref('')
const bank = ref({})

const preview = useResource({ url: 'verp_staffing.cr.refund.get_refund_preview', notifyOnError: false })
const creating = useResource({ url: 'verp_staffing.cr.refund.create_refund_request', notifyOnError: false })

const amountNum = computed(() => Number(amount.value) || 0)
const feeNum = computed(() => Number(fee.value) || 0)
const netNum = computed(() => Math.max(0, amountNum.value - feeNum.value))
const money = (v) => `${Number(v || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${info.value?.currency || ''}`.trim()
const feeHint = computed(() =>
  suggestedFee.value != null ? `Suggested ${money(suggestedFee.value)} - the fee absorbed on these payments. You can change it.` : 'Filled in from the payments being refunded once you enter an amount.',
)

const canSubmit = computed(
  () =>
    amountNum.value > 0 &&
    amountNum.value <= (info.value?.refundable_total || 0) &&
    netNum.value > 0 &&
    reason.value.trim() &&
    bank.value.account_holder_name?.trim() &&
    bank.value.bank_name?.trim() &&
    bank.value.account_number?.trim(),
)

async function openDialog() {
  open.value = true
  info.value = null
  loadError.value = ''
  settingFee = true
  amount.value = fee.value = reason.value = ''
  await nextTick()
  settingFee = false
  feeTouched.value = false
  suggestedFee.value = null
  bank.value = {}
  try {
    info.value = await preview.resource.submit({ cr: props.name })
  } catch (error) {
    loadError.value = normalizeError(error).message
  }
}

// Re-price the fee as the amount changes (until the CR employee types their own).
let timer
watch(amount, (value) => {
  clearTimeout(timer)
  if (!info.value || !(Number(value) > 0)) return
  timer = setTimeout(async () => {
    try {
      const res = await preview.resource.submit({ cr: props.name, amount: value, fee: feeTouched.value ? fee.value : undefined })
      suggestedFee.value = res.fee_default
      if (!feeTouched.value) {
        settingFee = true
        fee.value = res.fee
        await nextTick()
        settingFee = false
      }
    } catch {
      /* the amount may be over the limit - the form already says so */
    }
  }, 300)
})
watch(fee, () => {
  if (!settingFee) feeTouched.value = true
})

async function submit() {
  try {
    const res = await creating.resource.submit({
      cr: props.name,
      amount: amountNum.value,
      fee: feeNum.value,
      reason: reason.value.trim(),
      ...bank.value,
    })
    notify.success(`Refund sent for verification: ${money(res.net_payout)} to the candidate.`)
    open.value = false
    props.detail.refresh()
  } catch (error) {
    notify.error(normalizeError(error).message)
  }
}
</script>

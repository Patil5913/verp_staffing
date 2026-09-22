<template>
  <SectionCard title="Payment Terms" :subtitle="subtitle">
    <div v-if="terms.length" class="overflow-x-auto rounded-lg border border-app-border">
      <table class="w-full text-left text-p-sm">
        <thead class="bg-app-panel-2 text-p-xs text-app-text-muted">
          <tr>
            <th class="px-3 py-2 font-medium">#</th>
            <th class="px-3 py-2 font-medium">Condition</th>
            <th class="px-3 py-2 font-medium">Due</th>
            <th class="px-3 py-2 text-right font-medium">Amount</th>
            <th class="px-3 py-2 font-medium">Status</th>
            <th class="px-3 py-2 font-medium">Payment Entry</th>
            <th class="px-3 py-2" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="(term, i) in terms" :key="term.name" class="border-t border-app-border align-top">
            <td class="px-3 py-2">{{ i + 1 }}</td>
            <td class="px-3 py-2">
              {{ term.payment_condition || '—' }}
              <span v-if="term.payment_condition !== 'Not Applied' && term.counter" class="text-app-text-muted">
                · {{ term.counter }} {{ term.payment_condition === 'Number of Interviews' ? 'interviews' : 'days' }}
              </span>
              <p v-if="term.payment_condition === 'Number of Interviews'" class="text-p-xs text-app-text-muted">
                {{ term.current_interview_count || 0 }} of {{ term.counter }} done
              </p>
            </td>
            <td class="px-3 py-2">{{ formatDate(term.due_date) || '—' }}</td>
            <td class="px-3 py-2 text-right tabular-nums">{{ formatFieldValue(term.amount, { fieldtype: 'Currency' }) }}</td>
            <td class="px-3 py-2"><DocStatusBadge :status="term.payment_status || 'Unpaid'" /></td>
            <td class="px-3 py-2">
              <router-link v-if="term.payment_entry" :to="`/Payment%20Entry/${encodeURIComponent(term.payment_entry)}`" class="text-app-primary hover:underline">
                {{ term.payment_entry }}
              </router-link>
              <span v-else class="text-app-text-muted">—</span>
            </td>
            <td class="px-3 py-2 text-right">
              <AppButton
                v-if="canAct(term)"
                size="sm"
                :variant="term.payment_status === 'Rejected' ? 'outline' : 'primary'"
                @click="openDialog(term)"
              >
                {{ term.payment_status === 'Rejected' ? 'Re-request' : 'Mark as Paid' }}
              </AppButton>
              <span v-else-if="term.payment_status === 'Pending Verification'" class="text-p-xs text-app-text-muted">Awaiting verification</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="rounded-lg border border-dashed border-app-border py-6 text-center text-p-sm text-app-text-muted">
      No payment terms on this order.
    </p>

    <Dialog v-model="open" :options="{ title: rerequest ? 'Re-request Verification' : 'Mark as Paid', size: 'lg' }">
      <template #body-content>
        <div v-if="active" class="flex flex-col gap-4">
          <div class="rounded-lg bg-app-primary-tint px-4 py-3 text-p-sm text-app-text">
            <p><b>Amount:</b> {{ formatFieldValue(active.received_amount || active.amount, { fieldtype: 'Currency' }) }} {{ active.currency || detail.values.currency }}</p>
            <p v-if="active.sales_invoice"><b>Invoice:</b> {{ active.sales_invoice }}</p>
            <p v-else class="text-app-text-muted">An invoice will be created for the company selected below.</p>
          </div>

          <template v-if="!active.sales_invoice">
            <AppLinkField label="Company" doctype="Company" v-model="form.company" hide-add-new />
            <AppInput v-if="foreign" type="number" :label="`Exchange Rate (1 ${detail.values.currency} = ?)`" v-model="form.conversion_rate" required />
            <p v-if="form.company" class="text-p-sm text-app-text-muted">
              Received: <b>{{ formatFieldValue(received, { fieldtype: 'Currency' }) }} {{ targetCurrency }}</b>
            </p>
          </template>

          <AppInput label="Payer's Account Name" v-model="form.payer_account_name" required />
          <AppInput label="Reference Id / Transaction No / Cheque No" v-model="form.reference_no" required />
          <AppInput type="textarea" label="Remarks (amount paid in which account)" v-model="form.remarks" required />
          <AppInput type="date" label="Reference Date" v-model="form.reference_date" required />
        </div>
      </template>
      <template #actions>
        <AppButton :loading="submitting" :disabled="!valid" @click="submit">
          {{ rerequest ? 'Re-request' : 'Submit for Verification' }}
        </AppButton>
      </template>
    </Dialog>
  </SectionCard>
</template>

<script setup>
import AppInput from '@/components/ui/AppInput.vue'
// The Sales Order's payment schedule with its "Mark as Paid" / "Re-request"
// flow, ported from sales_order.js (render_payment_term_actions /
// open_mark_as_paid_dialog): the dialog collects who paid and the reference,
// picks the receiving company (converting currency if it differs from the
// order's), and create_payment_entry_from_term raises a Payment Entry that
// lands in the Payment Verification queue.
import { computed, reactive, ref, watch } from 'vue'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import { useResource } from '@/composables/list/useResource'
import { formatDate, formatFieldValue } from '@/utils/list/formatValue'
import { notify } from '@/utils/common/notify'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  name: { type: String, required: true },
})

const terms = computed(() => props.detail.values.payment_terms || [])
const total = computed(() => terms.value.reduce((s, t) => s + Number(t.amount || 0), 0))
const subtitle = computed(() => `${terms.value.length} ${terms.value.length === 1 ? 'term' : 'terms'} · ${formatFieldValue(total.value, { fieldtype: 'Currency' })} scheduled`)

// A term can be paid only once the order itself is submitted (docstatus 1),
// and never while it's already verified / awaiting verification.
const canAct = (term) =>
  term.payment_status !== 'Verified' && term.payment_status !== 'Pending Verification' && props.detail.docstatus.value === 1

const open = ref(false)
const active = ref(null)
const rerequest = computed(() => active.value?.payment_status === 'Rejected')
const form = reactive({ company: '', conversion_rate: 1, payer_account_name: '', reference_no: '', remarks: '', reference_date: '' })

const companyCurrency = useResource({ url: 'frappe.client.get_value', notifyOnError: false })
watch(
  () => form.company,
  (company) => company && companyCurrency.resource.submit({ doctype: 'Company', filters: company, fieldname: 'default_currency' }),
)
const targetCurrency = computed(() => companyCurrency.resource.data?.default_currency || props.detail.values.currency)
const foreign = computed(() => form.company && targetCurrency.value !== props.detail.values.currency)
const received = computed(() => (foreign.value ? Number(active.value?.amount || 0) * Number(form.conversion_rate || 0) : Number(active.value?.amount || 0)))

function openDialog(term) {
  active.value = term
  Object.assign(form, {
    company: term.sales_invoice ? '' : props.detail.values.company || '',
    conversion_rate: 1,
    payer_account_name: '',
    reference_no: '',
    remarks: '',
    reference_date: new Date().toISOString().slice(0, 10),
  })
  open.value = true
}

const valid = computed(
  () =>
    form.payer_account_name.trim() &&
    form.reference_no.trim() &&
    form.remarks.trim() &&
    form.reference_date &&
    (active.value?.sales_invoice || form.company) &&
    (!foreign.value || Number(form.conversion_rate) > 0),
)

const create = useResource({
  url: 'verp_staffing.accounts.doctype.sales_order.sales_order.create_payment_entry_from_term',
})
const submitting = computed(() => create.isLoading)

async function submit() {
  const needsCompany = !active.value.sales_invoice
  const result = await create.resource.submit({
    sales_order: props.name,
    payment_term_row: active.value.name,
    reference_no: form.reference_no,
    reference_date: form.reference_date,
    remarks: form.remarks,
    payer_account_name: form.payer_account_name,
    company: needsCompany ? form.company : undefined,
    conversion_rate: needsCompany && foreign.value ? form.conversion_rate : undefined,
  })
  if (!result) return
  open.value = false
  notify.success(`Payment Entry ${result.payment_entry} submitted for verification.`)
  props.detail.refresh()
}
</script>

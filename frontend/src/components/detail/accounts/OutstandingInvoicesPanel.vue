<template>
  <SectionCard title="Write Off" subtitle="Settle outstanding invoices from this entry.">
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <FieldControl v-if="basedOnField" :field="basedOnField" v-model="detail.values.write_off_based_on" :disabled="disabled" />
      <div class="flex items-end">
        <AppButton variant="outline" icon="file-text" :disabled="disabled" @click="openDialog">Get Outstanding Invoices</AppButton>
      </div>
    </div>

    <Dialog v-model="open" :options="{ title: 'Outstanding Invoices', size: '3xl' }">
      <template #body-content>
        <div v-if="loading" class="flex justify-center py-10"><LoadingIndicator class="h-5 w-5 text-app-text-muted" /></div>
        <p v-else-if="!invoices.length" class="py-8 text-center text-p-sm text-app-text-muted">
          No submitted {{ kind.doctype }}s with an outstanding amount for {{ detail.values.company }}.
        </p>
        <div v-else class="max-h-[50vh] overflow-auto rounded-lg border border-app-border">
          <table class="w-full text-left text-p-sm">
            <thead class="sticky top-0 bg-app-panel-2 text-p-xs text-app-text-muted">
              <tr>
                <th class="w-10 px-3 py-2"><AppCheckbox :model-value="allSelected" :indeterminate="!allSelected && selected.size > 0" @update:model-value="toggleAll" /></th>
                <th class="px-3 py-2 font-medium">Invoice</th>
                <th class="px-3 py-2 font-medium">Party</th>
                <th class="px-3 py-2 font-medium">Account</th>
                <th class="px-3 py-2 font-medium">Date</th>
                <th class="px-3 py-2 text-right font-medium">Outstanding</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="inv in invoices" :key="inv.name" class="cursor-pointer border-t border-app-border hover:bg-app-panel-2" @click="toggle(inv.name)">
                <td class="px-3 py-2" @click.stop><AppCheckbox :model-value="selected.has(inv.name)" @update:model-value="toggle(inv.name)" /></td>
                <td class="px-3 py-2 font-medium text-app-text">{{ inv.name }}</td>
                <td class="px-3 py-2">{{ inv[kind.partyField] }}</td>
                <td class="px-3 py-2 text-app-text-muted">{{ inv[kind.accountField] }}</td>
                <td class="px-3 py-2">{{ formatDate(inv.posting_date) }}</td>
                <td class="px-3 py-2 text-right tabular-nums">{{ formatFieldValue(inv.outstanding_amount, { fieldtype: 'Currency' }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
      <template #actions>
        <AppButton icon="check" :loading="applying" :disabled="!selected.size" @click="apply">
          Select{{ selected.size ? ` (${selected.size})` : '' }}
        </AppButton>
      </template>
    </Dialog>
  </SectionCard>
</template>

<script setup>
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
// journal_entry.js's "Get Outstanding Invoices": for a write-off, list the
// company's open Sales (receivable) or Purchase (payable) invoices, and turn
// the ticked ones into entry rows - one per invoice, each referencing it and
// carrying its party, currency, exchange rate and due date (from the same
// get_outstanding the desk row uses) - plus a balancing row with the total,
// left for you to give its account (typically the bank / write-off account).
import { computed, ref } from 'vue'
import { call, Dialog, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import FieldControl from '@/components/detail/FieldControl.vue'
import { formatDate, formatFieldValue } from '@/utils/list/formatValue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  locked: { type: Boolean, default: false },
})

const KINDS = {
  'Accounts Receivable': { doctype: 'Sales Invoice', partyField: 'customer', accountField: 'debit_to', partyType: 'Customer', amountField: 'credit_in_account_currency', balanceField: 'debit_in_account_currency' },
  'Accounts Payable': { doctype: 'Purchase Invoice', partyField: 'supplier', accountField: 'credit_to', partyType: 'Supplier', amountField: 'debit_in_account_currency', balanceField: 'credit_in_account_currency' },
}

const disabled = computed(() => props.locked || !props.detail.canWrite.value)
const basedOnField = computed(() => props.detail.fields.value.find((f) => f.fieldname === 'write_off_based_on'))
const kind = computed(() => KINDS[props.detail.values.write_off_based_on] || KINDS['Accounts Receivable'])

const open = ref(false)
const loading = ref(false)
const applying = ref(false)
const invoices = ref([])
const selected = ref(new Set())

const allSelected = computed(() => invoices.value.length > 0 && selected.value.size === invoices.value.length)
const toggle = (name) => {
  const next = new Set(selected.value)
  next.has(name) ? next.delete(name) : next.add(name)
  selected.value = next
}
const toggleAll = () => (selected.value = allSelected.value ? new Set() : new Set(invoices.value.map((i) => i.name)))

async function openDialog() {
  const values = props.detail.values
  if (!values.company) {
    notify.error('Select a Company first.')
    return
  }
  if (!values.write_off_based_on) {
    notify.error('Please select Write Off Based On.')
    return
  }
  selected.value = new Set()
  invoices.value = []
  open.value = true
  loading.value = true
  try {
    invoices.value = await call('frappe.client.get_list', {
      doctype: kind.value.doctype,
      fields: ['name', kind.value.partyField, 'posting_date', 'outstanding_amount', kind.value.accountField],
      filters: { docstatus: 1, outstanding_amount: ['>', 0], company: values.company },
      order_by: 'posting_date asc',
      limit_page_length: 200,
    })
  } catch (error) {
    notify.error(normalizeError(error).message)
  } finally {
    loading.value = false
  }
}

async function apply() {
  const values = props.detail.values
  const k = kind.value
  applying.value = true
  try {
    const rows = []
    let total = 0
    let multi = false
    const companyCurrency = (await call('frappe.client.get_value', { doctype: 'Company', filters: values.company, fieldname: 'default_currency' }))?.default_currency

    for (const inv of invoices.value.filter((i) => selected.value.has(i.name))) {
      const account = inv[k.accountField]
      const details = (await call('verp_staffing.accounts.doctype.journal_entry.journal_entry.get_account_details_and_party_type', { account, company: values.company })) || {}
      const out = (await call('verp_staffing.accounts.doctype.journal_entry.journal_entry.get_outstanding', {
        args: {
          doctype: k.doctype,
          docname: inv.name,
          party: inv[k.partyField],
          account,
          account_currency: details.account_currency,
          company: values.company,
          company_currency: companyCurrency,
        },
      })) || {}
      const amount = Number(inv.outstanding_amount)
      total += amount
      if (details.account_currency && details.account_currency !== companyCurrency) multi = true
      rows.push({
        account,
        account_currency: details.account_currency,
        exchange_rate: out.exchange_rate || 1,
        party_type: k.partyType,
        party: inv[k.partyField],
        reference_type: k.doctype,
        reference_name: inv.name,
        reference_due_date: out.reference_due_date,
        [k.amountField]: amount,
      })
    }
    rows.push({ [k.balanceField]: Number(total.toFixed(6)) }) // toFixed: 0.1 + 0.2 must not leave 0.30000000000000004 on the balancing row
    values.accounts = rows
    if (multi) values.multi_currency = 1
    open.value = false
    notify.info('Invoices added - choose the account for the balancing row, then save.')
  } catch (error) {
    notify.error(normalizeError(error).message)
  } finally {
    applying.value = false
  }
}
</script>

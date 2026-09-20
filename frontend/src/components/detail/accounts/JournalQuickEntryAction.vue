<template>
  <AppButton v-if="detail.isNew.value" variant="outline" icon="zap" @click="open = true">Quick Entry</AppButton>

  <Dialog v-model="open" :options="{ title: 'Quick Journal Entry', size: 'lg' }">
    <template #body-content>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <AppInput type="number" label="Amount" v-model="form.amount" required />
        <AppInput type="date" label="Date" v-model="form.posting_date" required />
        <AppLinkField label="Debit Account" doctype="Account" v-model="form.debit_account" :filters="accountFilters" hide-add-new />
        <AppLinkField label="Credit Account" doctype="Account" v-model="form.credit_account" :filters="accountFilters" hide-add-new />
        <AppCombobox v-if="seriesOptions.length > 1" label="Series" v-model="form.naming_series" :options="seriesOptions" required />
        <AppInput type="textarea" label="User Remark" v-model="form.user_remark" class="sm:col-span-2" />
      </div>
    </template>
    <template #actions>
      <AppButton icon="save" :loading="saving" :disabled="!valid" @click="apply">Save</AppButton>
    </template>
  </Dialog>
</template>

<script setup>
import AppInput from '@/components/ui/AppInput.vue'
// journal_entry.js's "Quick Entry": one amount moved from a credit account to a
// debit account. Fills the entry's two rows (and date / remark / series) and
// saves it straight away, so a simple transfer is one dialog rather than a
// hand-built table.
import { computed, reactive, ref, watch } from 'vue'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import { notify } from '@/utils/common/notify'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  // The page's Save — saves and, for a new record, moves to its own URL.
  save: { type: Function, required: true },
})

const open = ref(false)
const saving = ref(false)
const form = reactive({ amount: '', debit_account: '', credit_account: '', posting_date: '', user_remark: '', naming_series: '' })

const seriesOptions = computed(() => {
  const field = props.detail.fields.value.find((f) => f.fieldname === 'naming_series')
  return (field?.options || '').split('\n').filter(Boolean)
})

// Leaf accounts of the entry's company (the desk's account_query; the
// company-currency restriction is dropped here — the server validates the
// currency rules on save).
const accountFilters = computed(() => ({ is_group: 0, ...(props.detail.values.company ? { company: props.detail.values.company } : {}) }))

watch(open, (isOpen) => {
  if (!isOpen) return
  Object.assign(form, {
    amount: '',
    debit_account: '',
    credit_account: '',
    posting_date: props.detail.values.posting_date || new Date().toISOString().slice(0, 10),
    user_remark: props.detail.values.user_remark || '',
    naming_series: props.detail.values.naming_series || seriesOptions.value[0] || '',
  })
})

const valid = computed(
  () => Number(form.amount) > 0 && form.debit_account && form.credit_account && form.debit_account !== form.credit_account && form.posting_date,
)

async function apply() {
  if (!props.detail.values.company) {
    notify.error('Select a Company first.')
    return
  }
  const values = props.detail.values
  values.posting_date = form.posting_date
  values.user_remark = form.user_remark
  if (form.naming_series) values.naming_series = form.naming_series
  values.accounts = [
    { account: form.debit_account, debit_in_account_currency: Number(form.amount) },
    { account: form.credit_account, credit_in_account_currency: Number(form.amount) },
  ]
  saving.value = true
  try {
    if (await props.save()) open.value = false
  } finally {
    saving.value = false
  }
}
</script>

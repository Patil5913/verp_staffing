<template>
  <div class="flex h-full flex-col bg-app-bg">
    <SubNavbar title="Chart of Accounts">
      <AppSearchInput v-model="search" class="w-full" placeholder="Search account name, number or type">
        <template #suffix>
          <Popover trigger="click" placement="bottom-end">
            <template #target="{ togglePopover }">
              <FeatherIcon
                name="info"
                class="h-4 w-4 cursor-pointer text-app-text-muted hover:text-app-primary"
                @click="togglePopover()"
              />
            </template>
            <template #body="{ close }">
              <div
                class="my-2 w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-app-border bg-app-panel shadow-xl"
              >
                <div class="flex items-center gap-2 border-b border-app-border bg-app-panel-2 px-4 py-3">
                  <FeatherIcon name="search" class="h-4 w-4 text-app-primary" />
                  <h4 class="text-p-base font-semibold text-app-text">Search syntax</h4>
                </div>
                <div class="flex flex-col divide-y divide-app-border">
                  <div v-for="group in treeSearchSyntaxHelp" :key="group.title" class="flex flex-col gap-2.5 px-4 py-3">
                    <p class="text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">{{ group.title }}</p>
                    <div v-for="row in group.rows" :key="row.example" class="flex flex-col gap-1">
                      <button
                        type="button"
                        class="block w-fit max-w-full whitespace-pre-wrap break-words rounded-md bg-app-panel-2 px-2 py-1 text-left font-mono text-p-xs text-app-primary hover:bg-app-primary-tint"
                        @click="search = row.example, close()"
                      >
                        {{ row.example }}
                      </button>
                      <span class="text-p-sm leading-snug text-app-text-muted">{{ row.description }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </Popover>
        </template>
      </AppSearchInput>
      <AppButton
        variant="outline"
        theme="red"
        icon="x"
        tooltip="Clear search"
        :disabled="!search"
        @click="search = ''"
      />

      <template #right>
        <AppButton variant="outline" icon="chevrons-down" tooltip="Expand all" @click="tree?.expandAll()" />
        <AppButton variant="outline" icon="chevrons-up" tooltip="Collapse" @click="tree?.collapseAll()" />
        <AppButton v-if="canCreate" variant="primary" icon="plus" tooltip="New Account" @click="openNew(null)" />
        <AppButton variant="surface" icon="refresh-cw" tooltip="Refresh" @click="tree?.reload()" />
      </template>
    </SubNavbar>

    <div class="flex min-h-0 flex-1 flex-col gap-3 px-3 md:px-6 py-3">
      <StateBanner
        v-if="!companies.length && !loadingCompanies"
        icon="building"
        title="No company yet"
        description="Create a Company first - accounts belong to one."
      />
      <template v-else-if="company">
        <div class="flex items-center gap-2">
          <AppCombobox v-model="company" class="w-56" compact :options="companies" :disabled="!companies.length" />
          <AppButton variant="surface" icon="refresh-cw" tooltip="Refresh" @click="tree?.reload()" />
        </div>

        <div class="flex flex-wrap items-center gap-2 text-p-xs text-app-text-muted">
          <span v-for="t in ROOT_TYPES" :key="t.name" class="inline-flex items-center gap-1.5 rounded-full border border-app-border bg-app-panel px-2.5 py-1">
            <span class="size-2 rounded-full" :class="t.dot" />{{ t.name }}
          </span>
          <span v-if="showBalances" class="ml-auto">Balances are shown as Dr / Cr in company currency.</span>
        </div>

        <DocTreeView
          ref="tree"
          :key="company"
          :loader="loadChildren"
          :after-load="attachBalances"
          :columns="columns"
          :search="search"
          name-label="Account"
          empty-title="No accounts in this company"
          empty-description="Add a root account (Asset, Liability, Equity, Income or Expense) to start the chart."
          @open="(node) => router.push(`/Account/${encodeURIComponent(node.value)}`)"
        >
          <template #label="{ node }">
            <span class="mr-2 size-2 shrink-0 rounded-full" :class="rootDot(node.root_type)" />
            <span class="truncate" :class="node.expandable ? 'font-semibold text-app-text' : 'text-app-text'">{{ node.label }}</span>
            <span v-if="node.disabled" class="ml-2 shrink-0 rounded bg-app-panel-2 px-1.5 text-p-xs text-app-text-muted">Disabled</span>
          </template>
          <template #cell-balance="{ node }">
            <span v-if="node.balanceText" :class="node.balance > 0 ? 'text-app-text' : 'text-app-text-muted'">{{ node.balanceText }}</span>
          </template>
          <template #actions="{ node }">
            <AppButton v-if="canCreate && node.expandable" variant="ghost" size="sm" icon="plus" tooltip="Add child account" @click="openNew(node)" />
            <AppButton v-if="canReadLedger" variant="ghost" size="sm" icon="book-open" tooltip="View ledger" @click="viewLedger(node)" />
          </template>
        </DocTreeView>
      </template>
    </div>

    <Dialog v-model="showNew" :options="{ title: newParent ? `Add account under ${newParent.label}` : 'New root account', size: 'lg' }">
      <template #body-content>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <AppInput label="Account Name" v-model="form.account_name" required class="sm:col-span-2" />
          <AppInput label="Account Number" v-model="form.account_number" description="Included as a prefix in the account's name." />
          <div class="pt-6"><AppCheckbox label="Is Group" v-model="form.is_group" /></div>
          <AppInput
            v-if="!newParent"
            type="select"
            label="Root Type"
            v-model="form.root_type"
            :options="['Asset', 'Liability', 'Equity', 'Income', 'Expense']"
            required
          />
          <AppInput type="select" label="Account Type" v-model="form.account_type" :options="accountTypes" />
          <AppLinkField label="Currency" doctype="Currency" v-model="form.account_currency" hide-add-new />
          <template v-if="form.account_type === 'Bank'">
            <AppLinkField label="Bank" doctype="Bank" v-model="form.bank" />
            <AppLinkField label="Bank Account Type" doctype="Bank Account Type" v-model="form.bank_account_type" />
          </template>
        </div>
      </template>
      <template #actions>
        <AppButton :loading="creating" :disabled="!canSubmitNew" @click="createAccount">Create</AppButton>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { moneyOptions } from '@/utils/common/defaultCurrency'
import AppSearchInput from '@/components/ui/AppSearchInput.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'
// Chart of Accounts - the Account tree, company-scoped. Ported from
// account_tree.js: nodes come from accounts.utils.get_children (which is
// company-aware; the stock treeview isn't, which is why accounts from every
// company used to pile into one list), balances from get_account_balances
// when Accounts Settings turns "Show Balances in COA" on, and new accounts go
// through add_ac.
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call, Dialog, FeatherIcon, Popover } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import SubNavbar from '@/components/common/SubNavbar.vue'
import DocTreeView from '@/components/tree/DocTreeView.vue'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

const route = useRoute()
const router = useRouter()

const ROOT_TYPES = [
  { name: 'Asset', dot: 'bg-emerald-500' },
  { name: 'Liability', dot: 'bg-rose-500' },
  { name: 'Equity', dot: 'bg-violet-500' },
  { name: 'Income', dot: 'bg-sky-500' },
  { name: 'Expense', dot: 'bg-amber-500' },
]
const rootDot = (type) => ROOT_TYPES.find((t) => t.name === type)?.dot || 'bg-app-border'

const tree = ref(null)
const search = ref('')
const company = ref('')

// Searching needs the whole chart in memory to keep matches' ancestors
// visible, so the first search loads it all.
watch(search, (value, prev) => {
  if (value.trim() && !prev.trim()) tree.value?.expandAll()
})

const treeSearchSyntaxHelp = [
  {
    title: 'Match a field',
    rows: [
      { example: 'account_type=Bank', description: 'Scope the match to one column, by its name or column label.' },
      { example: 'root_type="Fixed Asset"', description: 'Quote a value that has spaces.' },
      { example: 'parth', description: 'A plain word matches any visible column instead.' },
    ],
  },
  {
    title: 'Combine conditions',
    rows: [
      { example: 'root_type=Asset account_type=Bank', description: 'Multiple fields - all must match (AND).' },
      { example: 'root_type=Asset or root_type=Liability', description: 'Either one can match (OR) instead.' },
    ],
  },
  {
    title: 'Compare & range',
    rows: [
      { example: 'root_type!=Expense', description: 'Not equal, also works with >, <, >=, <=.' },
      { example: 'name between a to m', description: 'A range on one field.' },
    ],
  },
]

const companyList = useResource({
  url: 'frappe.client.get_list',
  params: { doctype: 'Company', fields: ['name'], limit_page_length: 200, order_by: 'name asc' },
  auto: true,
})
const loadingCompanies = computed(() => companyList.isLoading)
const companies = computed(() => (companyList.resource.data || []).map((c) => c.name))
watch(
  companies,
  (list) => {
    if (company.value || !list.length) return
    const wanted = route.query.company
    company.value = list.includes(wanted) ? wanted : list[0]
  },
  { immediate: true },
)

const settings = useResource({
  url: 'frappe.client.get_single_value',
  params: { doctype: 'Accounts Settings', field: 'show_balance_in_coa' },
  notifyOnError: false,
  auto: true,
})
const showBalances = computed(() => Boolean(Number(settings.resource.data)))

const accountMeta = useResource({
  url: 'verp_staffing.utils.detail_view.get_doc_meta',
  params: { doctype: 'Account' },
  notifyOnError: false,
  auto: true,
})
const canCreate = computed(() => Boolean(accountMeta.resource.data?.perms?.write))
const canReadLedger = true
const accountTypes = computed(() => {
  const f = accountMeta.resource.data?.fields?.find((x) => x.fieldname === 'account_type')
  return (f?.options || '').split('\n')
})

const columns = computed(() => [
  { key: 'account_type', label: 'Type', width: '11rem' },
  { key: 'root_type', label: 'Root', width: '7rem' },
  { key: 'account_currency', label: 'Currency', width: '6rem' },
  ...(showBalances.value ? [{ key: 'balance', label: 'Balance', width: '12rem', align: 'right' }] : []),
])

function loadChildren(parent) {
  return call('verp_staffing.accounts.utils.utils.get_children', {
    doctype: 'Account',
    parent: parent || '',
    company: company.value,
    is_root: parent === null,
  })
}

const fmt = (n, currency) =>
  new Intl.NumberFormat(undefined, moneyOptions(currency)).format(Math.abs(n))

async function attachBalances(nodes) {
  if (!showBalances.value || !nodes.length) return
  try {
    const rows = await call('verp_staffing.accounts.utils.utils.get_account_balances', {
      accounts: nodes.map((n) => ({ value: n.value, account_currency: n.account_currency })),
      company: company.value,
    })
    for (const row of rows || []) {
      const node = nodes.find((n) => n.value === row.value)
      if (!node) continue
      node.balance = row.balance
      node.balanceText = `${fmt(row.balance, row.company_currency)} ${row.balance > 0 ? 'Dr' : row.balance < 0 ? 'Cr' : ''}`.trim()
    }
  } catch {
    // Balances are decoration - a failure here shouldn't hide the chart.
  }
}

function viewLedger(node) {
  router.push({ path: '/report/General%20Ledger', query: { company: company.value, account: node.value } })
}

const showNew = ref(false)
const newParent = ref(null)
const creating = ref(false)
const blankForm = () => ({ account_name: '', account_number: '', is_group: false, root_type: '', account_type: '', account_currency: '', bank: '', bank_account_type: '' })
const form = reactive(blankForm())
const canSubmitNew = computed(() => form.account_name.trim() && (newParent.value || form.root_type))

function openNew(parent) {
  newParent.value = parent
  Object.assign(form, blankForm(), parent ? { root_type: parent.root_type } : {})
  showNew.value = true
}

async function createAccount() {
  creating.value = true
  try {
    await call('verp_staffing.accounts.utils.utils.add_ac', {
      doctype: 'Account',
      company: company.value,
      parent: newParent.value?.value || '',
      is_root: newParent.value ? 0 : 1,
      account_name: form.account_name.trim(),
      account_number: form.account_number,
      is_group: form.is_group ? 1 : 0,
      root_type: form.root_type,
      account_type: form.account_type,
      account_currency: form.account_currency,
      bank: form.bank,
      bank_account_type: form.bank_account_type,
    })
    notify.success('Account created.')
    showNew.value = false
    if (newParent.value) await tree.value?.refreshNode(newParent.value)
    else await tree.value?.reload()
  } catch (error) {
    notify.error(normalizeError(error).message)
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  if (route.query.search) search.value = String(route.query.search)
})
</script>

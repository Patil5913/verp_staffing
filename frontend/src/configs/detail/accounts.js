import { call } from 'frappe-ui'
import { computeInvoiceStatus } from '@/utils/list/statusTheme'
import { formatFieldValue } from '@/utils/list/formatValue'
import { paidAccountFilterFor } from '@/utils/detail/paymentAccounts'
import { notify } from '@/utils/common/notify'
import AddressContactPanel from '@/components/detail/customer/AddressContactPanel.vue'
import DocAction from '@/components/detail/actions/DocAction.vue'
import NoticeBanner from '@/components/common/NoticeBanner.vue'
import LinkAction from '@/components/detail/actions/LinkAction.vue'
import SummaryStrip from '@/components/detail/SummaryStrip.vue'
import { agreementRequired } from '@/utils/detail/agreementRequired'
import AgreementPanel from '@/components/detail/accounts/AgreementPanel.vue'
import SendDetailsFormAction from '@/components/detail/accounts/SendDetailsFormAction.vue'
import JournalQuickEntryAction from '@/components/detail/accounts/JournalQuickEntryAction.vue'
import OutstandingInvoicesPanel from '@/components/detail/accounts/OutstandingInvoicesPanel.vue'
import LinkedInvoicesPanel from '@/components/detail/accounts/LinkedInvoicesPanel.vue'
import PaymentEntryAssist from '@/components/detail/accounts/PaymentEntryAssist.vue'
import PaymentTermsField from '@/components/detail/accounts/PaymentTermsField.vue'

const notNew = (d) => !d.isNew.value
const submitted = (d) => d.docstatus.value === 1
const num = (v) => Number(v) || 0
const sum = (rows, key) => (rows || []).reduce((s, r) => s + num(r[key]), 0)
// Sales Order hides `company` (auto-set from ERP Configuration's default,
// set_only_once) — get_doc_meta drops hidden fields from `values` entirely,
// so it only ever shows up in `hidden`. Every other doctype here shows it
// plainly in `values`. Checking both keeps one accessor working across all
// of them instead of every company-scoped filter/lookup silently getting
// undefined on Sales Order specifically.
const companyOf = (detail) => detail.values.company || detail.hidden.company

const strip = (items) => ({ type: 'component', component: SummaryStrip, props: { items } })
const fields = (fieldnames, title, extra = {}) => ({ type: 'fields', fieldnames, title, ...extra })
const table = (fieldname, extra = {}) => ({ type: 'table', fieldname, ...extra })
// A grid section is always column-curated (a grid has no room for every
// field a row-dialog would show) — `columns` is required, `readOnlyColumns`
// optional. See GridTableField.vue.
// Editable-grid or row dialog, per the child doctype's own flag; columns from in_list_view.
const auto = (fieldname, extra = {}) => ({ type: 'auto', fieldname, ...extra })
const grid = (fieldname, columns, extra = {}) => ({ type: 'grid', fieldname, columns, ...extra })

// Ported from the old desk sales_order.js / sales_invoice.js /
// purchase_order.js / purchase_invoice.js's near-identical Items Table row
// handlers (all four share the same "Items Table" child doctype):
// picking an Item auto-fills Type to "Sales" (Sales Order/Sales Invoice) or
// "Purchase" (Purchase Order/Purchase Invoice) and fetches its stock UOM
// plus the document's company's default Income Account or Expense Account
// respectively (kept off the dialog entirely via the items table() config's
// hiddenColumns — meant to be set automatically, never picked by hand);
// Qty/Rate recompute Amount, which the doctype itself marks read_only (see
// ChildTableField's Amount column) — none of that was happening
// client-side, so every row's Amount stayed at 0 until the next full
// save/reload.
function makeItemsTableFieldChange({ type, accountField }) {
  return async function itemsTableFieldChange(fieldname, value, draft, { detail }) {
    if (fieldname === 'item' && value) {
      const patch = { type }
      const item = await call('frappe.client.get_value', {
        doctype: 'Item',
        filters: value,
        fieldname: 'stock_uom',
      }).catch(() => null)
      if (item?.stock_uom) patch.uom = item.stock_uom

      const company = companyOf(detail)
      if (company) {
        const account = await call('verp_staffing.accounts.api.get_defaults.get_default_company_account', {
          company,
          fieldname: accountField,
        }).catch(() => null)
        if (account) patch[accountField === 'default_income_account' ? 'income_account' : 'expense_account'] = account
      }

      const qty = num(draft.qty) || 1
      patch.qty = qty
      if (draft.rate) patch.amount = qty * num(draft.rate)
      return patch
    }

    if (fieldname === 'qty' || fieldname === 'rate') {
      const qty = fieldname === 'qty' ? num(value) : num(draft.qty)
      const rate = fieldname === 'rate' ? num(value) : num(draft.rate)
      return { amount: qty * rate }
    }

    return null
  }
}
// Same rule the list view badge (statusTheme.js's listStatusColumn) uses —
// see computeInvoiceStatus there for the actual formula.
const invoiceStatusText = (d) => computeInvoiceStatus(d.values)

// Items already picked in another row of the same table can't be picked again.
const uniqueItemQuery = (row, rows, idx) => ({
  item: { filters: { name: ['not in', (rows || []).filter((r, i) => i !== idx && r.item).map((r) => r.item)] } },
})

const salesItemsFieldChange = makeItemsTableFieldChange({ type: 'Sales', accountField: 'default_income_account' })
const purchaseItemsFieldChange = makeItemsTableFieldChange({ type: 'Purchase', accountField: 'default_expense_account' })

// Payment Terms' own condition-based clearing/interview-count/due-date
// logic now lives in PaymentTermsField.vue (the grid+row-expand component
// that replaced both the old plain grid section and the separate
// PaymentTermsPanel display table) — nothing config-level needs it anymore.

const ledgerAction = (queryExtra = {}) => ({
  component: LinkAction,
  props: {
    label: 'View Ledger',
    icon: 'book-open',
    to: '/report/General%20Ledger',
    query: { company: '$values.company', voucher_no: '$name', ...queryExtra },
  },
  show: (d) => notNew(d) && d.docstatus.value > 0,
})

// ─── Taxes and Charges (shared across Sales Invoice, Purchase Invoice, ───
// ─── Sales Order, Purchase Order) ─────────────────────────────────────
//
// Ported from the old desk script's `frappe.ui.form.on("Taxes and
// Charges", {...})` handlers (charge_type / rate / tax_amount / row_id /
// taxes_add / taxes_remove, all funneling into validate_taxes_and_charges).
// Kept as ONE shared pair of functions, not a per-doctype factory like
// items — unlike items (different `type` and account field per Sales/
// Purchase), nothing about this validation differs by doctype; it was a
// single doctype-level script in Desk, and stays a single function here.
//
// This is wired to `grid()`, not `table()` — see the taxes sections below
// for why (GridTableField's readOnlyColumns is the only place this
// per-row-conditional editability can live; ChildTableField's dialog has
// no equivalent). Column set is a best guess at Taxes and Charges' own
// fields (charge_type, account_head, rate, tax_amount, total) — confirm
// against the actual doctype before shipping and add/remove columns as
// needed; description or included_in_print_rate may belong here too.
// Totals block shared by the four doc types. base_* (company currency) fields
// carry a currency-mismatch depends_on in their doctype JSON, so they only
// appear when the document currency differs from the company's; a field a
// doctype doesn't have is simply skipped.
const TOTALS_FIELDS = [
  'total_qty', 'total', 'base_total', 'net_total', 'base_net_total',
  'total_taxes_and_charges', 'base_total_taxes_and_charges', 'base_discount_amount',
  'grand_total', 'base_grand_total', 'rounding_adjustment', 'base_rounding_adjustment',
  'rounded_total', 'base_rounded_total', 'in_words', 'base_in_words',
]

const TAXES_GRID_COLUMNS = ['charge_type', 'account_head', 'rate', 'tax_amount', 'total']

function taxesReadOnlyColumns(col, row) {
  if (col.fieldname === 'rate') return row.charge_type === 'Actual'
  if (col.fieldname === 'tax_amount') return row.charge_type !== 'Actual'
  return false
}

// GridTableField calls onFieldChange(fieldname, value, row, rowIndex);
// ConfigDetailPage's onFieldChangeFor forwards rowIndex as `idx` on the
// context object (see that file's onFieldChangeFor) since only grid
// sections have a stable row position — a table() dialog edits one row in
// isolation with no equivalent notion of "which row is this."
//
// GridTableField has no per-row error banner the way ChildTableField's
// dialog does (no `validateRow`/inline message slot), so where the desk
// script did `frappe.throw(msg)` — which both showed a message AND
// aborted the change — this can only do the second half via a returned
// patch, and surfaces the message as a toast (notify.error, the same
// utility fieldGuards already uses in ConfigDetailPage) as the closest
// equivalent.
function taxesFieldChange(fieldname, value, draft, { idx }) {
  // rate / tax_amount typed with no Charge Type chosen (validate_taxes_and_charges'
  // first branch): reset the row rather than keep numbers that mean nothing.
  if ((fieldname === 'rate' || fieldname === 'tax_amount') && !draft.charge_type && value) {
    notify.error('Please select Charge Type first')
    return { row_id: '', rate: 0, tax_amount: 0 }
  }
  if (fieldname !== 'charge_type' && fieldname !== 'row_id') return null

  const row = { ...draft, [fieldname]: value }
  const patch = {}

  if (fieldname === 'charge_type') {
    // charge_type cleared while row_id/rate/tax_amount were already set —
    // desk reset all three ("Please select Charge Type first").
    if (!value && (row.row_id || row.rate || row.tax_amount)) {
      notify.error('Please select Charge Type first')
      return { row_id: '', rate: 0, tax_amount: 0 }
    }
    // Actual: rate isn't used at all — desk zeroed it; which of rate/
    // tax_amount is editable is handled separately by taxesReadOnlyColumns.
    if (value === 'Actual') patch.rate = 0
    // Only "On Previous Row Amount/Total" may reference another row.
    if (['Actual', 'On Net Total', 'On Paid Amount'].includes(value) && row.row_id) {
      notify.error("Can refer row only if charge type is 'On Previous Row Amount' or 'On Previous Row Total'")
      patch.row_id = ''
    }
    if (['On Previous Row Amount', 'On Previous Row Total'].includes(value)) {
      // idx is 0-based; desk's tax.idx is 1-based, so idx === 0 is desk's
      // tax.idx === 1 (the first row — nothing to reference).
      if (idx === 0) {
        notify.error("Cannot select 'On Previous Row' charge type for the first row")
        return { charge_type: '' }
      }
      // Default row_id to the previous row — desk's `tax.idx - 1`, which
      // in 0-based terms is just this row's own idx.
      if (!row.row_id) patch.row_id = idx
    }
  }

  if (fieldname === 'row_id' && ['On Previous Row Amount', 'On Previous Row Total'].includes(row.charge_type)) {
    // row_id must reference an earlier row — desk's `row_id >= idx` (1-based)
    // is `row_id >= idx + 1` here (0-based).
    if (row.row_id !== '' && Number(row.row_id) >= idx + 1) {
      notify.error('Row ID must be less than the current row number')
      patch.row_id = ''
    }
  }

  return Object.keys(patch).length ? patch : null
}

// ─── Accounts Master ──────────────────────────────────────────────────

export const companyConfig = {
  doctype: 'Company',
  timeline: 'full',
  // The abbreviation and chart-of-accounts choice are fixed at creation
  // (company.js locks them once the record exists).
  readOnlyFields: (d) => (d.isNew.value ? [] : ['abbr', 'create_chart_of_accounts_based_on', 'chart_of_accounts', 'existing_company']),
  actions: [
    {
      component: LinkAction,
      props: { label: 'Chart of Accounts', icon: 'list-tree', to: '/Account/view/tree', query: { company: '$name' } },
      show: notNew,
    },
  ],
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        fields(['company_name', 'abbr', 'default_currency', 'country', 'parent_company', 'is_group', 'date_of_establishment'], 'Company'),
        fields(['company_logo', 'date_of_commencement', 'date_of_incorporation', 'phone_no', 'email'], 'Contact'),
        fields(['create_chart_of_accounts_based_on', 'existing_company', 'chart_of_accounts'], 'Chart of Accounts'),
      ],
    },
    {
      key: 'accounts',
      label: 'Default Accounts',
      sections: [
        fields(
          [
            'default_bank_account', 'default_cash_account', 'default_receivable_account', 'default_payable_account',
            'default_income_account', 'default_expense_account', 'default_discount_account', 'write_off_account',
            'round_off_account', 'allow_account_creation_against_child_company',
          ],
          'Default Accounts',
        ),
      ],
    },
    { key: 'contacts', label: 'Address & Contact', show: notNew, sections: [{ type: 'component', component: AddressContactPanel }] },
  ],
}

export const fiscalYearConfig = {
  doctype: 'Fiscal Year',
  timeline: 'full',
  // A disabled Fiscal Year is permanently locked (fiscal_year.js's
  // _enforce_disabled_state) — judged by the *saved* value, so ticking the
  // box mid-edit doesn't lock the form before it's been saved.
  locked: (d) => notNew(d) && Boolean(d.meta.resource.data?.values?.disabled),
  // Ticking "disabled" is irreversible, so it asks first (fiscal_year.js's
  // `disabled` handler); a saved-disabled year can't be re-enabled at all.
  fieldGuards: [
    {
      field: 'disabled',
      check: (value, saved) => {
        if (!value && Number(saved)) return { block: 'A disabled Fiscal Year is permanently locked and cannot be re-enabled.' }
        if (value) {
          return {
            confirm: {
              title: 'Disable this Fiscal Year?',
              message:
                'This permanently locks the Fiscal Year: no new transactions can be posted against it and the record becomes fully read-only. This action cannot be undone.',
              confirmLabel: 'Disable Fiscal Year',
            },
          }
        }
        return null
      },
    },
  ],
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        fields(['year', 'year_start_date', 'year_end_date', 'is_short_year', 'disabled'], 'Fiscal Year'),
        // Only companies not already in another active year (get_available_companies).
        table('included_companies', {
          linkQueries: ({ name }) => ({
            company: {
              query: 'verp_staffing.accounts.doctype.fiscal_year.fiscal_year.get_available_companies',
              filters: { current_fiscal_year: name || '' },
            },
          }),
        }),
      ],
    },
  ],
}

export const accountConfig = {
  doctype: 'Account',
  timeline: 'full',
  // A root account (no parent) is read-only; company / is_group can't change
  // once created (account.js: toggle_enable(..., is_new())).
  locked: (d) => notNew(d) && !d.values.parent_account,
  readOnlyFields: (d) => (d.isNew.value ? [] : ['is_group', 'company']),
  actions: [
    { component: LinkAction, props: { label: 'Chart of Accounts', icon: 'list-tree', to: '/Account/view/tree', query: { company: '$values.company' } }, show: notNew },
    {
      component: DocAction,
      props: {
        label: 'Convert to Non-Group',
        icon: 'file-text',
        method: 'run_doc_method',
        args: { dt: '$doctype', dn: '$name', method: 'convert_group_to_ledger' },
        confirm: 'Convert this group account to a ledger (non-group) account?',
        success: 'Converted to a ledger account.',
      },
      show: (d) => notNew(d) && d.values.parent_account && Number(d.values.is_group) === 1,
    },
    {
      component: LinkAction,
      props: { label: 'General Ledger', icon: 'book-open', to: '/report/General%20Ledger', query: { account: '$name', company: '$values.company' } },
      show: (d) => notNew(d) && Number(d.values.is_group) === 0,
    },
  ],
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        {
          type: 'component',
          component: NoticeBanner,
          props: { message: 'This is a root account and cannot be edited.' },
          show: (d) => notNew(d) && !d.values.parent_account,
        },
        fields(['account_name', 'account_number', 'company', 'parent_account', 'is_group', 'disabled'], 'Account'),
        fields(['root_type', 'report_type', 'account_type', 'account_currency'], 'Classification'),
        { ...fields(['bank', 'bank_account_type', 'ifsc_code'], 'Bank Details'), show: (d) => d.values.account_type === 'Bank' },
      ],
    },
  ],
}

export const bankConfig = {
  doctype: 'Bank',
  timeline: 'full',
  tabs: [
    { key: 'details', label: 'Details', sections: [fields(['bank_name', 'swift_number'], 'Bank Details')] },
    { key: 'contacts', label: 'Address & Contact', show: notNew, sections: [{ type: 'component', component: AddressContactPanel }] },
  ],
}

export const bankAccountConfig = {
  doctype: 'Bank Account',
  timeline: 'full',
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        fields(['account_name', 'bank', 'account', 'account_type', 'company', 'is_company_account', 'disabled'], 'Bank Account'),
        fields(['party_type', 'party'], 'Party'),
        fields(['bank_account_no', 'iban', 'ifsc_code'], 'Account Details'),
      ],
    },
    { key: 'contacts', label: 'Address & Contact', show: notNew, sections: [{ type: 'component', component: AddressContactPanel }] },
  ],
}

// ─── Accounting ───────────────────────────────────────────────────────

export const journalEntryConfig = {
  doctype: 'Journal Entry',
  timeline: 'full',
  actions: [
    { component: JournalQuickEntryAction },
    ledgerAction(),
    {
      component: DocAction,
      props: {
        label: 'Reverse Journal Entry',
        icon: 'rotate-ccw',
        method: 'verp_staffing.accounts.doctype.journal_entry.journal_entry.make_reverse_journal_entry',
        args: { source_name: '$name' },
        create: 'Journal Entry',
        success: 'Reversal drafted.',
      },
      show: (d) => notNew(d) && submitted(d),
    },
  ],
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        // Live figures — recomputed from the rows as they're typed, so an
        // unbalanced entry is obvious before the server refuses it.
        strip([
          { label: 'Total Debit', value: (d) => sum(d.values.accounts, 'debit') || sum(d.values.accounts, 'debit_in_account_currency') },
          { label: 'Total Credit', value: (d) => sum(d.values.accounts, 'credit') || sum(d.values.accounts, 'credit_in_account_currency') },
          {
            label: 'Difference',
            value: (d) => Math.abs((sum(d.values.accounts, 'debit') || sum(d.values.accounts, 'debit_in_account_currency')) - (sum(d.values.accounts, 'credit') || sum(d.values.accounts, 'credit_in_account_currency'))),
            tone: (v) => (num(v) === 0 ? 'text-green-600' : 'text-red-600'),
          },
        ]),
        fields(['voucher_type', 'naming_series', 'company', 'posting_date', 'finance_book', 'multi_currency', 'from_template', 'reversal_of'], 'Journal Entry'),
        table('accounts'),
        fields(['cheque_no', 'cheque_date', 'user_remark'], 'Notes'),
        fields(['clearance_date', 'bill_no', 'bill_date', 'due_date', 'is_opening', 'mode_of_payment'], 'More Information'),
        { type: 'component', component: OutstandingInvoicesPanel, show: (d) => d.docstatus.value === 0 },
      ],
    },
  ],
}

function paidAccountFilters(bankCashPaymentTypes) {
  return ({ detail }) =>
    paidAccountFilterFor({
      partyType: detail.values.party_type,
      paymentType: detail.values.payment_type,
      company: companyOf(detail),
      bankCashPaymentTypes,
    })
}

// account_head (the taxes/charges child table shared by Sales Order/Sales
// Invoice/Purchase Order/Purchase Invoice/Payment Entry, one Item Tax-style
// row per line) and additional_discount_account (Discount & Rounding on
// every one of those five) both had no filter at all before this — every
// account in the company showed up, groups and disabled ones included, and
// nothing scoped to the transaction's own company.
export const TAX_ACCOUNT_TYPES = ['Tax', 'Chargeable', 'Indirect Expense', 'Direct Expense', 'Expense Account', 'Income Account']
function taxAccountLinkQueries({ detail }) {
  return {
    account_head: {
      filters: { account_type: ['in', TAX_ACCOUNT_TYPES], is_group: 0, disabled: 0, company: companyOf(detail) },
    },
  }
}
function discountAccountLinkQueries({ detail }) {
  return {
    additional_discount_account: { filters: { is_group: 0, disabled: 0, company: companyOf(detail) } },
  }
}

const fmtAmount = (d) => `${formatFieldValue(d.values.paid_amount, { fieldtype: 'Currency' })} ${d.values.currency || ''}`.trim()

// Ported verbatim (content-wise) from the old desk payment_entry.js's
// Submit/Cancel confirmation dialogs — Submit had no confirmation at all
// before ConfigDetailPage's submitConfirm/cancelConfirm hooks, and Cancel
// only ever showed one generic sentence.
export const paymentEntrySubmitConfirm = (d) => `
  <div style="line-height:1.6">
    <p><b>You are about to submit this Payment Entry.</b></p>
    <p>Submitting confirms that:</p>
    <ul style="padding-left:16px">
      <li>The payment of <b>${fmtAmount(d)}</b> has been <b>received</b></li>
      <li>This will be recorded as a <b>Verified Payment</b></li>
      <li>This <b>cannot be edited</b> after submission.</li>
    </ul>
    <p class="text-app-text-muted" style="font-size:12px">
      If unsure, ask your accounts manager to verify instead.
    </p>
  </div>
`

const paymentEntryCancelConfirm = (d) => `
  <div style="line-height:1.6">
    <p><b>You are about to cancel this Payment Entry.</b></p>
    <p>Cancelling means:</p>
    <ul style="padding-left:16px">
      <li>The payment of <b>${fmtAmount(d)}</b> will be <b>reversed</b></li>
      <li>All accounting entries (GL) will be <b>cancelled</b></li>
      ${
        d.hidden.payment_term_row
          ? `<li>The linked payment term will be <b>reset to Unpaid</b></li>`
          : `<li>Outstanding amounts on linked invoices will be <b>restored</b></li>`
      }
      <li>This action <b>cannot be undone</b></li>
    </ul>
    <p class="text-app-text-muted" style="font-size:12px">
      Only cancel if the payment was made in error.
    </p>
  </div>
`

export const paymentEntryConfig = {
  doctype: 'Payment Entry',
  timeline: 'full',
  submitConfirm: paymentEntrySubmitConfirm,
  cancelConfirm: paymentEntryCancelConfirm,
  // Rejected entries are frozen (payment_entry.py's validate).
  locked: (d) => d.hidden.verification_status === 'Rejected',
  // Once a Payment Entry is tied to a Sales Order's payment term,
  // verification_status (Pending Verification / Verified / Rejected) is
  // the status that actually matters — plain docstatus stays "Submitted"
  // throughout that whole review, telling the viewer nothing. A Payment
  // Entry with no payment_term isn't part of that flow, so it keeps the
  // ordinary Draft/Submitted/Cancelled badge.
  statusField: (d) => (d.hidden.payment_term_row ? 'verification_status' : null),
  // The generic "submit this to confirm" draft banner is redundant once
  // Rejected already has its own (locked, verification_status badge) —
  // only suppress it for that specific state, not for every draft.
  hideDraftNotice: (d) => d.hidden.verification_status === 'Rejected',
  actions: [ledgerAction()],
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        strip([
          { label: 'Paid Amount', field: 'paid_amount' },
          { label: 'Allocated', field: 'total_allocated_amount' },
          { label: 'Unallocated', field: 'unallocated_amount' },
          { label: 'Difference', field: 'difference_amount', tone: (v) => (num(v) === 0 ? 'text-green-600' : 'text-red-600') },
        ]),
        fields(['naming_series', 'payment_type', 'posting_date', 'company', 'mode_of_payment', 'party_type', 'party', 'party_name', 'payer_account_name'], 'Payment'),
        { type: 'component', component: PaymentEntryAssist },
        fields(
          ['paid_from', 'paid_from_account_currency', 'paid_to', 'paid_to_account_currency', 'currency', 'conversion_rate', 'paid_amount', 'base_paid_amount'],
          'Accounts & Amount',
          {
            linkQueries: (ctx) => ({
              paid_from: paidAccountFilters(['Pay', 'Internal Transfer'])(ctx),
              paid_to: paidAccountFilters(['Receive', 'Internal Transfer'])(ctx),
            }),
          },
        ),
        table('references'),
        table('deductions'),
        // NOTE: not converted to grid() — Payment Entry's taxes table was
        // out of scope for this pass (only Sales Invoice / Purchase
        // Invoice / Sales Order / Purchase Order were asked for). It's the
        // same shared child doctype and would benefit from the same
        // treatment (taxesReadOnlyColumns / taxesFieldChange) — flagging
        // for a follow-up rather than changing it here.
        {
          ...table('taxes', { linkQueries: taxAccountLinkQueries }),
          show: (d) => ['Supplier', 'Customer'].includes(d.values.party_type),
        },
        fields(['reference_no', 'reference_date', 'clearance_date', 'remarks', 'is_opening'], 'Reference'),
      ],
    },
  ],
}

const invoiceActions = (payTo) => [
  ledgerAction(),
  {
    component: DocAction,
    props: {
      label: 'Payment Entry',
      icon: 'credit-card',
      method: 'verp_staffing.accounts.doctype.payment_entry.payment_entry.make_payment_entry',
      args: { source_name: '$name' },
      create: 'Payment Entry',
      success: `Payment Entry drafted for this ${payTo} invoice.`,
    },
    show: (d) => notNew(d) && submitted(d) && num(d.values.outstanding_amount) > 0,
  },
]

export const salesInvoiceConfig = {
  doctype: 'Sales Invoice',
  timeline: 'full',
  autoCalculate: true,
  statusText: invoiceStatusText,
  actions: [
    ...invoiceActions('sales'),
    {
      component: DocAction,
      props: {
        label: 'Send Invoice',
        icon: 'send',
        method: 'verp_staffing.accounts.doctype.sales_invoice.sales_invoice.send_sales_invoice_email',
        args: { doc: '$name' },
        confirm: 'Send this Sales Invoice by email to the customer?',
        success: 'Invoice sent successfully.',
        then: 'stay',
      },
      show: (d) => notNew(d) && submitted(d),
    },
  ],
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        strip([
          { label: 'Grand Total', field: 'grand_total' },
          { label: 'Outstanding', field: 'outstanding_amount', tone: (v) => (num(v) > 0 ? 'text-orange-600' : 'text-green-600') },
          { label: 'Net Total', field: 'net_total' },
          { label: 'Taxes', field: 'total_taxes_and_charges' },
        ]),
        fields(['naming_series', 'customer', 'company', 'posting_date', 'due_date', 'sales_order', 'update_outstanding_for_self'], 'Invoice'),
        fields(['currency', 'conversion_rate', 'tax_category'], 'Currency'),
        auto('items', { hiddenColumns: ['income_account'], onFieldChange: salesItemsFieldChange, rowLinkQueries: uniqueItemQuery }),
        grid('taxes', TAXES_GRID_COLUMNS, {
          readOnlyColumns: taxesReadOnlyColumns,
          onFieldChange: taxesFieldChange,
          linkQueries: taxAccountLinkQueries,
        }),
        fields(['additional_discount_percentage', 'discount_amount', 'additional_discount_account', 'disable_rounded_total'], 'Discount & Rounding', {
          linkQueries: discountAccountLinkQueries,
        }),
        fields(['debit_to', 'cash_bank_account', 'is_paid'], 'Accounting'),
        // depends_on for the currency-mismatch-only base_* fields (see
        // handle_currency_ui/toggle_base_fields in the old desk script)
        // belongs on the DocType field itself, not here — DocDetailView
        // already runs every field through dependsOnPasses before this
        // fieldnames list is applied, so setting
        // depends_on: "eval:doc.currency && doc.company_currency &&
        // doc.currency != doc.company_currency" on base_total,
        // base_net_total, base_grand_total (and base_rounded_total /
        // base_discount_amount / base_total_taxes_and_charges /
        // base_rounding_adjustment / base_in_words if you want full parity
        // with desk — they're not all listed below yet) is sufficient with
        // no frontend change. Add the missing base_* fieldnames to this
        // list once that's done, or they'll stay hidden regardless of
        // depends_on.
        fields(TOTALS_FIELDS, 'Totals'),
      ],
    },
  ],
}

export const purchaseInvoiceConfig = {
  doctype: 'Purchase Invoice',
  timeline: 'full',
  autoCalculate: true,
  actions: invoiceActions('purchase'),
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        strip([
          { label: 'Grand Total', field: 'grand_total' },
          { label: 'Outstanding', field: 'outstanding_amount', tone: (v) => (num(v) > 0 ? 'text-orange-600' : 'text-green-600') },
          { label: 'Net Total', field: 'net_total' },
          { label: 'Taxes', field: 'total_taxes_and_charges' },
        ]),
        fields(['naming_series', 'supplier', 'company', 'posting_date', 'due_date', 'bill_no', 'bill_date', 'purchase_order', 'is_paid', 'update_outstanding_for_self'], 'Invoice'),
        fields(['currency', 'conversion_rate', 'tax_category'], 'Currency'),
        auto('items', { hiddenColumns: ['expense_account'], onFieldChange: purchaseItemsFieldChange, rowLinkQueries: uniqueItemQuery }),
        grid('taxes', TAXES_GRID_COLUMNS, {
          readOnlyColumns: taxesReadOnlyColumns,
          onFieldChange: taxesFieldChange,
          linkQueries: taxAccountLinkQueries,
        }),
        fields(['additional_discount_percentage', 'discount_amount', 'additional_discount_account', 'disable_rounded_total'], 'Discount & Rounding', {
          linkQueries: discountAccountLinkQueries,
        }),
        fields(['credit_to', 'cashbank_account', 'mode_of_payment', 'is_opening'], 'Accounting'),
        // Same depends_on note as salesInvoiceConfig above applies here.
        fields([...TOTALS_FIELDS, 'total_advance'], 'Totals'),
      ],
    },
  ],
}

export const salesOrderConfig = {
  doctype: 'Sales Order',
  timeline: 'full',
  autoCalculate: true,
  allowOnSubmitEdit: true,
  actions: [{ component: SendDetailsFormAction, show: notNew }],
  // Sales Order's own `status` (Open/Closed, server-computed) only ever
  // matters once it reads "Closed" — otherwise the ordinary Draft/
  // Submitted/Cancelled docstatus badge tells the fuller story.
  statusField: (d) => (d.values.status === 'Closed' ? 'status' : null),
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        fields(['customer', 'posting_date', 'conversion_rate'], 'Order'),
        auto('items', { hiddenColumns: ['income_account'], onFieldChange: salesItemsFieldChange, rowLinkQueries: uniqueItemQuery }),
        grid('taxes', TAXES_GRID_COLUMNS, {
          readOnlyColumns: taxesReadOnlyColumns,
          onFieldChange: taxesFieldChange,
          linkQueries: taxAccountLinkQueries,
        }),
        fields(['additional_discount_percentage', 'discount_amount', 'additional_discount_account', 'disable_rounded_total'], 'Discount & Rounding', {
          linkQueries: discountAccountLinkQueries,
        }),
        fields(TOTALS_FIELDS, 'Totals'),
      ],
    },
    {
      key: 'payments',
      label: 'Invoices and Payments',
      show: notNew,
      sections: [
        { type: 'component', component: PaymentTermsField },
        { type: 'component', component: LinkedInvoicesPanel },
      ],
    },
    { key: 'agreements', label: 'Agreements', show: (d) => notNew(d) && agreementRequired(d), sections: [{ type: 'component', component: AgreementPanel }] },
  ],
}

export const purchaseOrderConfig = {
  doctype: 'Purchase Order',
  timeline: 'full',
  autoCalculate: true,
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        strip([
          { label: 'Grand Total', field: 'grand_total' },
          { label: 'Billed', field: 'per_billed', type: 'text' },
          { label: 'Received', field: 'per_received', type: 'text' },
          { label: 'Status', field: 'status', type: 'text' },
        ]),
        fields(['naming_series', 'supplier', 'company', 'posting_date', 'schedule_date', 'currency', 'conversion_rate'], 'Order'),
        auto('items', { hiddenColumns: ['expense_account'], onFieldChange: purchaseItemsFieldChange, rowLinkQueries: uniqueItemQuery }),
        grid('taxes', TAXES_GRID_COLUMNS, {
          readOnlyColumns: taxesReadOnlyColumns,
          onFieldChange: taxesFieldChange,
          linkQueries: taxAccountLinkQueries,
        }),
        fields(['tax_category', 'additional_discount_percentage', 'discount_amount', 'additional_discount_account', 'disable_rounded_total'], 'Discount & Rounding', {
          linkQueries: discountAccountLinkQueries,
        }),
        fields([...TOTALS_FIELDS, 'total_advance', 'outstanding_amount'], 'Totals'),
      ],
    },
  ],
}

export const supplierConfig = {
  doctype: 'Supplier',
  timeline: 'full',
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        fields(['supplier_name', 'supplier_type', 'supplier_group', 'country', 'is_transporter', 'disabled'], 'Supplier'),
        fields(['default_currency', 'default_bank_account', 'tax_category', 'tax_id', 'supplier_details'], 'Defaults & Tax'),
      ],
    },
    { key: 'contacts', label: 'Address & Contact', show: notNew, sections: [{ type: 'component', component: AddressContactPanel }] },
  ],
}

// ─── Subscriptions ────────────────────────────────────────────────────

export const subscriptionConfig = {
  doctype: 'Subscription',
  timeline: 'full',
  actions: [
    {
      component: DocAction,
      props: {
        label: 'Generate Invoice Now',
        icon: 'file-plus',
        method: 'verp_staffing.accounts.doctype.subscription.subscription.generate_invoice_now',
        args: { subscription: '$name' },
        confirm: 'Generate the next invoice for this subscription now?',
        success: 'Invoice generated.',
      },
      show: (d) => notNew(d) && submitted(d) && ['Active', 'Trialing'].includes(d.hidden.status),
    },
    {
      component: DocAction,
      props: {
        label: 'Pause Subscription',
        icon: 'pause',
        method: 'run_doc_method',
        args: { dt: '$doctype', dn: '$name', method: 'pause_subscription' },
        prompt: [{ fieldname: 'resume_date', label: 'Resume On', type: 'date', required: true }],
        nestPrompt: 'args',
        success: 'Subscription paused.',
      },
      show: (d) => notNew(d) && submitted(d) && !Number(d.hidden.is_paused) && !['Trialing', 'Cancelled', 'Completed'].includes(d.hidden.status),
    },
    {
      component: DocAction,
      props: {
        label: 'Resume Subscription',
        icon: 'play',
        method: 'run_doc_method',
        args: { dt: '$doctype', dn: '$name', method: 'resume_subscription' },
        confirm: 'Resume this subscription?',
        success: 'Subscription resumed.',
      },
      show: (d) => notNew(d) && submitted(d) && Number(d.hidden.is_paused) === 1,
    },
    {
      component: DocAction,
      props: {
        label: 'Cancel Subscription',
        icon: 'x-circle',
        variant: 'outline',
        method: 'run_doc_method',
        args: { dt: '$doctype', dn: '$name', method: 'cancel_subscription' },
        confirm: 'This will cancel the subscription immediately. Continue?',
        success: 'Subscription cancelled.',
      },
      show: (d) => notNew(d) && submitted(d) && !['Cancelled', 'Completed'].includes(d.hidden.status),
    },
  ],
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        fields(['subscription_type', 'party_type', 'party', 'company', 'cancelation_date'], 'Subscription'),
        fields(['plan', 'qty', 'start_date', 'end_date', 'trial_period_end'], 'Plan & Period'),
        table('one_time_charges'),
        table('discount_schedule'),
        table('taxes'),
        fields(['generate_invoice_at', 'number_of_days', 'days_until_due', 'auto_submit_invoice_check', 'cancel_at_period_end'], 'Invoice Generation'),
        fields(['additional_discount_account', 'net_total'], 'Totals'),
      ],
    },
  ],
}

export const subscriptionPlanConfig = {
  doctype: 'Subscription Plan',
  timeline: 'full',
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [fields(['plan_name', 'item', 'is_active', 'currency', 'rate', 'billing_interval', 'billing_interval_count'], 'Plan')],
    },
  ],
}

// Agreement (an order's filled-in PDF): mostly read-only — it's produced from
// the Sales Order's Agreements tab. agreement.js's only button is Download.
export const agreementConfig = {
  doctype: 'Agreement',
  timeline: 'full',
  noDelete: true,
  actions: [
    {
      component: DocAction,
      props: {
        label: 'Download Agreement',
        icon: 'download',
        method: 'verp_staffing.crm.api.agreement.download_agreement',
        args: { agreement: '$name' },
        then: 'open-file',
      },
      show: notNew,
    },
  ],
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        { type: 'fields', fieldnames: ['sales_order', 'template', 'status', 'sent_on', 'last_reminder_sent', 'certificate_id', 'signature_image', 'pdf'] },
      ],
    },
  ],
}
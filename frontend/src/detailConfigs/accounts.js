import AddressContactPanel from '@/components/detail/AddressContactPanel.vue'
import DocAction from '@/components/detail/DocAction.vue'
import NoticeBanner from '@/components/common/NoticeBanner.vue'
import LinkAction from '@/components/detail/LinkAction.vue'
import SummaryStrip from '@/components/detail/SummaryStrip.vue'
import AgreementPanel from '@/components/detail/accounts/AgreementPanel.vue'
import SendDetailsFormAction from '@/components/detail/accounts/SendDetailsFormAction.vue'
import JournalQuickEntryAction from '@/components/detail/accounts/JournalQuickEntryAction.vue'
import OutstandingInvoicesPanel from '@/components/detail/accounts/OutstandingInvoicesPanel.vue'
import LinkedInvoicesPanel from '@/components/detail/accounts/LinkedInvoicesPanel.vue'
import PaymentEntryAssist from '@/components/detail/accounts/PaymentEntryAssist.vue'
import PaymentTermsPanel from '@/components/detail/accounts/PaymentTermsPanel.vue'

const notNew = (d) => !d.isNew.value
const submitted = (d) => d.docstatus.value === 1
const num = (v) => Number(v) || 0
const sum = (rows, key) => (rows || []).reduce((s, r) => s + num(r[key]), 0)

const strip = (items) => ({ type: 'component', component: SummaryStrip, props: { items } })
const fields = (fieldnames, title) => ({ type: 'fields', fieldnames, title })
const table = (fieldname, extra = {}) => ({ type: 'table', fieldname, ...extra })

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

export const paymentEntryConfig = {
  doctype: 'Payment Entry',
  timeline: 'full',
  // Rejected entries are frozen (payment_entry.py's validate).
  locked: (d) => d.hidden.verification_status === 'Rejected',
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
        fields(['paid_from', 'paid_from_account_currency', 'paid_to', 'paid_to_account_currency', 'currency', 'conversion_rate', 'paid_amount', 'base_paid_amount'], 'Accounts & Amount'),
        table('references'),
        table('deductions'),
        { ...table('taxes'), show: (d) => ['Supplier', 'Customer'].includes(d.values.party_type) },
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
        table('items'),
        table('taxes'),
        fields(['additional_discount_percentage', 'discount_amount', 'additional_discount_account', 'disable_rounded_total'], 'Discount & Rounding'),
        fields(['debit_to', 'cash_bank_account', 'is_paid', 'paid_amount'], 'Accounting'),
        fields(['total_qty', 'total', 'base_total', 'net_total', 'base_net_total', 'grand_total', 'base_grand_total', 'rounding_adjustment', 'rounded_total', 'in_words'], 'Totals'),
      ],
    },
  ],
}

export const purchaseInvoiceConfig = {
  doctype: 'Purchase Invoice',
  timeline: 'full',
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
        table('items'),
        table('taxes'),
        fields(['additional_discount_percentage', 'discount_amount', 'additional_discount_account', 'disable_rounded_total'], 'Discount & Rounding'),
        fields(['credit_to', 'cashbank_account', 'mode_of_payment', 'paid_amount', 'is_opening'], 'Accounting'),
        fields(['total_qty', 'total', 'base_total', 'net_total', 'base_net_total', 'grand_total', 'base_grand_total', 'rounding_adjustment', 'rounded_total', 'in_words', 'total_advance'], 'Totals'),
      ],
    },
  ],
}

export const salesOrderConfig = {
  doctype: 'Sales Order',
  timeline: 'full',
  actions: [{ component: SendDetailsFormAction, show: notNew }],
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        strip([
          { label: 'Grand Total', field: 'grand_total' },
          { label: 'Outstanding', field: 'outstanding_amount', tone: (v) => (num(v) > 0 ? 'text-orange-600' : 'text-green-600') },
          { label: 'Status', field: 'status', type: 'text' },
        ]),
        fields(['customer', 'posting_date', 'currency', 'conversion_rate'], 'Order'),
        table('items'),
        table('payment_terms'),
        table('taxes'),
        fields(['additional_discount_percentage', 'discount_amount', 'additional_discount_account', 'disable_rounded_total'], 'Discount & Rounding'),
        fields(['total_qty', 'total', 'net_total', 'total_taxes_and_charges', 'grand_total', 'rounding_adjustment', 'rounded_total', 'in_words'], 'Totals'),
      ],
    },
    { key: 'payments', label: 'Payments', show: notNew, sections: [{ type: 'component', component: PaymentTermsPanel }] },
    { key: 'agreements', label: 'Agreements', show: notNew, sections: [{ type: 'component', component: AgreementPanel }] },
    { key: 'invoices', label: 'Invoices', show: notNew, sections: [{ type: 'component', component: LinkedInvoicesPanel }] },
  ],
}

export const purchaseOrderConfig = {
  doctype: 'Purchase Order',
  timeline: 'full',
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
        table('items'),
        table('taxes'),
        fields(['tax_category', 'additional_discount_percentage', 'discount_amount', 'additional_discount_account', 'disable_rounded_total'], 'Discount & Rounding'),
        fields(['total_qty', 'total', 'net_total', 'total_taxes_and_charges', 'grand_total', 'rounding_adjustment', 'rounded_total', 'in_words', 'total_advance', 'outstanding_amount'], 'Totals'),
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

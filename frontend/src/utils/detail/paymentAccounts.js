// Ported from the old desk payment_entry.js's set_query("paid_from"/
// "paid_to"). Frappe's standard Party Type records fix each type's
// account_type (Customer → Receivable, Supplier → Payable, Employee →
// Payable, Shareholder → Equity) — hardcoded here rather than round-tripped
// from the server, the same shortcut a synchronous linkQueries resolver
// needs. Shared so every place that offers a Paid From/Paid To picker
// (Payment Entry's own detail page, and the Verify dialog on the Payment
// Verification queue) filters identically, not two near-copies that can
// drift apart.
const PARTY_ACCOUNT_TYPE = { Customer: 'Receivable', Supplier: 'Payable', Employee: 'Payable', Shareholder: 'Equity' }

export function paidAccountFilterFor({ partyType, paymentType, company, bankCashPaymentTypes }) {
  const partyAccountType = PARTY_ACCOUNT_TYPE[partyType] || 'Receivable'
  const accountTypes = bankCashPaymentTypes.includes(paymentType)
    ? ['Bank', 'Cash']
    : [partyAccountType, ...(partyType === 'Shareholder' ? ['Equity'] : [])]
  return { filters: { account_type: ['in', accountTypes], is_group: 0, disabled: 0, company } }
}

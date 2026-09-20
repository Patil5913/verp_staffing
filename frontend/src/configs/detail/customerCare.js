import AssignToField from '@/components/detail/AssignToField.vue'
import CustomerContextPanel from '@/components/detail/customer/CustomerContextPanel.vue'
import CustomerHistoryPanel from '@/components/detail/customer/CustomerHistoryPanel.vue'
import CustomerSalesOrdersPanel from '@/components/detail/customer/CustomerSalesOrdersPanel.vue'
import ForwardAction from '@/components/detail/actions/ForwardAction.vue'
import ResolutionActions from '@/components/detail/actions/ResolutionActions.vue'
import CreateSalesOrderAction from '@/components/detail/actions/CreateSalesOrderAction.vue'

const notNew = (detail) => !detail.isNew.value

// The `status` field on CR / Onboardings is hidden and derived from the
// latest history row, so that row is the source of truth for "is this case
// still open" (see cr.py / onboardings.py sync_history).
const latestStatus = (detail, field) => {
  const rows = detail.values[field] || []
  return rows.length ? rows[rows.length - 1].status : ''
}

// Both doctypes are made by forwarding a candidate, not by hand, so there's
// no Add New in their lists (see listOptions.js) — this page is for working
// the case: assign it, resolve it, and read the customer's context.
const CUSTOMER_INFO_FIELDS = [
  'agreement_link', 'signature_image', 'my_electronic_signature_has_same_effect_as_handwritten',
  'i_consent_to_receive_sign_and_store_documents_electronically', 'i_confirm_my_identity_and_signing_this_document_intentionally',
  'surname', 'first_name', 'father_name', 'personal_phone_number', 'email', 'personal_linkedin', 'date_of_birth',
  'educational_details', 'past_experience_table', 'technologies', 'additional_skills', 'entry_date', 'current_address',
  'address_history', 'certificate_or_completed_course', 'current_visa_status', 'experience', 'number_for_marketing',
  'google_voice_number', 'marketing_linkedin', 'passport_number', 'ssn_digit', 'availability_for_interview', 'remarks',
  'visa_copy', 'ead_card', 'driving_licence', 'old_resume',
]

const customerTabs = (extraFields = []) => [
  {
    key: 'customer',
    label: 'Customer Information',
    show: notNew,
    sections: [
      { type: 'component', component: CustomerContextPanel, props: { fixedFields: [...CUSTOMER_INFO_FIELDS, ...extraFields], title: 'Customer Information' } },
    ],
  },
  { key: 'history', label: 'History', show: notNew, sections: [{ type: 'component', component: CustomerHistoryPanel }] },
  { key: 'sales-order', label: 'Sales Order', show: notNew, sections: [{ type: 'component', component: CustomerSalesOrdersPanel }] },
]

export const crConfig = {
  doctype: 'CR',
  timeline: false,
  // A resolved / refunded case is read-only (cr.js: disable_form()).
  locked: (detail) => notNew(detail) && !!latestStatus(detail, 'cr_history') && latestStatus(detail, 'cr_history') !== 'Dispute Pending',
  readOnlyFields: (detail) => (detail.isNew.value ? [] : ['customer']),
  actions: [
    {
      component: ResolutionActions,
      props: {
        historyField: 'cr_history',
        openStatus: 'Dispute Pending',
        method: 'verp_staffing.cr.doctype.cr.cr.resolve_or_refund_cr',
        nameArg: 'cr_name',
        options: [
          { label: 'Resolve', action: 'Dispute Resolved', remarks: true, icon: 'check-circle', variant: 'primary' },
          { label: 'Refund', action: 'Refund', remarks: true, icon: 'rotate-ccw', variant: 'outline' },
        ],
      },
    },
    // Only once the dispute is closed can the candidate be sent elsewhere.
    {
      component: ForwardAction,
      props: { fromServiceName: 'CR' },
      show: (d) => notNew(d) && !!latestStatus(d, 'cr_history') && latestStatus(d, 'cr_history') !== 'Dispute Pending',
    },
  ],
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        { type: 'fields', fieldnames: ['customer'] },
        { type: 'component', component: AssignToField, props: { filters: { department: 'CR' } } },
        { type: 'table', fieldname: 'cr_history', readOnly: true },
      ],
    },
    ...customerTabs(),
  ],
}

export const onboardingsConfig = {
  doctype: 'Onboardings',
  timeline: false,
  locked: (detail) => notNew(detail) && !!latestStatus(detail, 'onboarding_history') && latestStatus(detail, 'onboarding_history') !== 'Active',
  readOnlyFields: (detail) => (detail.isNew.value ? [] : ['customer']),
  actions: [
    {
      component: ResolutionActions,
      props: {
        historyField: 'onboarding_history',
        openStatus: 'Active',
        method: 'verp_staffing.onboarding.doctype.onboardings.onboardings.resolve_onboarding',
        nameArg: 'onboarding_name',
        options: [
          { label: 'Mark Completed', action: 'Completed', icon: 'check-circle', variant: 'primary' },
          { label: 'Mark Returned', action: 'Returned', icon: 'corner-up-left', variant: 'outline' },
        ],
      },
    },
    {
      component: ForwardAction,
      props: { fromServiceName: 'Onboarding' },
      show: (d) => notNew(d) && latestStatus(d, 'onboarding_history') === 'Returned',
    },
    { component: CreateSalesOrderAction, show: notNew },
  ],
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        { type: 'fields', fieldnames: ['customer'] },
        { type: 'component', component: AssignToField, props: { filters: { department: 'Onboarding' } } },
        { type: 'table', fieldname: 'contact_references' },
        { type: 'table', fieldname: 'documents' },
        { type: 'table', fieldname: 'onboarding_history', readOnly: true },
      ],
    },
    ...customerTabs(['marketing_email_id', 'marketing_email_password']),
  ],
}

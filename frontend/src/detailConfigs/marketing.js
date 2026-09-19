import AssignToField from '@/components/detail/AssignToField.vue'
import CustomerContextPanel from '@/components/detail/CustomerContextPanel.vue'
import CustomerHistoryPanel from '@/components/detail/CustomerHistoryPanel.vue'
import ForwardAction from '@/components/detail/ForwardAction.vue'
import ServiceResumePanel from '@/components/detail/ServiceResumePanel.vue'
import CreateInterviewButton from '@/components/detail/marketing/CreateInterviewButton.vue'
import FieldUpdateActions from '@/components/detail/fieldUpdate/FieldUpdateActions.vue'
import InterviewRoundsField from '@/components/detail/marketing/InterviewRoundsField.vue'
import JobApplicationGrid from '@/components/detail/marketing/JobApplicationGrid.vue'
import MarketingInterviewsPanel from '@/components/detail/marketing/MarketingInterviewsPanel.vue'
import MarketingTargetPanel from '@/components/detail/marketing/MarketingTargetPanel.vue'

const isCompleted = (detail) => detail.values.status === 'Completed'
const notNew = (detail) => !detail.isNew.value

// Ported from marketing.js: the assignee, target block and per-day job
// application counts, the interviews raised from this record, and (on their
// own tabs) the customer's resume/lead data and full department history.
export const marketingConfig = {
  doctype: 'Marketing',
  timeline: 'service',
  // status locks once Completed; the customer can't be re-picked after the
  // record exists (marketing.js sets it read_only when !is_new()).
  readOnlyFields: (detail) => [
    ...(isCompleted(detail) ? ['status'] : []),
    ...(detail.isNew.value ? [] : ['customer']),
  ],
  actions: [
    { component: CreateInterviewButton, show: notNew },
    { component: ForwardAction, props: { fromServiceName: 'Marketing' } },
    { component: FieldUpdateActions, props: { mode: 'service' }, show: notNew },
  ],
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        { type: 'fields', fieldnames: ['customer', 'status'] },
        {
          type: 'component',
          component: AssignToField,
          props: { query: 'verp_staffing.crm.api.helpers.get_assign_to_by_service', filters: { service: 'Marketing' }, withCustomer: true },
        },
        { type: 'component', component: MarketingInterviewsPanel, show: notNew },
        { type: 'component', component: MarketingTargetPanel },
        { type: 'component', component: JobApplicationGrid },
      ],
    },
    {
      key: 'customer',
      label: 'Customer',
      show: notNew,
      sections: [
        { type: 'component', component: ServiceResumePanel },
        { type: 'component', component: CustomerContextPanel, props: { displayKey: 'Marketing' } },
      ],
    },
    {
      key: 'history',
      label: 'History',
      show: notNew,
      sections: [{ type: 'component', component: CustomerHistoryPanel }],
    },
  ],
}

export const interviewConfig = {
  doctype: 'Interview',
  timeline: false,
  // Once created, everything but the rounds is fixed (interview.js sets
  // customer/role/company/status read_only on existing records).
  readOnlyFields: (detail) => (detail.isNew.value ? ['status'] : ['customer', 'role', 'company', 'status']),
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        { type: 'fields', fieldnames: ['marketing_link'], show: (d) => d.isNew.value },
        { type: 'fields', fieldnames: ['company', 'role', 'status', 'customer'] },
        { type: 'component', component: ServiceResumePanel, show: notNew },
        { type: 'component', component: InterviewRoundsField },
      ],
    },
  ],
}

// Marketing Other Services / Other Services share one shape: a customer's
// service request with proof-of-work documents, locked once Completed.
export function otherServicesConfig({ doctype, department }) {
  return {
    doctype,
    timeline: 'service',
    locked: isCompleted,
    readOnlyFields: (detail) => (detail.isNew.value ? [] : ['customer', 'service', 'department']),
    actions: [
      { component: ForwardAction, props: { serviceField: 'service' } },
      { component: FieldUpdateActions, props: { mode: 'service' }, show: notNew },
    ],
    tabs: [
      {
        key: 'details',
        label: 'Details',
        sections: [
          { type: 'fields', fieldnames: ['customer', 'service', 'department', 'status', 'forwarded_on', 'completed_on'] },
          {
            type: 'component',
            component: AssignToField,
            props: {
              query: 'verp_staffing.crm.api.helpers.get_subordinate_employees',
              ...(department ? { filters: { department } } : { departmentField: 'department' }),
            },
          },
          { type: 'component', component: ServiceResumePanel, show: notNew },
        ],
      },
      { key: 'proof-of-work', label: 'Proof Of Work', show: notNew, sections: [{ type: 'table', fieldname: 'proof_of_work' }] },
      {
        key: 'customer',
        label: 'Customer',
        show: notNew,
        sections: [{ type: 'component', component: CustomerContextPanel, props: { displayKeyField: 'service' } }],
      },
    ],
  }
}

export const marketingOtherServicesConfig = otherServicesConfig({ doctype: 'Marketing Other Services', department: 'Marketing' })

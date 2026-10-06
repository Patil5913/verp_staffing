import { hasRole } from '@/utils/common/roles'
import { watch } from 'vue'
import { call } from 'frappe-ui'
import { notify } from '@/utils/common/notify'
import AssignToField from '@/components/detail/AssignToField.vue'
import CustomerContextPanel from '@/components/detail/customer/CustomerContextPanel.vue'
import CustomerHistoryPanel from '@/components/detail/customer/CustomerHistoryPanel.vue'
import ForwardAction from '@/components/detail/actions/ForwardAction.vue'
import ServiceResumePanel from '@/components/detail/lead/ServiceResumePanel.vue'
import CreateInterviewButton from '@/components/detail/marketing/CreateInterviewButton.vue'
import FieldUpdateActions from '@/components/detail/fieldUpdate/FieldUpdateActions.vue'
import InterviewRoundsField from '@/components/detail/marketing/InterviewRoundsField.vue'
import JobApplicationGrid from '@/components/detail/marketing/JobApplicationGrid.vue'
import MarketingInterviewsPanel from '@/components/detail/marketing/MarketingInterviewsPanel.vue'
import MarketingTargetPanel from '@/components/detail/marketing/MarketingTargetPanel.vue'
import { autoTitleFromFile } from '@/utils/detail/documentTitle'

const isCompleted = (detail) => detail.values.status === 'Completed' && !hasRole('System Manager')
const notNew = (detail) => !detail.isNew.value

// Ported from marketing.js: the assignee, target block and per-day job
// application counts, the interviews raised from this record, and (on their
// own tabs) the customer's resume/lead data and full department history.
export const marketingConfig = {
  doctype: 'Marketing',
  timeline: 'service',
  // Forwarded/auto-created off a Customer's own workflow - no manual delete.
  noDelete: true,
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
        {
          type: 'fields',
          fieldnames: ['customer', 'status'],
          // Placed is computed from the customer's services (set automatically), so it's shown
          // but never offered as a choice, and can't be edited by hand.
          fieldOverrides: (detail) => ({
            status: {
              options: 'Pending\nStarted\nCompleted\nHold',
              read_only: detail.values.status === 'Placed' ? 1 : 0,
            },
          }),
        },
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
      sections: [{ type: 'component', component: CustomerHistoryPanel, props: { includeInterviews: false } }],
    },
  ],
}

// interview.js's initialize_default_interview_status: a NEW Interview starts with the status
// set in ERP Configuration (Default Interview Status), unless it already has one.
function interviewSetup(detail) {
  watch(
    () => [detail.meta.resource.data, detail.isNew.value],
    async ([data, isNew]) => {
      if (!data || !isNew || detail.values.status) return
      const status = await call('frappe.client.get_single_value', { doctype: 'ERP Configuration', field: 'default_interview_status' }).catch(() => null)
      if (!status) {
        notify.error("Default Interview Status is not set in 'ERP Configuration', please contact admin.")
        return
      }
      if (!detail.values.status) detail.values.status = status
    },
    { immediate: true },
  )
}

export const interviewConfig = {
  doctype: 'Interview',
  timeline: false,
  setup: interviewSetup,
  // Once created, everything but the rounds is fixed (interview.js sets
  // role/company/status read_only on existing records). `customer` isn't
  // shown at all - it's purely derived from marketing_link, redundant next
  // to Company/Role, and used to show up (unhidden, unlike the doctype's
  // own display) on the create form specifically since this generic
  // renderer doesn't otherwise know to drop it.
  readOnlyFields: (detail) => (detail.isNew.value ? ['status'] : ['role', 'company', 'status']),
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        { type: 'fields', fieldnames: ['marketing_link'], show: (d) => d.isNew.value },
        { type: 'fields', fieldnames: ['company', 'role', 'status'] },
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
    // Forwarded/auto-created off a Customer's own workflow - no manual delete.
    noDelete: true,
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
      { key: 'proof-of-work', label: 'Proof Of Work', show: notNew, sections: [{ type: 'table', fieldname: 'proof_of_work', onFileMeta: autoTitleFromFile }] },
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

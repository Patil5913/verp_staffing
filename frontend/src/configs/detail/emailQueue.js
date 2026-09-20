import EmailQueueActions from '@/components/detail/emailQueue/EmailQueueActions.vue'
import EmailQueueError from '@/components/detail/emailQueue/EmailQueueError.vue'
import EmailQueueMessage from '@/components/detail/emailQueue/EmailQueueMessage.vue'

const notNew = (detail) => !detail.isNew.value

// Email Queue (Staffing Master): mail waiting to go out, or that failed. The
// system creates these — the page is a read-only view with Send now / Retry
// sending, like the desk form, and Delete for clearing one out.
export const emailQueueConfig = {
  doctype: 'Email Queue',
  timeline: false,
  locked: () => true,
  actions: [{ component: EmailQueueActions, show: notNew }],
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        { type: 'component', component: EmailQueueError },
        {
          type: 'fields',
          title: 'Delivery',
          fieldnames: ['status', 'sender', 'email_account', 'send_after', 'priority', 'retry', 'reference_doctype', 'reference_name', 'communication'],
        },
        { type: 'table', fieldname: 'recipients' },
      ],
    },
    { key: 'message', label: 'Message', show: notNew, sections: [{ type: 'component', component: EmailQueueMessage }] },
  ],
}

import ESignBuilder from '@/components/detail/esign/ESignBuilder.vue'
import ESignSendAction from '@/components/detail/esign/ESignSendAction.vue'
import ESignTracking from '@/components/detail/esign/ESignTracking.vue'
import NoticeBanner from '@/components/common/NoticeBanner.vue'

const notNew = (d) => !d.isNew.value
const sentOrDone = (d) => ['Sent', 'Fully Signed'].includes(d.values.status)

export const eSignConfig = {
  doctype: 'E Sign',
  timeline: 'full',
  // Once sent, the document and its fields are frozen (e_sign.js lock_editor).
  locked: (d) => notNew(d) && sentOrDone(d),
  actions: [{ component: ESignSendAction, show: (d) => notNew(d) && d.values.status === 'Draft' }],
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        { type: 'fields', title: 'Document', fieldnames: ['title', 'original_pdf', 'status', 'signed_pdf'] },
      ],
    },
    {
      key: 'document',
      label: 'Fields & Signers',
      show: notNew,
      sections: [
        {
          type: 'component',
          component: NoticeBanner,
          props: { tone: 'info', message: 'This document has been sent — its fields are locked.' },
          show: sentOrDone,
        },
        { type: 'component', component: ESignBuilder },
      ],
    },
    { key: 'tracking', label: 'Tracking', show: notNew, sections: [{ type: 'component', component: ESignTracking }] },
  ],
}

import { ref } from 'vue'
import { call } from 'frappe-ui'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

// Sending is one call for compose, reply, reply-all and forward - the server
// picks the sender from the user's own accounts (utils/mailbox.send_mail).
export function useSendMail() {
  const sending = ref(false)

  async function send({ to, cc = [], bcc = [], subject, content, inReplyTo = '', attachments = [], account = '' }) {
    sending.value = true
    try {
      const res = await call('verp_staffing.utils.mailbox.send_mail', {
        to: to.join(', '),
        cc: cc.join(', '),
        bcc: bcc.join(', '),
        subject,
        content,
        in_reply_to: inReplyTo || undefined,
        attachments: JSON.stringify(attachments),
        account: account || undefined,
      })
      notify.success('Message sent')
      return res
    } catch (e) {
      notify.error(normalizeError(e).message)
      return null
    } finally {
      sending.value = false
    }
  }

  return { send, sending }
}

import { describe, it, expect, vi, beforeEach } from 'vitest'

const { callMock, notifyMock } = vi.hoisted(() => ({ callMock: vi.fn(), notifyMock: { success: vi.fn(), error: vi.fn() } }))
vi.mock('frappe-ui', () => ({ call: (...a) => callMock(...a) }))
vi.mock('@/utils/common/notify', () => ({ notify: notifyMock }))

import { useSendMail } from '@/composables/mail/useSendMail'

beforeEach(() => { callMock.mockReset(); notifyMock.success.mockReset(); notifyMock.error.mockReset() })

describe('useSendMail', () => {
  it('sends with recipients joined and attachments as JSON', async () => {
    callMock.mockResolvedValue({ name: 'COMM-1' })
    const { send } = useSendMail()
    const res = await send({ to: ['a@x.com', 'b@x.com'], cc: ['c@x.com'], subject: 'S', content: '<p>hi</p>', attachments: ['F1'], account: 'Support' })
    expect(res).toEqual({ name: 'COMM-1' })
    expect(callMock).toHaveBeenCalledWith('verp_staffing.utils.mailbox.send_mail', {
      to: 'a@x.com, b@x.com', cc: 'c@x.com', bcc: '', subject: 'S', content: '<p>hi</p>',
      in_reply_to: undefined, attachments: '["F1"]', account: 'Support',
    })
    expect(notifyMock.success).toHaveBeenCalledWith('Message sent')
  })
  it('passes the reply target and omits a blank account', async () => {
    callMock.mockResolvedValue({})
    await useSendMail().send({ to: ['a@x.com'], subject: 'Re', content: '', inReplyTo: 'COMM-9' })
    const args = callMock.mock.calls[0][1]
    expect(args.in_reply_to).toBe('COMM-9')
    expect(args.account).toBeUndefined()
  })
  it('tracks the sending state and clears it afterwards', async () => {
    let release
    callMock.mockReturnValue(new Promise((r) => (release = r)))
    const { send, sending } = useSendMail()
    const p = send({ to: ['a@x.com'], subject: 'S', content: '' })
    expect(sending.value).toBe(true)
    release({})
    await p
    expect(sending.value).toBe(false)
  })
  it('returns null and shows the server message when sending fails', async () => {
    callMock.mockRejectedValue({ status: 417, messages: ['Add at least one recipient'] })
    const { send, sending } = useSendMail()
    expect(await send({ to: [], subject: '', content: '' })).toBeNull()
    expect(notifyMock.error).toHaveBeenCalledWith('Add at least one recipient')
    expect(notifyMock.success).not.toHaveBeenCalled()
    expect(sending.value).toBe(false)
  })
})

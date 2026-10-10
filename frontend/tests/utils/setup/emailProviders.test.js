import { describe, it, expect } from 'vitest'
import { EMAIL_PROVIDERS } from '@/utils/setup/emailProviders'

describe('EMAIL_PROVIDERS', () => {
  const keys = ['email_server', 'smtp_server', 'incoming_port', 'smtp_port', 'use_imap', 'use_ssl', 'use_tls', 'use_starttls', 'use_ssl_for_outgoing', 'append_emails_to_sent_folder', 'sent_folder_name']
  it.each(Object.entries(EMAIL_PROVIDERS))('%s has a full, consistent preset', (_k, p) => {
    expect(p.label).toBeTruthy()
    expect(Array.isArray(p.domains)).toBe(true)
    expect(Object.keys(p.defaults).sort()).toEqual([...keys].sort())
  })
  it('never combines ssl and starttls for outgoing', () => {
    for (const p of Object.values(EMAIL_PROVIDERS)) {
      expect(p.defaults.use_ssl_for_outgoing && p.defaults.use_starttls).toBeFalsy()
    }
  })
  it('domains are unique across providers', () => {
    const all = Object.values(EMAIL_PROVIDERS).flatMap((p) => p.domains)
    expect(new Set(all).size).toBe(all.length)
  })
  it('gmail matches gmail.com', () => expect(EMAIL_PROVIDERS.gmail.domains).toContain('gmail.com'))
})

import { describe, it, expect, vi, beforeEach } from 'vitest'

const { callMock } = vi.hoisted(() => ({ callMock: vi.fn() }))
vi.mock('frappe-ui', () => ({ call: (...a) => callMock(...a) }))

let usePortal, usePortalGate

beforeEach(async () => {
  callMock.mockReset()
  vi.resetModules()
  ;({ usePortal } = await import('@/composables/portal/usePortal'))
  ;({ usePortalGate } = await import('@/composables/portal/usePortalGate'))
})

describe('usePortalGate', () => {
  const answer = (form, agreements) =>
    callMock.mockImplementation(async (method) => {
      if (method.endsWith('get_lock_state')) return form
      return agreements
    })

  it('is open until checked', () => {
    const g = usePortalGate()
    expect(g.blocked.value).toBe(false)
    expect(g.checked.value).toBe(false)
  })
  it('blocks while the candidate form must be filled, and points at it', async () => {
    answer({ must_fill: true }, [])
    const g = usePortalGate()
    await g.refresh()
    expect(g.blocked.value).toBe(true)
    expect(g.mustFillForm.value).toBe(true)
    expect(g.gateTarget.value).toBe('/portal/candidate-details')
    expect(g.checked.value).toBe(true)
  })
  it('blocks on an unsigned agreement and points at agreements', async () => {
    answer({ must_fill: false }, [{ needs_signature: false }, { needs_signature: true }])
    const g = usePortalGate()
    await g.refresh()
    expect(g.mustSignAgreement.value).toBe(true)
    expect(g.gateTarget.value).toBe('/portal/agreements')
  })
  it('the form comes before agreements when both are pending', async () => {
    answer({ must_fill: true }, [{ needs_signature: true }])
    const g = usePortalGate()
    await g.refresh()
    expect(g.gateTarget.value).toBe('/portal/candidate-details')
  })
  it('is clear when nothing is pending, and a failed lookup does not lock the customer out', async () => {
    answer({ must_fill: false }, [])
    const g = usePortalGate()
    await g.refresh()
    expect(g.blocked.value).toBe(false)
    callMock.mockRejectedValue(new Error('x'))
    await g.refresh()
    expect(g.blocked.value).toBe(false)
  })
  it('only the form and agreement pages stay reachable while blocked', () => {
    const { isAllowedPath } = usePortalGate()
    expect(isAllowedPath('/portal/candidate-details')).toBe(true)
    expect(isAllowedPath('/portal/agreements')).toBe(true)
    expect(isAllowedPath('/portal/agreements/AG-1')).toBe(true)
    expect(isAllowedPath('/portal/dashboard')).toBe(false)
    expect(isAllowedPath('/portal/candidate-details-x/../y')).toBe(false)
  })
})

describe('usePortal', () => {
  const portalData = {
    other_service_doctypes: ['Other Services'],
    technical_doctypes: ['Resume'],
    feedback_rounds: [1, 2],
    pending_feedback_items: [1],
    chat_enabled: true,
    history: {
      departments: {
        'Sales Order': [{ status: 'Open' }],
        Interview: [{ status: 'Scheduled' }],
        Resume: [{ status: 'Completed' }],
        Marketing: [{ status: 'Pending' }, { status: 'Request for Update' }],
        'Other Services': [{ status: 'Started', service_name: 'Visa' }],
      },
    },
  }

  it('loads once and caches unless forced', async () => {
    callMock.mockResolvedValue(portalData)
    const p = usePortal()
    await p.load()
    await p.load()
    expect(callMock).toHaveBeenCalledTimes(1)
    await p.load(true)
    expect(callMock).toHaveBeenCalledTimes(2)
  })
  it('keeps a readable error when loading fails', async () => {
    callMock.mockRejectedValue({ messages: ['Customer not found'] })
    const p = usePortal()
    await p.load()
    expect(p.error.value).toBe('Customer not found')
    expect(p.loading.value).toBe(false)
    callMock.mockRejectedValue(new Error())
    await p.load()
    expect(p.error.value).toBe('Could not load your portal.')
  })
  it('services skip sales orders and interviews, and name other services by their own title', async () => {
    callMock.mockResolvedValue(portalData)
    const p = usePortal()
    await p.load()
    expect(p.services.value.map((s) => s.title)).toEqual(['Resume', 'Marketing', 'Marketing', 'Visa'])
    expect(p.services.value.find((s) => s.title === 'Visa').isOther).toBe(true)
  })
  it('technical services are split from the rest', async () => {
    callMock.mockResolvedValue(portalData)
    const p = usePortal()
    await p.load()
    expect(p.technicalServices.value.map((s) => s.dept)).toEqual(['Resume'])
    expect(p.generalServices.value).toHaveLength(3)
  })
  it('counts services by bucket and pending feedback', async () => {
    callMock.mockResolvedValue(portalData)
    const p = usePortal()
    await p.load()
    expect(p.counts.value).toEqual({ completed: 1, progress: 1, pending: 1, rework: 1 })
    expect(p.pendingCount.value).toBe(3)
  })
  it('no data means no services', () => {
    const p = usePortal()
    expect(p.services.value).toEqual([])
    expect(p.pendingCount.value).toBe(0)
  })
  it('interviews load once; a failure leaves an empty list and is not retried', async () => {
    callMock.mockResolvedValue({ departments: { Interview: [{ name: 'I1' }] } })
    const p = usePortal()
    await p.loadInterviews()
    await p.loadInterviews()
    expect(p.interviews.value).toEqual([{ name: 'I1' }])
    expect(callMock).toHaveBeenCalledTimes(1)
  })
  it('accounts fall back to an empty summary on failure', async () => {
    callMock.mockRejectedValue(new Error('x'))
    const p = usePortal()
    await p.loadAccounts()
    expect(p.accounts.value.totals.billed).toBe(0)
    expect(p.accounts.value.invoices).toEqual([])
  })
  it('unread count needs chat enabled and tolerates failure', async () => {
    const p = usePortal()
    await p.refreshUnread()
    expect(callMock).not.toHaveBeenCalled()
    callMock.mockResolvedValueOnce(portalData)
    await p.load()
    callMock.mockResolvedValueOnce('4')
    await p.refreshUnread()
    expect(p.unread.value).toBe(4)
    callMock.mockRejectedValueOnce(new Error('x'))
    await p.refreshUnread()
    expect(p.unread.value).toBe(4)
  })
  it('rejects uploads over 1 MB without calling the server', async () => {
    const p = usePortal()
    global.fetch = vi.fn()
    await expect(p.uploadDocument('visa', { size: 2 * 1024 * 1024 })).rejects.toThrow('under 1 MB')
    expect(fetch).not.toHaveBeenCalled()
  })
  it('a successful upload remembers the file name; a failure explains why', async () => {
    const p = usePortal()
    window.csrf_token = 't'
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ message: { status: 'success' } }) })
    await p.uploadDocument('visa', { size: 10, name: 'visa.pdf' })
    expect(p.docNames.visa).toBe('visa.pdf')
    expect(fetch.mock.calls[0][1].headers['X-Frappe-CSRF-Token']).toBe('t')
    global.fetch = vi.fn().mockResolvedValue({ ok: false, json: async () => ({ _server_messages: JSON.stringify([JSON.stringify({ message: 'Bad type' })]) }) })
    await expect(p.uploadDocument('visa', { size: 10, name: 'x.exe' })).rejects.toThrow('Bad type')
    global.fetch = vi.fn().mockResolvedValue({ ok: false, json: async () => { throw new Error() } })
    await expect(p.uploadDocument('visa', { size: 10, name: 'x' })).rejects.toThrow('Upload failed. Please try again.')
  })
})

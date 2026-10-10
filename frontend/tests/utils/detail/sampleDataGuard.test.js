import { describe, it, expect, vi, beforeEach } from 'vitest'

const callMock = vi.fn()
const confirmMock = vi.fn()
vi.mock('frappe-ui', () => ({ call: (...a) => callMock(...a) }))
vi.mock('@/utils/common/confirmDialog', () => ({ confirmLeave: (...a) => confirmMock(...a) }))

import { confirmSampleDataLinks } from '@/utils/detail/sampleDataGuard'

beforeEach(() => { callMock.mockReset(); confirmMock.mockReset(); delete window.is_sample_data_removed })

describe('confirmSampleDataLinks', () => {
  it('skips ERP Configuration and removed-sample sessions', async () => {
    expect(await confirmSampleDataLinks('ERP Configuration', {})).toBe(true)
    window.is_sample_data_removed = true
    expect(await confirmSampleDataLinks('Lead', {})).toBe(true)
    expect(callMock).not.toHaveBeenCalled()
  })
  it('never blocks when the check fails', async () => {
    callMock.mockRejectedValue(new Error('x'))
    expect(await confirmSampleDataLinks('Lead', {})).toBe(true)
  })
  it('no links -> true without a dialog', async () => {
    callMock.mockResolvedValue([])
    expect(await confirmSampleDataLinks('Lead', {})).toBe(true)
    expect(confirmMock).not.toHaveBeenCalled()
  })
  it('asks and escapes html', async () => {
    callMock.mockResolvedValue([{ label: 'L', value: '<img>', reference_doctype: 'Customer' }])
    confirmMock.mockResolvedValue(false)
    expect(await confirmSampleDataLinks('Lead', {})).toBe(false)
    const html = confirmMock.mock.calls[0][0].html
    expect(html).toContain('&lt;img&gt;')
    expect(html).not.toContain('<img>')
  })
})

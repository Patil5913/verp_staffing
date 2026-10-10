import { describe, it, expect, vi, beforeEach } from 'vitest'

const callMock = vi.fn()
vi.mock('frappe-ui', () => ({ call: (...a) => callMock(...a) }))

import { requestTitles, recordTitle, setRecordTitle } from '@/composables/common/useRecordTitles'

const tick = () => new Promise((r) => setTimeout(r, 10))

beforeEach(() => { callMock.mockReset() })

describe('useRecordTitles', () => {
  it('batches ids per doctype into one request and caches', async () => {
    callMock.mockResolvedValue({ a: 'Alpha' })
    requestTitles('Customer', ['a', 'b'])
    requestTitles('Customer', ['a', 'c'])
    await tick()
    expect(callMock).toHaveBeenCalledTimes(1)
    expect(callMock.mock.calls[0][1]).toEqual({ doctype: 'Customer', names: ['a', 'b', 'c'] })
    expect(recordTitle('Customer', 'a')).toBe('Alpha')
    expect(recordTitle('Customer', 'b')).toBe('')
    requestTitles('Customer', ['a', 'b'])
    await tick()
    expect(callMock).toHaveBeenCalledTimes(1)
  })
  it('a failed lookup leaves ids blank, not retried forever', async () => {
    callMock.mockRejectedValue(new Error('x'))
    requestTitles('User', ['u1'])
    await tick()
    expect(recordTitle('User', 'u1')).toBe('')
  })
  it('ignores junk input', async () => {
    requestTitles('', ['a'])
    requestTitles('Lead', [null, 5, ''])
    requestTitles('Lead', undefined)
    await tick()
    expect(callMock).not.toHaveBeenCalled()
  })
  it('setRecordTitle skips a lookup and ignores title equal to id', async () => {
    setRecordTitle('Quote', 'q1', 'Big Deal')
    setRecordTitle('Quote', 'q2', 'q2')
    setRecordTitle('', 'q3', 'x')
    requestTitles('Quote', ['q1', 'q2'])
    await tick()
    expect(callMock).not.toHaveBeenCalled()
    expect(recordTitle('Quote', 'q1')).toBe('Big Deal')
    expect(recordTitle('Quote', 'q2')).toBe('')
  })
})

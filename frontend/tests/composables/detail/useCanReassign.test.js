import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, nextTick } from 'vue'

const callMock = vi.fn()
vi.mock('frappe-ui', () => ({ call: (...a) => callMock(...a) }))

import { useCanReassign } from '@/composables/detail/useCanReassign'

const flush = async () => { await nextTick(); await new Promise((r) => setTimeout(r, 0)) }
beforeEach(() => { callMock.mockReset() })

describe('useCanReassign', () => {
  it('always true for a new record', async () => {
    const r = useCanReassign(ref('Lead'), ref('L1'), ref(true))
    await flush()
    expect(r.value).toBe(true)
    expect(callMock).not.toHaveBeenCalled()
  })
  it('follows the server', async () => {
    callMock.mockResolvedValue({ allowed: true })
    const r = useCanReassign(ref('Lead'), ref('L1'), ref(false), 'svc')
    await flush()
    expect(r.value).toBe(true)
    expect(callMock.mock.calls[0][1]).toEqual({ doctype: 'Lead', name: 'L1', service: 'svc' })
  })
  it('fails closed on error and on denial', async () => {
    callMock.mockRejectedValue(new Error('x'))
    const r = useCanReassign(ref('Lead'), ref('L1'), ref(false))
    await flush()
    expect(r.value).toBe(false)
    callMock.mockResolvedValue({ allowed: false })
    const r2 = useCanReassign(ref('Lead'), ref('L2'), ref(false))
    await flush()
    expect(r2.value).toBe(false)
  })
})

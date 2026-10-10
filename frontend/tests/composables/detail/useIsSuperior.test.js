import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, reactive, nextTick } from 'vue'

const h = vi.hoisted(() => ({ r: null }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: () => (h.r = reactive({ resource: { data: null, submit: vi.fn() }, isLoading: false })),
}))
import { useIsSuperior } from '@/composables/detail/useIsSuperior'

beforeEach(() => { window.user = 'me@x.com' })

describe('useIsSuperior', () => {
  it('fails closed until answered', () => {
    const { isSuperior } = useIsSuperior(ref(''), 'Marketing')
    expect(isSuperior.value).toBe(false)
    expect(h.r.resource.submit).not.toHaveBeenCalled()
  })
  it('asks the server when an assignee is set and when it changes', async () => {
    const a = ref('a@x.com')
    const { isSuperior } = useIsSuperior(a, 'Marketing')
    expect(h.r.resource.submit).toHaveBeenCalledWith({ assign_to: 'a@x.com', current_user: 'me@x.com', department: 'Marketing' })
    a.value = 'b@x.com'
    await nextTick()
    expect(h.r.resource.submit).toHaveBeenCalledTimes(2)
    h.r.resource.data = { is_superior: 1 }
    expect(isSuperior.value).toBe(true)
  })
})

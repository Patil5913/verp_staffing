import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, reactive, nextTick } from 'vue'

const h = vi.hoisted(() => ({ made: {}, notify: { success: vi.fn() } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (opts) => {
    const r = reactive({
      resource: { data: null, submit: vi.fn(async () => null), setData(d) { this.data = d } },
      isLoading: false, opts,
    })
    h.made[opts.url.split('.').pop()] = r
    return r
  },
}))
import { useUserRoles } from '@/composables/detail/useUserRoles'

beforeEach(() => { h.made = {}; h.notify.success.mockReset() })

describe('useUserRoles', () => {
  it('does not fetch until enabled', async () => {
    const enabled = ref(false)
    useUserRoles(ref('u'), enabled)
    expect(h.made.get_roles_matrix.resource.submit).not.toHaveBeenCalled()
    enabled.value = true
    await nextTick()
    expect(h.made.get_roles_matrix.resource.submit).toHaveBeenCalled()
    expect(h.made.get_roles_matrix.opts.makeParams()).toEqual({ user: 'u' })
  })

  it('ticks follow the server, toggling makes it dirty', async () => {
    const r = useUserRoles(ref('u'))
    expect(r.isDirty.value).toBe(false)
    h.made.get_roles_matrix.resource.data = { roles: ['A', 'B'], assigned: ['A'] }
    await nextTick()
    expect(r.allRoles.value).toEqual(['A', 'B'])
    expect([...r.checked.value]).toEqual(['A'])
    expect(r.isDirty.value).toBe(false)
    r.toggle('B')
    expect(r.isDirty.value).toBe(true)
    r.toggle('B')
    expect(r.isDirty.value).toBe(false)
    r.toggle('A')
    expect(r.isDirty.value).toBe(true)
  })

  it('submit saves the ticked roles and resolves true', async () => {
    const r = useUserRoles(ref('u'))
    h.made.get_roles_matrix.resource.data = { roles: ['A', 'B'], assigned: ['A'] }
    await nextTick()
    r.toggle('B')
    expect(await r.submit()).toBe(true)
    expect(h.made.set_user_roles.resource.submit).toHaveBeenCalledWith({ user: 'u', roles: ['A', 'B'] })
    expect(h.notify.success).toHaveBeenCalled()
    h.made.set_user_roles.opts.onSuccess({ roles: ['A', 'B'], assigned: ['A', 'B'] })
    expect(r.isDirty.value).toBe(false)
  })

  it('submit resolves false on failure', async () => {
    const r = useUserRoles(ref('u'))
    h.made.set_user_roles.resource.submit.mockRejectedValue(new Error('x'))
    expect(await r.submit()).toBe(false)
    expect(h.notify.success).not.toHaveBeenCalled()
  })
})

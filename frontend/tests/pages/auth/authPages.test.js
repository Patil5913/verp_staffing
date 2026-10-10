import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ route: { query: {} }, made: [], notify: { success: vi.fn(), error: vi.fn() } }))
vi.mock('vue-router', () => ({ useRoute: () => h.route }))
vi.mock('frappe-ui', () => ({
  ErrorMessage: { template: '<i />' }, Password: { template: '<i />' },
  createResource: (o) => {
    const r = reactive({ opts: o, error: null, submit: vi.fn(async () => { if (r.fail) { r.error = r.fail; throw r.fail } return r.result }) })
    h.made.push(r)
    return r
  },
}))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/layout/useBranding', () => ({ useBranding: () => ({ appName: ref('Acme'), appLogo: ref('/l.png') }) }))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))

import Login from '@/pages/auth/Login.vue'
import UpdatePassword from '@/pages/auth/UpdatePassword.vue'

let loc
beforeEach(() => {
  vi.clearAllMocks(); h.made = []; h.route.query = {}
  loc = { href: '' }
  Object.defineProperty(window, 'location', { value: loc, configurable: true })
})

describe('Login', () => {
  const make = () => { const w = shallowMount(Login); return { w, login: h.made[0], reset: h.made[1] } }

  it('sends the credentials as usr / pwd', () => {
    const { w, login } = make()
    w.vm.form.email = 'a@x.com'; w.vm.form.password = 'pw'
    expect(login.opts.makeParams()).toEqual({ usr: 'a@x.com', pwd: 'pw' })
  })
  it('does nothing until both are filled', async () => {
    const { w, login } = make()
    w.vm.form.email = 'a@x.com'
    await w.vm.submitLogin()
    expect(login.submit).not.toHaveBeenCalled()
  })
  it('signs in with a full page load into the app', async () => {
    const { w, login } = make(); w.vm.form.email = 'a'; w.vm.form.password = 'b'
    await w.vm.submitLogin()
    expect(loc.href).toBe('/verp')
  })
  it('goes back to where the user was headed, inside the app only', async () => {
    for (const [target, expected] of [['/verp/Lead/L1', '/verp/Lead/L1'], ['https://evil.com', '/verp'], ['//evil.com', '/verp'], ['/app/user', '/verp'], [['/verp/x'], '/verp']]) {
      h.made = []; h.route.query = { 'redirect-to': target }
      const { w } = make(); w.vm.form.email = 'a'; w.vm.form.password = 'b'
      await w.vm.submitLogin()
      expect(loc.href).toBe(expected)
    }
  })
  it('failed sign in stays on the page and shows the servers message', async () => {
    const { w, login } = make(); w.vm.form.email = 'a'; w.vm.form.password = 'b'
    login.fail = { messages: ['Invalid login credentials'] }
    await w.vm.submitLogin()
    expect(loc.href).toBe('')
    expect(w.vm.errorMessage).toBe('Invalid login credentials')
    login.error = { message: 'fallback' }
    expect(w.vm.errorMessage).toBe('fallback')
  })
  it('the reset form starts from the typed email', () => {
    const { w } = make(); w.vm.form.email = 'a@x.com'
    w.vm.switchToReset()
    expect([w.vm.mode, w.vm.resetEmail]).toEqual(['reset', 'a@x.com'])
  })
  it('reset needs an address, sends it, and returns to sign in with a neutral message', () => {
    const { w, reset } = make()
    w.vm.submitReset(); expect(reset.submit).not.toHaveBeenCalled()
    w.vm.resetEmail = 'a@x.com'; w.vm.submitReset()
    expect(reset.submit).toHaveBeenCalled()
    expect(reset.opts.makeParams()).toEqual({ user: 'a@x.com' })
    w.vm.mode = 'reset'; reset.opts.onSuccess()
    expect(h.notify.success.mock.calls[0][0]).toMatch(/If that account exists/)
    expect(w.vm.mode).toBe('login')
    reset.opts.onError(); expect(h.notify.error).toHaveBeenCalled()
  })
})

describe('UpdatePassword', () => {
  const make = (query = { key: 'K' }) => { h.route.query = query; const w = shallowMount(UpdatePassword); return { w, update: h.made[0] } }

  it('an invalid link is rejected before calling the server', async () => {
    const { w, update } = make({})
    await w.vm.submit()
    expect(w.vm.errorMessage).toMatch(/invalid/)
    expect(update.submit).not.toHaveBeenCalled()
  })
  it('the two passwords must match', async () => {
    const { w, update } = make(); w.vm.password = 'a'; w.vm.confirm = 'b'
    await w.vm.submit()
    expect(w.vm.errorMessage).toBe("Passwords don't match.")
    expect(update.submit).not.toHaveBeenCalled()
  })
  it('sends the new password with the reset key, then loads the app', async () => {
    const { w, update } = make(); w.vm.password = 'pw'; w.vm.confirm = 'pw'
    update.result = '/verp/Lead'
    await w.vm.submit()
    expect(update.opts.makeParams()).toEqual({ new_password: 'pw', key: 'K' })
    expect(loc.href).toBe('/verp/Lead')
  })
  it('a redirect outside the app is ignored', async () => {
    for (const result of ['https://evil.com', '/app', null, undefined]) {
      h.made = []
      const { w, update } = make(); w.vm.password = 'pw'; w.vm.confirm = 'pw'; update.result = result
      await w.vm.submit()
      expect(loc.href).toBe('/verp')
    }
  })
  it('an expired key stays on the page with the servers message', async () => {
    const { w, update } = make(); w.vm.password = 'pw'; w.vm.confirm = 'pw'
    update.fail = { messages: ['Invalid or expired key'] }
    loc.href = ''
    await w.vm.submit()
    expect(loc.href).toBe('')
    expect(w.vm.errorMessage).toBe('Invalid or expired key')
  })
  it('a stale local error is cleared on the next attempt', async () => {
    const { w, update } = make(); w.vm.password = 'a'; w.vm.confirm = 'b'
    await w.vm.submit(); expect(w.vm.errorMessage).toBeTruthy()
    w.vm.confirm = 'a'; update.result = '/verp'
    await w.vm.submit(); expect(w.vm.localError).toBe('')
  })
})

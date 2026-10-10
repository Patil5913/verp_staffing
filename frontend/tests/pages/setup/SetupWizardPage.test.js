import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const h = vi.hoisted(() => ({ call: vi.fn() }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), LoadingIndicator: { template: '<i class="loading" />' } }))
vi.mock('@/utils/common/errors', () => ({ normalizeError: (e) => ({ message: e.message }) }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<div class="stub"><slot /></div>' } }))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<div class="stub"><slot /></div>' } }))
vi.mock('@/components/ui/AppDatePicker.vue', () => ({ default: { template: '<div class="stub"><slot /></div>' } }))
vi.mock('@/components/common/DataImportWizard.vue', () => ({ default: { template: '<div class="stub"><slot /></div>' } }))

import Page from '@/pages/setup/SetupWizardPage.vue'

const WIZARD = {
  languages: { languages: ['English', 'Hindi'], default_language: 'Hindi' },
  country_info: {
    India: { timezones: ['Asia/Kolkata'], currency: 'INR' },
    Japan: { timezones: ['Asia/Tokyo', 'Asia/Okinawa'], currency: 'JPY' },
  },
  all_timezones: ['UTC', 'Asia/Tokyo'],
  currencies: ['INR', 'JPY'],
  current: {},
}
const open = async (wizard = WIZARD) => {
  h.call.mockImplementation(async (m) => {
    if (m.endsWith('get_wizard_data')) return JSON.parse(JSON.stringify(wizard))
  })
  const w = mount(Page)
  await flushPromises()
  return w
}
beforeEach(() => { vi.clearAllMocks(); h.call.mockReset() })

describe('startup', () => {
  it('uses the sites default language and the current settings', async () => {
    const w = await open({ ...WIZARD, current: { country: 'Japan', time_zone: 'Asia/Okinawa', currency: 'JPY' } })
    expect(w.vm.form.language).toBe('Hindi')
    expect(w.vm.form.country).toBe('Japan')
    expect(w.vm.form.timezone).toBe('Asia/Okinawa')
  })
  it('a chosen country fills timezone and currency', async () => {
    const w = await open({ ...WIZARD, current: { country: 'Japan' } })
    expect(w.vm.form.timezone).toBe('Asia/Tokyo')
    expect(w.vm.form.currency).toBe('JPY')
  })
  it('changing country later re-fills both', async () => {
    const w = await open()
    w.vm.form.country = 'India'
    await flushPromises()
    expect([w.vm.form.timezone, w.vm.form.currency]).toEqual(['Asia/Kolkata', 'INR'])
  })
  it('lists country timezones first, without duplicates', async () => {
    const w = await open({ ...WIZARD, current: { country: 'Japan' } })
    expect(w.vm.timezoneOptions).toEqual(['Asia/Okinawa', 'Asia/Tokyo', 'UTC'])
  })
  it('a failed load shows the error', async () => {
    h.call.mockRejectedValue(new Error('offline'))
    const w = mount(Page)
    await flushPromises()
    expect(w.vm.errorMessage).toBe('offline')
    expect(w.vm.loading).toBe(false)
  })
  it('sorted country and provider lists', async () => {
    const w = await open()
    expect(w.vm.countryOptions).toEqual(['India', 'Japan'])
    expect(w.vm.providerOptions).toEqual([...w.vm.providerOptions].sort((a, b) => a.localeCompare(b)))
  })
})

describe('email providers', () => {
  it('typing a known address picks the provider and its server presets', async () => {
    const w = await open()
    w.vm.onEmailInput('me@gmail.com')
    expect(w.vm.form.email_provider).toBe('Gmail')
    expect(w.vm.form.email_server).toBe('imap.gmail.com')
    expect(w.vm.form.incoming_port).toBe(993)
    expect(w.vm.form.use_ssl).toBe(true)
    expect(w.vm.form.use_tls).toBe(false)
  })
  it('unknown domains or partial input change nothing', async () => {
    const w = await open()
    w.vm.onEmailInput('me@corp.example'); w.vm.onEmailInput('me'); w.vm.onEmailInput('')
    expect(w.vm.form.email_provider).toBe('')
  })
  it('choosing a provider by hand applies its presets', async () => {
    const w = await open()
    w.vm.onProviderChange('Gmail')
    expect(w.vm.form.smtp_server).toBe('smtp.gmail.com')
    w.vm.onProviderChange('Nope')
  })
})

describe('steps and validation', () => {
  const fillWelcome = (w) => Object.assign(w.vm.form, { language: 'English', country: 'India', timezone: 'Asia/Kolkata', currency: 'INR' })
  const fillOrg = (w, o = {}) => Object.assign(w.vm.form, {
    company_name: 'Acme', fy_start_date: '2026-04-01', fy_end_date: '2027-03-31',
    business_email: 'me@gmail.com', email_password: 'pw', email_provider: 'Gmail', ...o,
  })

  it('welcome step needs all four choices', async () => {
    const w = await open()
    w.vm.form.country = ''; w.vm.form.timezone = ''
    w.vm.next()
    expect(w.vm.step).toBe(0)
    expect(w.vm.errorMessage).toContain('required')
    fillWelcome(w); w.vm.next()
    expect(w.vm.step).toBe(1)
    expect(w.vm.errorMessage).toBe('')
  })

  const problem = async (o) => { const w = await open(); fillWelcome(w); fillOrg(w, o); return w.vm.validateOrganization() }
  it('organisation rules', async () => {
    expect(await problem({})).toBe('')
    expect(await problem({ company_name: '  ' })).toMatch(/Company Name/)
    expect(await problem({ fy_start_date: '' })).toMatch(/Fiscal Year dates/)
    expect(await problem({ fy_start_date: '2027-01-01', fy_end_date: '2026-01-01' })).toMatch(/after Start/)
    expect(await problem({ fy_start_date: '2027-01-01', fy_end_date: '2027-01-01' })).toMatch(/after Start/)
    expect(await problem({ business_email: '' })).toMatch(/provider|Business Email/)
    expect(await problem({ business_email: '', email_provider: 'Gmail' })).toMatch(/Business Email/)
    expect(await problem({ email_password: '' })).toMatch(/Password/)
    expect(await problem({ business_email: 'x@corp.example', email_provider: '' })).toMatch(/provider/)
  })

  it('a known domain does not need the provider picked', async () => {
    expect(await problem({ email_provider: '' })).toBe('')
  })

  it('a problem on step 2 blocks completion', async () => {
    const w = await open(); fillWelcome(w); fillOrg(w, { company_name: '' }); w.vm.step = 1
    w.vm.next()
    expect(h.call).toHaveBeenCalledTimes(1) // only the wizard-data fetch
    expect(w.vm.errorMessage).toMatch(/Company/)
  })
})

describe('completing setup', () => {
  const ready = async () => {
    const w = await open()
    Object.assign(w.vm.form, {
      language: 'English', country: 'India', timezone: 'Asia/Kolkata', currency: 'INR', company_name: 'Acme',
      fy_start_date: '2026-04-01', fy_end_date: '2027-03-31', business_email: 'me@gmail.com', email_password: 'pw',
      email_provider: 'Gmail', add_sample_data: true, use_imap: true, use_tls: false,
    })
    w.vm.step = 1
    return w
  }

  it('sets up email, then the site, sending flags as 0/1 and lang', async () => {
    const w = await ready()
    h.call.mockImplementation(async (m) => (m.endsWith('setup_complete') ? { status: 'ok' } : {}))
    await w.vm.complete()
    const calls = h.call.mock.calls.map((c) => c[0])
    expect(calls.slice(-2)).toEqual(['verp_staffing.setup.email_utils.setup_email', 'frappe.desk.page.setup_wizard.setup_wizard.setup_complete'])
    const args = h.call.mock.calls.at(-1)[1].args
    expect(args).toMatchObject({ lang: 'English', add_sample_data: 1, use_imap: 1, use_tls: 0 })
    expect(w.vm.showImportStep).toBe(true)
    expect(w.vm.working).toBe(false)
  })

  it('a failing email check stops before the site is set up', async () => {
    const w = await ready()
    h.call.mockImplementation(async (m) => { if (m.endsWith('setup_email')) throw new Error('bad login') })
    await w.vm.complete()
    expect(h.call.mock.calls.map((c) => c[0])).not.toContain('frappe.desk.page.setup_wizard.setup_wizard.setup_complete')
    expect(w.vm.errorMessage).toBe('bad login')
    expect(w.vm.working).toBe(false)
  })

  it('a refusal from setup_complete is shown', async () => {
    const w = await ready()
    h.call.mockImplementation(async (m) => (m.endsWith('setup_complete') ? { status: 'fail', fail: 'Company exists' } : {}))
    await w.vm.complete()
    expect(w.vm.errorMessage).toBe('Company exists')
    expect(w.vm.showImportStep).toBe(false)
  })

  describe('background setup', () => {
    beforeEach(() => vi.useFakeTimers())
    afterEach(() => vi.useRealTimers())

    it('polls until the site reports complete', async () => {
      const w = await ready()
      let polls = 0
      h.call.mockImplementation(async (m) => {
        if (m.endsWith('setup_complete')) return { status: 'registered' }
        if (m.endsWith('get_setup_status')) return { setup_complete: ++polls >= 3 }
        return {}
      })
      const p = w.vm.complete()
      await vi.advanceTimersByTimeAsync(2000 * 3 + 10)
      await p
      expect(polls).toBe(3)
      expect(w.vm.showImportStep).toBe(true)
    })

    it('tolerates poll errors and gives up eventually', async () => {
      const w = await ready()
      h.call.mockImplementation(async (m) => {
        if (m.endsWith('setup_complete')) return { status: 'registered' }
        if (m.endsWith('get_setup_status')) throw new Error('blip')
        return {}
      })
      const p = w.vm.complete()
      await vi.advanceTimersByTimeAsync(2000 * 151)
      await p
      expect(w.vm.errorMessage).toMatch(/taking longer/)
      expect(w.vm.working).toBe(false)
    })
  })

  it('goToWorkspace does a full reload into the app', async () => {
    const w = await open()
    const orig = window.location
    Object.defineProperty(window, 'location', { value: { href: '' }, configurable: true })
    w.vm.goToWorkspace()
    expect(window.location.href).toBe('/verp')
    Object.defineProperty(window, 'location', { value: orig, configurable: true })
  })
})

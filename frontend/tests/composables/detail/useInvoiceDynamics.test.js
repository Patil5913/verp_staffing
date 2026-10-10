import { describe, it, expect, vi, beforeEach } from 'vitest'
import { reactive, ref, nextTick } from 'vue'

const callMock = vi.fn()
vi.mock('frappe-ui', () => ({ call: (...a) => callMock(...a) }))

const flush = async () => { for (let i = 0; i < 5; i++) { await Promise.resolve(); await nextTick() } }
let n = 0
const co = () => `Co-${++n}` // the composable caches per company, so each test uses a fresh one

const make = (values = {}, { isNew = true, hidden = {} } = {}) => ({
  values: reactive({ items: [], taxes: [], ...values }),
  hidden: reactive(hidden),
  isNew: ref(isNew),
})

beforeEach(() => { callMock.mockReset() })

describe('useInvoiceDynamics', () => {
  it('fills company currency and empty currency on a new doc', async () => {
    const { useInvoiceDynamics } = await import('@/composables/detail/useInvoiceDynamics')
    callMock.mockResolvedValue({ default_currency: 'INR' })
    const d = make({ company: co() })
    useInvoiceDynamics(d)
    await flush()
    expect(d.values.company_currency).toBe('INR')
    expect(d.values.currency).toBe('INR')
  })

  it('keeps an already chosen currency unless followCompanyCurrency', async () => {
    const { useInvoiceDynamics } = await import('@/composables/detail/useInvoiceDynamics')
    callMock.mockResolvedValue({ default_currency: 'INR' })
    const a = make({ company: co(), currency: 'USD' })
    useInvoiceDynamics(a)
    await flush()
    expect(a.values.currency).toBe('USD')
    const b = make({ company: co(), currency: 'USD' })
    useInvoiceDynamics(b, { followCompanyCurrency: true })
    await flush()
    expect(b.values.currency).toBe('INR')
  })

  it('leaves saved docs alone', async () => {
    const { useInvoiceDynamics } = await import('@/composables/detail/useInvoiceDynamics')
    callMock.mockResolvedValue({ default_currency: 'INR' })
    const d = make({ company: co() }, { isNew: false })
    useInvoiceDynamics(d)
    await flush()
    expect(d.values.company_currency).toBeUndefined()
  })

  it('same currency forces rate to 1', async () => {
    const { useInvoiceDynamics } = await import('@/composables/detail/useInvoiceDynamics')
    const d = make({ currency: 'INR', company_currency: 'INR', conversion_rate: 83 })
    useInvoiceDynamics(d)
    await flush()
    expect(d.values.conversion_rate).toBe(1)
    const e = make({ currency: 'USD', company_currency: 'INR', conversion_rate: 83 })
    useInvoiceDynamics(e)
    await flush()
    expect(e.values.conversion_rate).toBe(83)
  })

  it('switching company resets dependent accounts', async () => {
    const { useInvoiceDynamics } = await import('@/composables/detail/useInvoiceDynamics')
    callMock.mockResolvedValue({ default_currency: 'INR', default_income_account: 'Sales', default_discount_account: 'Disc' })
    const first = co(), second = co()
    const d = make({ company: first, items: [{ income_account: 'Old' }], taxes: [{ account_head: 'Old Tax' }] })
    useInvoiceDynamics(d)
    await flush()
    d.values.company = second
    await flush()
    expect(d.values.items[0].income_account).toBe('Sales')
    expect(d.values.taxes[0].account_head).toBeNull()
    expect(d.values.additional_discount_account).toBe('Disc')
  })

  it('expenseSide resets expense accounts', async () => {
    const { useInvoiceDynamics } = await import('@/composables/detail/useInvoiceDynamics')
    callMock.mockResolvedValue({ default_expense_account: 'Exp' })
    const d = make({ company: co(), items: [{ expense_account: 'Old' }] })
    useInvoiceDynamics(d, { expenseSide: true })
    await flush()
    d.values.company = co()
    await flush()
    expect(d.values.items[0].expense_account).toBe('Exp')
  })

  it('a discount picks the default discount account only when none set', async () => {
    const { useInvoiceDynamics } = await import('@/composables/detail/useInvoiceDynamics')
    callMock.mockResolvedValue({ default_discount_account: 'Disc' })
    const d = make({ company: co() })
    useInvoiceDynamics(d)
    await flush()
    d.values.discount_amount = 10
    await flush()
    expect(d.values.additional_discount_account).toBe('Disc')
    const e = make({ company: co(), additional_discount_account: 'Mine' })
    useInvoiceDynamics(e)
    e.values.discount_amount = 10
    await flush()
    expect(e.values.additional_discount_account).toBe('Mine')
  })

  it('a failing company lookup does not throw', async () => {
    const { useInvoiceDynamics } = await import('@/composables/detail/useInvoiceDynamics')
    callMock.mockRejectedValue(new Error('x'))
    const d = make({ company: co() })
    useInvoiceDynamics(d)
    await flush()
    expect(d.values.company_currency).toBeUndefined()
  })
})

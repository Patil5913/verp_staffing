import { describe, it, expect, vi } from 'vitest'

const h = vi.hoisted(() => ({ call: vi.fn() }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a) }))

import { currencyCodeFor, currencySymbol } from '@/utils/detail/currency'

describe('currencyCodeFor', () => {
  it('no options → blank', () => expect(currencyCodeFor({}, [{}])).toBe(''))
  it('reads the named field from the row first, then the parent', () => {
    const f = { options: 'currency' }
    expect(currencyCodeFor(f, [{ currency: 'EUR' }, { currency: 'USD' }])).toBe('EUR')
    expect(currencyCodeFor(f, [{}, { currency: 'USD' }])).toBe('USD')
    expect(currencyCodeFor(f, [{ currency: '' }, { currency: 'GBP' }])).toBe('GBP')
  })
  it('a literal code', () => expect(currencyCodeFor({ options: 'INR' }, [{}])).toBe('INR'))
  it('a non-code with no field is blank', () => expect(currencyCodeFor({ options: 'currency' }, [{}])).toBe(''))
  it('Company:<link>:<field> fetches once and is reactive', async () => {
    h.call.mockResolvedValue({ default_currency: 'CAD' })
    const f = { options: 'Company:company:default_currency' }
    expect(currencyCodeFor(f, [{ company: 'Acme' }])).toBe('')
    expect(currencyCodeFor(f, [{ company: 'Acme' }])).toBe('')
    expect(h.call).toHaveBeenCalledTimes(1)
    expect(h.call).toHaveBeenCalledWith('frappe.client.get_value', { doctype: 'Company', filters: 'Acme', fieldname: 'default_currency' })
    await Promise.resolve(); await Promise.resolve()
    expect(currencyCodeFor(f, [{ company: 'Acme' }])).toBe('CAD')
  })
  it('no company chosen does not fetch', () => {
    h.call.mockClear()
    expect(currencyCodeFor({ options: 'Company:company:default_currency' }, [{}])).toBe('')
    expect(h.call).not.toHaveBeenCalled()
  })
})

describe('currencySymbol', () => {
  it('blank', () => expect(currencySymbol('')).toBe(''))
  it('known', () => expect(currencySymbol('USD')).toBe('$'))
  it('invalid code is returned as is', () => expect(currencySymbol('??')).toBe('??'))
})

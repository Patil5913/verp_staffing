import { describe, it, expect } from 'vitest'
import { dependsOnPasses } from '@/utils/detail/dependsOn'
import { paidAccountFilterFor } from '@/utils/detail/paymentAccounts'
import { autoTitleFromFile } from '@/utils/detail/documentTitle'

describe('dependsOnPasses', () => {
  it('no expression passes', () => expect(dependsOnPasses({}, {})).toBe(true))
  it('bare fieldname = has value', () => {
    expect(dependsOnPasses({ depends_on: 'a' }, { a: 1 })).toBe(true)
    expect(dependsOnPasses({ depends_on: 'a' }, { a: 0 })).toBe(false)
  })
  it('eval expressions', () => {
    expect(dependsOnPasses({ depends_on: 'eval:doc.x==2' }, { x: 2 })).toBe(true)
    expect(dependsOnPasses({ depends_on: 'eval:!doc.cur' }, { cur: 1 })).toBe(false)
    expect(dependsOnPasses({ depends_on: "eval:in_list(['a','b'], doc.t)" }, { t: 'b' })).toBe(true)
    expect(dependsOnPasses({ depends_on: "eval:in_list(['a','b'], doc.t)" }, { t: 'c' })).toBe(false)
  })
  it('broken expression shows the field', () => {
    expect(dependsOnPasses({ depends_on: 'eval:doc.(' }, {})).toBe(true)
    expect(dependsOnPasses({ depends_on: 'eval:doc.a.b.c' }, {})).toBe(true)
  })
})

describe('paidAccountFilterFor', () => {
  const base = { company: 'C', bankCashPaymentTypes: ['Receive', 'Pay'] }
  it('bank/cash payment types', () => {
    expect(paidAccountFilterFor({ ...base, partyType: 'Customer', paymentType: 'Receive' }).filters.account_type).toEqual(['in', ['Bank', 'Cash']])
  })
  it('party account types', () => {
    const f = (partyType) => paidAccountFilterFor({ ...base, partyType, paymentType: 'Internal Transfer' }).filters
    expect(f('Customer').account_type).toEqual(['in', ['Receivable']])
    expect(f('Supplier').account_type).toEqual(['in', ['Payable']])
    expect(f('Shareholder').account_type).toEqual(['in', ['Equity', 'Equity']])
    expect(f('Unknown').account_type).toEqual(['in', ['Receivable']])
    expect(f('Customer')).toMatchObject({ is_group: 0, disabled: 0, company: 'C' })
  })
})

describe('autoTitleFromFile', () => {
  it('strips extension', () => expect(autoTitleFromFile({ file_name: 'my.resume.pdf' }, {})).toEqual({ document_title: 'my.resume' }))
  it('does not overwrite', () => expect(autoTitleFromFile({ file_name: 'a.pdf' }, { document_title: 'x' })).toBeNull())
  it('no file name', () => expect(autoTitleFromFile(null, {})).toBeNull())
  it('custom field', () => expect(autoTitleFromFile({ file_name: 'a.pdf' }, {}, { titleField: 't' })).toEqual({ t: 'a' }))
})

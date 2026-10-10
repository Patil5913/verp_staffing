import { describe, it, expect } from 'vitest'
import { recalcDocTotals } from '@/utils/detail/docCalculator'

const doc = (extra = {}) => ({
  items: [{ qty: 2, rate: 10.005 }, { qty: 1, rate: 5 }],
  ...extra,
})

describe('recalcDocTotals', () => {
  it('totals items', () => {
    const v = doc()
    recalcDocTotals(v)
    expect(v.items[0].amount).toBe(20.01)
    expect(v.total).toBe(25.01)
    expect(v.total_qty).toBe(3)
    expect(v.net_total).toBe(25.01)
    expect(v.grand_total).toBe(25.01)
    expect(v.rounded_total).toBe(25)
    expect(v.rounding_adjustment).toBe(-0.01)
    expect(v.outstanding_amount).toBe(25)
  })

  it('applies percentage discount over absolute', () => {
    const v = { items: [{ qty: 1, rate: 200 }], additional_discount_percentage: 10, discount_amount: 1 }
    recalcDocTotals(v)
    expect(v.discount_amount).toBe(20)
    expect(v.net_total).toBe(180)
  })

  it('absolute discount', () => {
    const v = { items: [{ qty: 1, rate: 100 }], discount_amount: 15 }
    recalcDocTotals(v)
    expect(v.net_total).toBe(85)
    expect(v.base_discount_amount).toBe(15)
  })

  it('taxes of each charge type', () => {
    const v = {
      items: [{ qty: 2, rate: 50 }],
      taxes: [
        { charge_type: 'On Net Total', rate: 10 },
        { charge_type: 'On Previous Row Amount', rate: 50 },
        { charge_type: 'On Previous Row Total', rate: 10 },
        { charge_type: 'On Item Quantity', rate: 1 },
        { charge_type: 'Actual', tax_amount: 3 },
      ],
    }
    recalcDocTotals(v)
    expect(v.taxes.map((t) => t.tax_amount)).toEqual([10, 5, 11.5, 2, 3])
    expect(v.taxes.map((t) => t.total)).toEqual([110, 115, 126.5, 128.5, 131.5])
    expect(v.total_taxes_and_charges).toBe(31.5)
    expect(v.grand_total).toBe(131.5)
  })

  it('disable_rounded_total keeps grand total', () => {
    const v = { items: [{ qty: 1, rate: 10.4 }], disable_rounded_total: 1 }
    recalcDocTotals(v)
    expect(v.rounded_total).toBe(10.4)
    expect(v.rounding_adjustment).toBe(0)
  })

  it('base currency conversion', () => {
    const v = { items: [{ qty: 1, rate: 10 }], conversion_rate: 2.5 }
    recalcDocTotals(v)
    expect(v.base_total).toBe(25)
    expect(v.base_grand_total).toBe(25)
  })

  it('handles empty doc and junk numbers', () => {
    const v = {}
    recalcDocTotals(v)
    expect(v.grand_total).toBe(0)
    const w = { items: [{ qty: 'x', rate: null }] }
    recalcDocTotals(w)
    expect(w.total).toBe(0)
  })
})

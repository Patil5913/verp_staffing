import { describe, it, expect } from 'vitest'
import { REPORT_CONFIGS } from '@/configs/reports'

describe('REPORT_CONFIGS', () => {
  const entries = Object.entries(REPORT_CONFIGS)
  it('has the financial statements as trees with a money axis chart', () => {
    for (const name of ['Profit and Loss Statement', 'Balance Sheet']) {
      expect(REPORT_CONFIGS[name]).toMatchObject({ layout: 'tree', currencyFromFilter: 'currency', chart: { mode: 'axis', currency: true } })
    }
  })
  it('every layout and chart mode is one the table and chart components know', () => {
    for (const [name, c] of entries) {
      if (c.layout) expect(['table', 'tree'], name).toContain(c.layout)
      if (c.chart) expect(['bars', 'funnel', 'axis'], name).toContain(c.chart.mode)
    }
  })
  it('hidden columns are lists of names; rowClass answers only tones the table styles', () => {
    const tones = ['', 'danger', 'success', 'muted', 'strong', 'total']
    for (const [name, c] of entries) {
      if (c.hidden) expect(Array.isArray(c.hidden), name).toBe(true)
      if (c.rowClass) {
        for (const row of [{}, { is_total_row: 1 }, { is_opening_row: 1 }, { to_highlight: 1 }, { total_revenue: 1, target: 5, completed_target: 0 }]) {
          expect(tones, `${name} -> ${c.rowClass(row)}`).toContain(c.rowClass(row))
        }
      }
    }
  })
  it('ledger rows: opening / closing are strong, totals are total, others untinted', () => {
    const gl = REPORT_CONFIGS['General Ledger']
    expect(gl.rowClass({ is_opening_row: 1 })).toBe('strong')
    expect(gl.rowClass({ is_closing_row: 1 })).toBe('strong')
    expect(gl.rowClass({ is_total_row: 1 })).toBe('total')
    expect(gl.rowClass({})).toBe('')
    expect(gl.totals).toBe(false)
  })
  it('target reports colour bars by whether the target was met', () => {
    const t = REPORT_CONFIGS['Interview Target Report'].chart
    expect(t.colorBy({ completed_target: 1, target: 5 })).toBe('danger')
    expect(t.colorBy({ completed_target: 5, target: 5 })).toBe('success')
    expect(t.colorBy({})).toBe('success')
    const revenue = REPORT_CONFIGS['Revenue Of Employee']
    expect(revenue.rowClass({ total_revenue: 1, target: 5 })).toBe('danger')
    expect(revenue.rowClass({ total_revenue: 9, target: 5 })).toBe('')
  })
  it('legends pair a known tone with a label', () => {
    for (const [name, c] of entries) for (const [tone, label] of c.chart?.legend || []) {
      expect(['success', 'danger'], name).toContain(tone)
      expect(label, name).toBeTruthy()
    }
  })
})

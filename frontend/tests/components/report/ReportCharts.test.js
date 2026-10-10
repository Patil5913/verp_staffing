import { describe, it, expect, vi, beforeAll } from 'vitest'
import { mount } from '@vue/test-utils'

import ReportChart from '@/components/report/ReportChart.vue'
import ReportBarChart from '@/components/report/ReportBarChart.vue'

beforeAll(() => {
  globalThis.ResizeObserver = class { observe() {} disconnect() {} }
})

const chart = (props = {}) =>
  mount(ReportChart, { props: { title: 'T', labels: ['Jan', 'Feb', 'Mar'], datasets: [{ name: 'A', values: [10, 20, 30] }], ...props } })

describe('ReportChart', () => {
  it('draws one bar per value in bar mode, with the title and period count', () => {
    const w = chart()
    expect(w.text()).toContain('3 periods')
    expect(w.findAll('svg rect').filter((r) => r.attributes('rx') && r.attributes('fill') !== 'var(--app-primary)')).toHaveLength(3)
  })

  it('singular period and series count', () => {
    expect(chart({ labels: ['Jan'], datasets: [{ name: 'A', values: [1] }] }).text()).toContain('1 period')
    expect(chart({ datasets: [{ name: 'A', values: [1] }, { name: 'B', values: [2] }] }).text()).toContain('2 series')
  })

  it('missing or non numeric values count as zero', () => {
    const w = chart({ datasets: [{ name: 'A', values: [1, 'x'] }] })
    expect(w.findAll('svg rect').filter((r) => r.attributes('rx')).length).toBe(3)
  })

  it('unknown type falls back to bars', () => {
    expect(chart({ type: 'pie' }).findAll('svg path').length).toBe(0)
  })

  it('line draws a path and points; area adds the fill', async () => {
    const w = chart({ type: 'line' })
    expect(w.findAll('svg path')).toHaveLength(1)
    expect(w.findAll('svg circle')).toHaveLength(3)
    const area = chart({ type: 'area' })
    expect(area.findAll('svg path')).toHaveLength(2)
  })

  it('the switch changes kind', async () => {
    const w = chart()
    const lineBtn = w.findAll('button').find((b) => b.text() === 'Line')
    await lineBtn.trigger('click')
    expect(w.findAll('svg path')).toHaveLength(1)
  })

  it('the legend hides a series but always leaves one visible', async () => {
    const w = chart({ type: 'line', datasets: [{ name: 'A', values: [1, 2, 3] }, { name: 'B', values: [3, 2, 1] }] })
    const [a, b] = w.findAll('button').filter((x) => ['A', 'B'].includes(x.text()))
    expect(w.findAll('svg path')).toHaveLength(2)
    await a.trigger('click')
    expect(w.findAll('svg path')).toHaveLength(1)
    await b.trigger('click')
    expect(w.findAll('svg path')).toHaveLength(1)
  })

  it('uses given colours, else the palette', () => {
    const w = chart({ type: 'line', colors: ['#111111'] })
    expect(w.find('svg path').attributes('stroke')).toBe('#111111')
    expect(chart({ type: 'line' }).find('svg path').attributes('stroke')).toBe('#4c7dff')
  })

  it('a point colour overrides the series colour on bars', () => {
    const w = chart({ pointColors: ['#aaaaaa'] })
    expect(w.findAll('svg rect').some((r) => r.attributes('fill') === '#aaaaaa')).toBe(true)
  })

  it('hover shows a tooltip with every series, formatted as currency', async () => {
    const w = chart({ currency: 'USD', datasets: [{ name: 'A', values: [10, 20, 30] }, { name: 'B', values: [1, 2, 3] }] })
    const svg = w.find('svg')
    svg.element.getBoundingClientRect = () => ({ left: 0 })
    await svg.trigger('mousemove', { clientX: 60 })
    expect(w.text()).toContain('Jan')
    expect(w.text()).toContain('$10.00')
    await w.find('div.relative').trigger('mouseleave')
    expect(w.text()).not.toContain('$10.00')
  })

  it('hover outside the plot area clears it', async () => {
    const w = chart()
    const svg = w.find('svg')
    svg.element.getBoundingClientRect = () => ({ left: 0 })
    await svg.trigger('mousemove', { clientX: 5 })
    expect(w.find('.pointer-events-none').exists()).toBe(false)
  })

  it('bad currency falls back to a plain number', async () => {
    const w = chart({ currency: 'NOPE!' })
    const svg = w.find('svg')
    svg.element.getBoundingClientRect = () => ({ left: 0 })
    await svg.trigger('mousemove', { clientX: 60 })
    expect(w.text()).toContain('10')
  })

  it('negative values draw below the zero line and the axis includes zero', () => {
    const w = chart({ datasets: [{ name: 'A', values: [-10, 5, 0] }] })
    const labels = w.findAll('svg text').map((t) => t.text())
    expect(labels).toContain('0')
    expect(labels.some((l) => l.startsWith('-') || l.startsWith('−'))).toBe(true)
  })

  it('all zero data still renders an axis without NaN', () => {
    const w = chart({ datasets: [{ name: 'A', values: [0, 0, 0] }] })
    expect(w.html()).not.toContain('NaN')
  })

  it('empty labels do not crash', () => {
    const w = chart({ labels: [], datasets: [{ name: 'A', values: [] }] })
    expect(w.html()).not.toContain('NaN')
  })

  it('thins crowded x labels and truncates long ones', () => {
    const labels = Array.from({ length: 60 }, (_, i) => `A very long label number ${i}`)
    const w = chart({ labels, datasets: [{ name: 'A', values: labels.map((_, i) => i) }] })
    const xs = w.findAll('svg text').filter((t) => t.text().includes('…'))
    expect(xs.length).toBeGreaterThan(0)
    expect(xs.length).toBeLessThan(60)
  })

  it('renders the extra legend', () => {
    expect(chart({ legend: [['#f00', 'Over target']] }).text()).toContain('Over target')
  })
})

const bar = (props = {}) => mount(ReportBarChart, { props: { title: 'Share', labels: ['a', 'b', 'c'], values: [50, 30, 20], ...props } })

describe('ReportBarChart (share)', () => {
  it('ranks by value with each share of the total', () => {
    const w = bar({ labels: ['small', 'big'], values: [10, 90] })
    const rows = w.findAll('ol li')
    expect(rows[0].text()).toContain('big')
    expect(rows[0].text()).toContain('90%')
    expect(rows[1].text()).toContain('10%')
    expect(w.text()).toContain('2 items')
    expect(w.text()).toContain('100')
  })

  it('shares round to one decimal', () => {
    expect(bar({ labels: ['a', 'b', 'c'], values: [1, 1, 1] }).text()).toContain('33.3%')
  })

  it('zero total gives 0% shares and no donut segments', () => {
    const w = bar({ values: [0, 0, 0] })
    expect(w.text()).toContain('0%')
    expect(w.findAll('svg circle')).toHaveLength(1)
    expect(w.html()).not.toContain('NaN')
  })

  it('hovering a row focuses the matching donut centre', async () => {
    const w = bar()
    await w.findAll('ol li')[1].trigger('mouseenter')
    expect(w.text()).toContain('b')
    expect(w.text()).toContain('30%')
    await w.findAll('ol li')[1].trigger('mouseleave')
    expect(w.text()).toContain('Total')
  })

  it('items past the palette share a neutral colour', () => {
    const labels = Array.from({ length: 9 }, (_, i) => `i${i}`)
    const w = bar({ labels, values: labels.map(() => 1) })
    const dots = w.findAll('ol li span.rounded-full').map((d) => d.attributes('style'))
    expect(dots[8]).toContain('148, 163, 184')
  })

  it('singular item', () => expect(bar({ labels: ['a'], values: [5] }).text()).toContain('1 item '))
})

describe('ReportBarChart (funnel)', () => {
  it('keeps stage order and shows drop-off from the previous stage', () => {
    const w = bar({ ratio: true, labels: ['Leads', 'Won'], values: [200, 50] })
    const rows = w.findAll('ol li')
    expect(rows[0].text()).toContain('Leads')
    expect(rows[0].text()).toContain('100%')
    expect(rows[1].text()).toContain('25%')
    expect(rows[1].text()).toContain('↓75%')
  })

  it('a zero first stage never divides by zero', () => {
    const w = bar({ ratio: true, labels: ['A', 'B'], values: [0, 5] })
    expect(w.html()).not.toContain('NaN')
    expect(w.html()).not.toContain('Infinity')
  })

  it('bars never get narrower than the minimum width', () => {
    const w = bar({ ratio: true, labels: ['A', 'B'], values: [1000, 1] })
    expect(w.findAll('ol li div div')[1].attributes('style')).toContain('width: 12%')
  })
})

import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

const { push } = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
vi.mock('frappe-ui', () => ({ call: vi.fn(), FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' } }))

import ReportTable from '@/components/report/ReportTable.vue'

const RouterLink = { props: ['to'], template: '<a class="rl" :data-to="to"><slot /></a>' }
const columns = [
  { fieldname: 'name', label: 'Name', fieldtype: 'Data' },
  { fieldname: 'amount', label: 'Amount', fieldtype: 'Currency' },
  { fieldname: 'qty', label: 'Qty', fieldtype: 'Int' },
]
const rows = [
  { name: 'b', amount: 20, qty: 2, currency: 'USD' },
  { name: 'a', amount: 5, qty: 10, currency: 'USD' },
  { name: 'c', amount: -3, qty: 1, currency: 'USD' },
]
const mk = (props = {}) => mount(ReportTable, { props: { columns, rows, defaultCurrency: 'USD', ...props }, global: { stubs: { 'router-link': RouterLink, RouterLink } } })
const names = (w) => w.findAll('tbody tr').map((r) => r.findAll('td')[1]?.text())
const header = (w, label) => w.findAll('thead th').find((th) => th.text().startsWith(label))

describe('ReportTable', () => {
  it('numbers rows and shows the counts', () => {
    const w = mk()
    expect(w.text()).toContain('3 rows · 3 columns')
    expect(w.findAll('tbody tr').map((r) => r.findAll('td')[0].text())).toEqual(['1', '2', '3'])
  })
  it('formats currency and tints negatives red', () => {
    const w = mk()
    const cells = w.findAll('tbody tr').map((r) => r.findAll('td')[2])
    expect(cells[0].text()).toContain('$')
    expect(cells[2].find('span').classes()).toContain('text-red-600')
    expect(cells[0].find('span').classes()).not.toContain('text-red-600')
  })
  it('click a header to sort: text ascending first, numbers descending first, then toggles', async () => {
    const w = mk()
    await header(w, 'Name').trigger('click')
    expect(names(w)).toEqual(['a', 'b', 'c'])
    await header(w, 'Name').trigger('click')
    expect(names(w)).toEqual(['c', 'b', 'a'])
    await header(w, 'Amount').trigger('click')
    expect(names(w)).toEqual(['b', 'a', 'c'])
    await header(w, 'Amount').trigger('click')
    expect(names(w)).toEqual(['c', 'a', 'b'])
  })
  it('sorting treats numbers numerically and blanks last', async () => {
    const w = mk({ rows: [{ name: 'x', qty: 9 }, { name: 'y', qty: '' }, { name: 'z', qty: 10 }] })
    await header(w, 'Qty').trigger('click')
    expect(names(w)).toEqual(['z', 'x', 'y'])
  })
  it('sorting keeps opening / total / closing rows where the report put them', async () => {
    const w = mk({ rows: [
      { name: 'Opening', amount: 0, is_opening_row: 1 },
      { name: 'b', amount: 20 }, { name: 'a', amount: 5 },
      { name: 'Total', amount: 25, is_total_row: 1 },
    ] })
    await header(w, 'Name').trigger('click')
    expect(names(w)).toEqual(['Opening', 'a', 'b', 'Total'])
    await header(w, 'Name').trigger('click')
    expect(names(w)).toEqual(['Opening', 'b', 'a', 'Total'])
  })
  it('search filters rows and the count follows', async () => {
    const w = mk({ config: { searchable: true } })
    await w.find('input').setValue('a')
    expect(names(w)).toEqual(['a'])
    expect(w.text()).toContain('1 of 3 rows')
  })
  it('search is hidden unless the report is searchable', () => {
    expect(mk().find('input').exists()).toBe(false)
  })
  it('totals sum Currency and Int columns of the visible rows, skipping summary rows', () => {
    const w = mk({ rows: [...rows, { name: 'T', amount: 999, is_total_row: 1 }] })
    const foot = w.findAll('tfoot td')
    expect(foot[0].text()).toBe('Σ')
    expect(foot[1].text()).toBe('Total')
    expect(foot[2].text()).toContain('22.00')
    expect(foot[3].text()).toBe('13')
  })
  it('totals follow the search', async () => {
    const w = mk({ config: { searchable: true } })
    await w.find('input').setValue('b')
    expect(w.find('tfoot').exists()).toBe(false) // a single row has nothing to add up
  })
  it('totals never add across currencies and can be switched off', () => {
    const mixed = [{ name: 'a', amount: 1, qty: 1, currency: 'USD' }, { name: 'b', amount: 2, qty: 2, currency: 'EUR' }]
    const w = mk({ rows: mixed })
    const foot = w.findAll('tfoot td')
    expect(foot[2].text()).toBe('')
    expect(foot[3].text()).toBe('3')
    expect(mk({ config: { totals: false } }).find('tfoot').exists()).toBe(false)
  })
  it('statements (tree layout) keep server order, indent, hide numbering and totals', async () => {
    const w = mk({ config: { layout: 'tree' }, rows: [{ name: 'Assets', indent: 0, amount: 1 }, { name: 'Cash', indent: 2, amount: 2 }] })
    expect(w.find('tbody tr td').text()).toBe('Assets')
    expect(w.findAll('tbody tr')[1].find('td').attributes('style')).toContain('padding-left: 48px')
    expect(w.find('tfoot').exists()).toBe(false)
    await header(w, 'Name').trigger('click')
    expect(w.findAll('tbody tr').map((r) => r.find('td').text())).toEqual(['Assets', 'Cash'])
  })
  it('link columns open the linked record; row links navigate', async () => {
    const linked = [{ fieldname: 'ref', label: 'Ref', fieldtype: 'Link', options: 'Sales Order' }]
    const w = mk({ columns: linked, rows: [{ ref: 'SO/1' }], config: { linkRow: (r) => `/x/${r.ref}` } })
    expect(w.find('a.rl').attributes('data-to')).toBe('/Sales%20Order/SO%2F1')
    await w.find('tbody tr').trigger('click')
    expect(push).toHaveBeenCalledWith('/x/SO/1')
  })
  it('clicking a cell link does not also trigger the row link', async () => {
    push.mockReset()
    const linked = [{ fieldname: 'ref', label: 'Ref', fieldtype: 'Link', options: 'Lead' }]
    const w = mk({ columns: linked, rows: [{ ref: 'L1' }], config: { linkRow: () => '/row' } })
    await w.find('a.rl').trigger('click')
    expect(push).not.toHaveBeenCalled()
  })
  it('rows beyond the first 200 load on demand', async () => {
    const many = Array.from({ length: 450 }, (_, i) => ({ name: `n${i}`, qty: i }))
    const w = mk({ rows: many })
    expect(w.findAll('tbody tr')).toHaveLength(200)
    const more = w.findAll('button').find((b) => b.text().startsWith('Show'))
    expect(more.text()).toBe('Show 200 more (250 left)')
    await more.trigger('click')
    expect(w.findAll('tbody tr')).toHaveLength(400)
    await w.findAll('button').find((b) => b.text().startsWith('Show')).trigger('click')
    expect(w.findAll('tbody tr')).toHaveLength(450)
    expect(w.findAll('button').some((b) => b.text().startsWith('Show'))).toBe(false)
  })
  it('compact mode toggles the row height', async () => {
    const w = mk()
    expect(w.find('tbody td').classes().join(' ')).toContain('h-11')
    await w.find('button[title="Fit more rows on screen"]').trigger('click')
    expect(w.find('tbody td').classes().join(' ')).toContain('h-[26px]')
  })
  it('row tint and emphasis from the report config', () => {
    const w = mk({ config: { rowClass: (r) => (r.name === 'a' ? 'danger' : r.name === 'b' ? 'total' : '') } })
    const trs = w.findAll('tbody tr')
    expect(trs[1].classes().join(' ')).toContain('bg-red-50')
    expect(trs[0].find('td:nth-child(2)').classes()).toContain('font-semibold')
  })
})

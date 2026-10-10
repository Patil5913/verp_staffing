import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AppTable from '@/components/ui/AppTable.vue'

const columns = [{ key: 'name', label: 'Name' }, { key: 'amount', label: 'Amount', align: 'right' }]
const rows = [{ name: 'a', amount: 5 }, { name: 'b', amount: null }]

describe('AppTable', () => {
  it('headers and cells, with blanks shown empty', () => {
    const w = mount(AppTable, { props: { columns, rows } })
    expect(w.findAll('th').map((t) => t.text())).toEqual(['Name', 'Amount'])
    expect(w.findAll('tbody tr').map((r) => r.findAll('td').map((c) => c.text()))).toEqual([['a', '5'], ['b', '']])
  })
  it('right-aligned columns align header and cells', () => {
    const w = mount(AppTable, { props: { columns, rows } })
    expect(w.findAll('th')[1].classes()).toContain('text-right')
    expect(w.findAll('tbody td')[1].classes()).toContain('text-right')
    expect(w.findAll('th')[0].classes()).not.toContain('text-right')
  })
  it('a cell slot overrides the value and receives the row', () => {
    const w = mount(AppTable, { props: { columns, rows }, slots: { 'cell-name': '<template #cell-name="{ row, value }"><b>{{ value }}/{{ row.amount }}</b></template>' } })
    expect(w.findAll('tbody td')[0].html()).toContain('<b>a/5</b>')
  })
  it('empty message, configurable', () => {
    expect(mount(AppTable, { props: { columns, rows: [] } }).text()).toContain('No data.')
    expect(mount(AppTable, { props: { columns, rows: [], emptyText: 'Nothing' } }).text()).toContain('Nothing')
  })
  it('rows are clickable only when asked', async () => {
    const plain = mount(AppTable, { props: { columns, rows } })
    await plain.find('tbody tr').trigger('click')
    expect(plain.emitted('row-click')).toBeUndefined()
    const w = mount(AppTable, { props: { columns, rows, clickable: true } })
    await w.findAll('tbody tr')[1].trigger('click')
    expect(w.emitted('row-click')).toEqual([[rows[1]]])
    expect(w.find('tbody tr').classes()).toContain('cursor-pointer')
  })
})

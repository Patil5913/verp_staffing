import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('frappe-ui', () => ({ LoadingIndicator: { template: '<i class="spinner" />' }, call: vi.fn() }))

import DocTreeView from '@/components/tree/DocTreeView.vue'

const TREE = {
  null: [
    { value: 'Assets', expandable: true, balance: 100, date: '2026-01-10' },
    { value: 'Income', expandable: true, balance: 50, date: '2026-02-10' },
  ],
  Assets: [
    { value: 'Bank 2', expandable: false, balance: 70, date: '2026-01-11' },
    { value: 'Account 12', expandable: false, balance: 30, date: '2026-01-12' },
    { value: 'Cash', title: 'Cash in hand', expandable: false, balance: 0, date: '2026-01-13' },
  ],
  Income: [{ value: 'Sales', expandable: false, balance: 50, date: '2026-02-11' }],
}
const makeLoader = () => vi.fn(async (parent) => (TREE[parent] || []).map((n) => ({ ...n })))
const columns = [{ key: 'balance', label: 'Balance', align: 'right' }, { key: 'date', label: 'Date' }]

const mk = async (props = {}) => {
  const loader = props.loader || makeLoader()
  const w = mount(DocTreeView, { props: { loader, columns, ...props } })
  await flushPromises()
  return { w, loader }
}
const labels = (w) => w.vm.visibleRows.map((n) => n.label)

describe('loading', () => {
  it('loads the roots once and shows them collapsed', async () => {
    const { w, loader } = await mk()
    expect(loader).toHaveBeenCalledTimes(1)
    expect(loader).toHaveBeenCalledWith(null)
    expect(labels(w)).toEqual(['Assets', 'Income'])
  })
  it('children load on first expand only', async () => {
    const { w, loader } = await mk()
    await w.vm.toggle(w.vm.roots[0])
    expect(labels(w)).toEqual(['Assets', 'Bank 2', 'Account 12', 'Cash in hand', 'Income'])
    await w.vm.toggle(w.vm.roots[0])
    expect(labels(w)).toEqual(['Assets', 'Income'])
    await w.vm.toggle(w.vm.roots[0])
    expect(loader.mock.calls.filter((c) => c[0] === 'Assets')).toHaveLength(1)
  })
  it('a title beats the raw value for the label; depth drives the indent', async () => {
    const { w } = await mk()
    await w.vm.toggle(w.vm.roots[0])
    expect(w.vm.roots[0].children[2].label).toBe('Cash in hand')
    expect(w.vm.roots[0].children[0]._depth).toBe(1)
    const rows = w.findAll('tbody tr')
    expect(rows[1].find('td div').attributes('style')).toContain('padding-left: 20px')
  })
  it('afterLoad can enrich every fresh batch in place', async () => {
    const afterLoad = vi.fn(async (nodes) => nodes.forEach((n) => (n.enriched = true)))
    const { w } = await mk({ afterLoad })
    expect(afterLoad).toHaveBeenCalled()
    expect(w.vm.roots.every((n) => n.enriched)).toBe(true)
  })
  it('a failed load shows why and an empty tree says so', async () => {
    const bad = await mk({ loader: vi.fn(async () => { throw { status: 403, message: 'No access' } }) })
    expect(bad.w.text()).toContain('No access')
    const empty = await mk({ loader: vi.fn(async () => []), emptyTitle: 'No accounts', emptyDescription: 'Add one' })
    expect(empty.w.text()).toContain('No accounts')
    expect(empty.w.text()).toContain('Add one')
  })
  it('expand all fills the tree level by level; collapse all closes it', async () => {
    const { w } = await mk()
    await w.vm.expandAll()
    expect(labels(w)).toEqual(['Assets', 'Bank 2', 'Account 12', 'Cash in hand', 'Income', 'Sales'])
    w.vm.collapseAll()
    expect(labels(w)).toEqual(['Assets', 'Income'])
  })
  it('refreshing a node reloads just its children and opens it', async () => {
    const { w, loader } = await mk()
    await w.vm.toggle(w.vm.roots[0])
    await w.vm.refreshNode(w.vm.roots[0])
    expect(loader.mock.calls.filter((c) => c[0] === 'Assets')).toHaveLength(2)
    expect(w.vm.roots[0]._open).toBe(true)
  })
  it('reload starts over from the roots', async () => {
    const { w, loader } = await mk()
    await w.vm.reload()
    expect(loader.mock.calls.filter((c) => c[0] === null)).toHaveLength(2)
  })
})

describe('clicking', () => {
  it('a group row expands; a leaf row opens its record; the arrow opens a group', async () => {
    const { w } = await mk()
    await w.findAll('tbody tr')[0].trigger('click')
    await flushPromises()
    expect(w.emitted('open')).toBeUndefined()
    expect(w.findAll('tbody tr')).toHaveLength(5)
    await w.findAll('tbody tr')[1].trigger('click')
    expect(w.emitted('open')[0][0]).toMatchObject({ value: 'Bank 2' })
    await w.find('button[title=Open]').trigger('click')
    expect(w.emitted('open')[1][0]).toMatchObject({ value: 'Assets' })
    expect(w.findAll('tbody tr')).toHaveLength(5) // the arrow did not also toggle the row
  })
})

describe('search', () => {
  const search = async (text, props = {}) => {
    const { w } = await mk({ search: '', ...props })
    await w.vm.expandAll()
    await w.setProps({ search: text })
    return w
  }
  it('plain words match the label, id or any column, keeping the path to each match', async () => {
    const w = await search('sales')
    expect(labels(w)).toEqual(['Income', 'Sales'])
    expect((await search('in hand')).vm.visibleRows.map((n) => n.value)).toEqual(['Assets', 'Cash'])
  })
  it('field=value matches a column, by key or label, case-insensitively', async () => {
    expect(labels(await search('balance=70'))).toEqual(['Assets', 'Bank 2'])
    expect(labels(await search('BALANCE=70'))).toEqual(['Assets', 'Bank 2'])
    expect(labels(await search('name=sales'))).toEqual(['Income', 'Sales'])
  })
  it('comparisons work on numbers', async () => {
    expect(labels(await search('balance>=70'))).toEqual(['Assets', 'Bank 2'])
    const high = labels(await search('balance>60'))
    expect(high).toContain('Bank 2')
    expect(high).not.toContain('Account 12')
    expect(labels(await search('balance<1'))).toContain('Cash in hand')
    expect(labels(await search('balance!=0'))).not.toContain('Cash in hand')
  })
  it('comparisons work on ISO dates, and between takes a range', async () => {
    const after = labels(await search('date>=2026-02-01'))
    expect(after).toEqual(['Income', 'Sales'])
    const range = labels(await search('date between 2026-01-11 and 2026-01-12'))
    expect(range).toEqual(['Assets', 'Bank 2', 'Account 12'])
    expect(labels(await search('date between 2026-01-11 to 2026-01-12'))).toEqual(range)
  })
  it('AND by default, OR when asked', async () => {
    expect(labels(await search('balance>40 name=Sales'))).toEqual(['Income', 'Sales'])
    expect(labels(await search('sales or bank'))).toEqual(['Assets', 'Bank 2', 'Income', 'Sales'])
  })
  it('quoted values keep their spaces', async () => {
    expect(labels(await search('label="Cash in hand"'))).toEqual(['Assets', 'Cash in hand'])
  })
  it('a blank search shows the tree as it was opened', async () => {
    const { w } = await mk()
    await w.setProps({ search: '   ' })
    expect(labels(w)).toEqual(['Assets', 'Income'])
  })
  it('names that merely look like dates still match as text', async () => {
    // "Account 12" contains "Account 1"; the two must not be compared as dates (Dec 2001 vs Jan 2001)
    expect(labels(await search('name="Account 1"'))).toEqual(['Assets', 'Account 12'])
    expect(labels(await search('name="Bank 2"'))).toEqual(['Assets', 'Bank 2'])
    expect(labels(await search('name!="Bank 2"'))).not.toContain('Bank 2')
  })
  it('an unknown field matches nothing', async () => {
    expect(labels(await search('nonsense=1'))).toEqual([])
  })
})

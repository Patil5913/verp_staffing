import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('frappe-ui', () => ({
  FeatherIcon: { template: '<i />' },
  LoadingIndicator: { template: '<i />' },
  call: vi.fn(),
}))

import Pagination from '@/components/list/Pagination.vue'

describe('Pagination', () => {
  const btns = (w) => w.findAllComponents({ name: 'AppButton' })

  it('shows the position', () => {
    expect(mount(Pagination, { props: { page: 2, pageCount: 5 } }).text()).toContain('Page 2 of 5')
  })
  it('previous is disabled on the first page, next on the last', () => {
    const first = btns(mount(Pagination, { props: { page: 1, pageCount: 3 } }))
    expect(first[0].props('disabled')).toBe(true)
    expect(first[1].props('disabled')).toBe(false)
    const last = btns(mount(Pagination, { props: { page: 3, pageCount: 3 } }))
    expect(last[0].props('disabled')).toBe(false)
    expect(last[1].props('disabled')).toBe(true)
  })
  it('a single page disables both', () => {
    const b = btns(mount(Pagination, { props: { page: 1, pageCount: 1 } }))
    expect(b.every((x) => x.props('disabled'))).toBe(true)
  })
  it('emits the next and previous page', async () => {
    const w = mount(Pagination, { props: { page: 2, pageCount: 3 } })
    await w.findAll('button')[0].trigger('click')
    await w.findAll('button')[1].trigger('click')
    expect(w.emitted('update:page')).toEqual([[1], [3]])
  })
})

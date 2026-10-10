import { describe, it, expect, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

vi.hoisted(() => {
  window.matchMedia ||= () => ({ matches: false, addEventListener() {}, removeEventListener() {} })
})
vi.mock('frappe-ui', () => new Proxy({}, {
  get: (t, k) => (k === 'then' || typeof k === 'symbol' ? undefined : { name: String(k), template: '<div />' }),
  has: () => true,
}))

import ComponentsPage from '@/pages/admin/ComponentsPage.vue'

const source = readFileSync(join(process.cwd(), 'src/pages/admin/ComponentsPage.vue'), 'utf8')
const sectionIds = [...source.matchAll(/<ComponentSection id="([^"]+)"/g)].map((m) => m[1])

describe('ComponentsPage', () => {
  it('every table-of-contents entry points at a section that exists', () => {
    const { toc } = shallowMount(ComponentsPage).vm
    expect(toc.length).toBeGreaterThan(0)
    for (const t of toc) expect(sectionIds, t.id).toContain(t.id)
  })
  it('every section is listed in the table of contents', () => {
    const ids = shallowMount(ComponentsPage).vm.toc.map((t) => t.id)
    for (const id of sectionIds) expect(ids, id).toContain(id)
  })
  it('search filters the contents case-insensitively', async () => {
    const w = shallowMount(ComponentsPage)
    w.vm.q = 'BUTT'
    await w.vm.$nextTick()
    expect(w.vm.filteredToc.map((t) => t.id)).toEqual(['buttons'])
    w.vm.q = 'zzz'
    await w.vm.$nextTick()
    expect(w.vm.filteredToc).toEqual([])
  })
  it('scrollTo scrolls the section into view and ignores unknown ids', () => {
    const el = { scrollIntoView: vi.fn() }
    const spy = vi.spyOn(document, 'getElementById').mockReturnValueOnce(el).mockReturnValueOnce(null)
    const { vm } = shallowMount(ComponentsPage)
    vm.scrollTo('tabs'); vm.scrollTo('missing')
    expect(el.scrollIntoView).toHaveBeenCalledTimes(1)
    spy.mockRestore()
  })
})

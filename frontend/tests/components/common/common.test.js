import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

const callMock = vi.fn()
vi.mock('frappe-ui', () => ({
  call: (...a) => callMock(...a),
  FeatherIcon: { template: '<i />' },
  LoadingIndicator: { template: '<i />' },
}))

import StateBanner from '@/components/common/StateBanner.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import SectionPills from '@/components/common/SectionPills.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import NoticeBanner from '@/components/common/NoticeBanner.vue'
import RecordLabel from '@/components/common/RecordLabel.vue'

beforeEach(() => { callMock.mockReset() })

describe('StateBanner', () => {
  it('renders title, optional description, icon and slot', () => {
    const w = mount(StateBanner, { props: { title: 'Nothing', description: 'Add one', icon: 'inbox' }, slots: { default: '<button>Add</button>' } })
    expect(w.text()).toContain('Nothing')
    expect(w.text()).toContain('Add one')
    expect(w.find('span').classes()).toContain('lucide-inbox')
    expect(w.find('button').exists()).toBe(true)
    expect(mount(StateBanner, { props: { title: 'T' } }).text()).toBe('T')
  })
})

describe('SectionCard', () => {
  it('header only when there is a title or actions', () => {
    expect(mount(SectionCard).find('header').exists()).toBe(false)
    const w = mount(SectionCard, { props: { title: 'Hist', subtitle: 'sub' }, slots: { default: 'body', actions: '<i id="a" />' } })
    expect(w.find('h3').text()).toBe('Hist')
    expect(w.text()).toContain('sub')
    expect(w.text()).toContain('body')
    expect(w.find('#a').exists()).toBe(true)
    expect(mount(SectionCard, { slots: { actions: '<i />' } }).find('header').exists()).toBe(true)
  })
})

describe('SectionPills', () => {
  it('scrolls to the section', async () => {
    const target = document.createElement('div')
    target.id = 'sec-1'
    target.scrollIntoView = vi.fn()
    document.body.appendChild(target)
    const w = mount(SectionPills, { props: { sections: [{ id: 'sec-1', label: 'One' }, { id: 'missing', label: 'Two' }] } })
    const buttons = w.findAll('button')
    expect(buttons.map((b) => b.text())).toEqual(['One', 'Two'])
    await buttons[0].trigger('click')
    expect(target.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' })
    await buttons[1].trigger('click') // a missing element is tolerated
    target.remove()
  })
})

describe('DocStatusBadge', () => {
  it('docstatus labels and themes', () => {
    const w = mount(DocStatusBadge, { props: { docstatus: 1 } })
    expect(w.text()).toBe('Submitted')
    expect(w.classes().join(' ')).toMatch(/green|emerald/)
    expect(mount(DocStatusBadge, { props: { docstatus: 0 } }).text()).toBe('Draft')
    expect(mount(DocStatusBadge, { props: { docstatus: 2 } }).text()).toBe('Cancelled')
  })
  it('renders nothing without status or docstatus', () => {
    expect(mount(DocStatusBadge).text()).toBe('')
    expect(mount(DocStatusBadge, { props: { docstatus: 7 } }).text()).toBe('')
  })
  it('status text wins over docstatus; explicit theme wins over the lookup', () => {
    expect(mount(DocStatusBadge, { props: { status: 'Open', docstatus: 1 } }).text()).toBe('Open')
    const w = mount(DocStatusBadge, { props: { status: 'Paid', theme: 'red' } })
    expect(w.classes().join(' ')).toMatch(/red/)
  })
})

describe('NoticeBanner', () => {
  it('tones', () => {
    const w = mount(NoticeBanner, { props: { message: 'Locked' } })
    expect(w.text()).toBe('Locked')
    expect(w.classes()).toContain('notice-banner--warning')
    expect(w.find('span').classes()).toContain('lucide-alert-triangle')
    const d = mount(NoticeBanner, { props: { message: 'x', tone: 'danger' } })
    expect(d.classes()).toContain('notice-banner--danger')
    expect(d.find('span').classes()).toContain('lucide-octagon-alert')
  })
})

describe('RecordLabel', () => {
  it('shows a given title without a lookup', async () => {
    const w = mount(RecordLabel, { props: { doctype: 'RL1', id: 'a', title: 'Alpha' } })
    await nextTick()
    expect(w.text()).toBe('Alpha')
    expect(callMock).not.toHaveBeenCalled()
  })
  it('falls back to the id, then shows the fetched title', async () => {
    callMock.mockResolvedValue({ b: 'Bravo' })
    const w = mount(RecordLabel, { props: { doctype: 'RL2', id: 'b' } })
    expect(w.text()).toBe('b')
    await new Promise((r) => setTimeout(r, 10))
    await nextTick()
    expect(w.text()).toBe('Bravo')
  })
  it('keeps showing the id when the record has no title', async () => {
    callMock.mockResolvedValue({})
    const w = mount(RecordLabel, { props: { doctype: 'RL3', id: 'c' } })
    await new Promise((r) => setTimeout(r, 10))
    expect(w.text()).toBe('c')
  })
})

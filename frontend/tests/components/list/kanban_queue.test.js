import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { callMock, notifyMock } = vi.hoisted(() => ({ callMock: vi.fn(), notifyMock: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }))
vi.mock('frappe-ui', () => ({
  call: (...a) => callMock(...a),
  FeatherIcon: { template: '<i />' },
  LoadingIndicator: { template: '<i />' },
}))
vi.mock('@/utils/common/notify', () => ({ notify: notifyMock }))

import KanbanBoard from '@/components/list/KanbanBoard.vue'
import EmailQueueStrip from '@/components/list/EmailQueueStrip.vue'

beforeEach(() => { callMock.mockReset(); Object.values(notifyMock).forEach((f) => f.mockReset()) })

const cards = [
  { name: 'A', status: 'Open' },
  { name: 'B', status: 'Open' },
  { name: 'C', status: 'Closed' },
  { name: 'D', status: 'Ghost' }, // not a known column
]
const mk = (props = {}) => mount(KanbanBoard, { props: { columns: ['Open', 'Closed'], cards, ...props } })

describe('KanbanBoard', () => {
  it('groups cards into their columns and drops unknown statuses', () => {
    const w = mk()
    const sections = w.findAll('section')
    expect(sections).toHaveLength(2)
    expect(sections[0].findAll('article').map((a) => a.text())).toEqual(['A', 'B'])
    expect(sections[1].findAll('article').map((a) => a.text())).toEqual(['C'])
    expect(w.text()).not.toContain('D')
  })
  it('header shows the server count when given, else the loaded count', () => {
    const counts = mk({ counts: { Open: 40 } }).findAll('header span').map((s) => s.text())
    expect(counts.filter((t) => /^\d+$/.test(t))).toEqual(['40', '1'])
  })
  it('empty column placeholder', () => {
    expect(mk({ cards: [] }).text()).toContain('Nothing here')
  })
  it('named colours beat the rotating palette', () => {
    const w = mk({ columnColors: { Closed: 'green' } })
    expect(w.findAll('section')[1].classes()).toContain('border-green-500/25')
    expect(w.findAll('section')[0].classes()).toContain('border-sky-500/25')
  })
  it('clicking a card opens it', async () => {
    const w = mk()
    await w.find('article').trigger('click')
    expect(w.emitted('open')[0][0]).toEqual(cards[0])
  })
  it('dragging a card to another column requests a move', async () => {
    const w = mk()
    await w.findAll('article')[0].trigger('dragstart')
    await w.findAll('section')[1].trigger('drop')
    expect(w.emitted('move')).toEqual([[{ card: cards[0], to: 'Closed' }]])
  })
  it('dropping on the same column or with nothing dragged does not move', async () => {
    const w = mk()
    await w.findAll('article')[0].trigger('dragstart')
    await w.findAll('section')[0].trigger('drop')
    await w.findAll('section')[1].trigger('drop')
    expect(w.emitted('move')).toBeUndefined()
  })
  it('highlights the column under the drag and clears it on leave', async () => {
    const w = mk()
    await w.findAll('section')[1].trigger('dragover')
    expect(w.findAll('section')[1].classes()).toContain('border-app-primary')
    await w.findAll('section')[1].trigger('dragleave')
    expect(w.findAll('section')[1].classes()).not.toContain('border-app-primary')
  })
  it('asks for more only near the bottom of a column that has more', async () => {
    const w = mk({ hasMore: { Open: true } })
    const box = w.findAll('section')[0].find('div.overflow-y-auto')
    const scroll = async (top) => {
      Object.defineProperty(box.element, 'scrollTop', { value: top, configurable: true })
      Object.defineProperty(box.element, 'clientHeight', { value: 300, configurable: true })
      Object.defineProperty(box.element, 'scrollHeight', { value: 1000, configurable: true })
      await box.trigger('scroll')
    }
    await scroll(100)
    expect(w.emitted('load-more')).toBeUndefined()
    await scroll(650)
    expect(w.emitted('load-more')).toEqual([['Open']])
    const idle = mk()
    const b2 = idle.findAll('section')[0].find('div.overflow-y-auto')
    Object.defineProperty(b2.element, 'scrollHeight', { value: 1000, configurable: true })
    Object.defineProperty(b2.element, 'scrollTop', { value: 900, configurable: true })
    await b2.trigger('scroll')
    expect(idle.emitted('load-more')).toBeUndefined()
  })
  it('does not ask again while a page is loading', async () => {
    const w = mk({ hasMore: { Open: true }, loadingMore: { Open: true } })
    const box = w.findAll('section')[0].find('div.overflow-y-auto')
    Object.defineProperty(box.element, 'scrollHeight', { value: 400, configurable: true })
    await box.trigger('scroll')
    expect(w.emitted('load-more')).toBeUndefined()
  })
  it('custom card slot', () => {
    const w = mount(KanbanBoard, { props: { columns: ['Open'], cards }, slots: { card: '<template #card="{ card }"><b>{{ card.name }}!</b></template>' } })
    expect(w.text()).toContain('A!')
  })
})

describe('EmailQueueStrip', () => {
  const overview = (o = {}) => ({ counts: { Sent: 3, Error: 1 }, suspended: false, muted: false, ...o })

  it('loads and shows a count per status', async () => {
    callMock.mockResolvedValue(overview())
    const w = mount(EmailQueueStrip)
    await flushPromises()
    expect(callMock).toHaveBeenCalledWith('verp_staffing.utils.email_queue.get_queue_overview')
    const sent = w.findAll('button').find((b) => b.text().startsWith('Sent'))
    expect(sent.text()).toContain('3')
    expect(w.findAll('button').find((b) => b.text().startsWith('Expired')).text()).toContain('–')
  })
  it('shows warnings for suspended and muted queues', async () => {
    callMock.mockResolvedValue(overview({ suspended: true }))
    const w = mount(EmailQueueStrip)
    await flushPromises()
    expect(w.text()).toContain('Sending is suspended')
    callMock.mockResolvedValue(overview({ muted: true }))
    const m = mount(EmailQueueStrip)
    await flushPromises()
    expect(m.text()).toContain('switched off in the site configuration')
  })
  it('clicking a status filters, clicking it again clears', async () => {
    callMock.mockResolvedValue(overview())
    const w = mount(EmailQueueStrip)
    await flushPromises()
    const error = () => w.findAll('button').find((b) => b.text().startsWith('Error'))
    await error().trigger('click')
    await error().trigger('click')
    expect(w.emitted('filter')).toEqual([['status=Error'], ['']])
  })
  it('suspend / resume flips the switch and says so', async () => {
    callMock.mockResolvedValueOnce(overview())
    const w = mount(EmailQueueStrip)
    await flushPromises()
    callMock.mockResolvedValueOnce(overview({ suspended: true }))
    await w.findAll('button').find((b) => b.text() === 'Suspend sending').trigger('click')
    await flushPromises()
    expect(callMock).toHaveBeenLastCalledWith('verp_staffing.utils.email_queue.set_sending', { enable: 0 })
    expect(notifyMock.success).toHaveBeenCalledWith('Sending suspended')
    callMock.mockResolvedValueOnce(overview())
    await w.findAll('button').find((b) => b.text() === 'Resume sending').trigger('click')
    await flushPromises()
    expect(callMock).toHaveBeenLastCalledWith('verp_staffing.utils.email_queue.set_sending', { enable: 1 })
    expect(notifyMock.success).toHaveBeenLastCalledWith('Sending resumed')
  })
  it('a failed toggle shows the error', async () => {
    callMock.mockResolvedValueOnce(overview())
    const w = mount(EmailQueueStrip)
    await flushPromises()
    callMock.mockRejectedValueOnce({ status: 403, message: 'Nope' })
    await w.findAll('button').find((b) => b.text() === 'Suspend sending').trigger('click')
    await flushPromises()
    expect(notifyMock.error).toHaveBeenCalledWith('Nope')
  })
  it('a failed load hides the switch instead of crashing', async () => {
    callMock.mockRejectedValue(new Error('x'))
    const w = mount(EmailQueueStrip)
    await flushPromises()
    expect(w.text()).not.toContain('sending')
  })
})

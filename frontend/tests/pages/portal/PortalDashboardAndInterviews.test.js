import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, reactive } from 'vue'

const h = vi.hoisted(() => ({ portal: null }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('frappe-ui', () => ({ Dialog: { template: '<div />' } }))
vi.mock('@/composables/portal/usePortal', () => ({ usePortal: () => h.portal }))
vi.mock('@/utils/common/siteTime', () => ({ siteTimeZone: () => 'UTC', siteTodayIso: () => '2026-05-15', zoneAbbr: (z) => z || '' }))
vi.mock('@/utils/portal/status', () => ({ money: (n, c) => `${c || ''}${n}`, serviceTheme: () => 'gray', interviewTheme: () => 'gray' }))
vi.mock('@/components/ui/AppBadge.vue', () => ({ default: { template: '<div class="stub"><slot /></div>' } }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<div class="stub"><slot /></div>' } }))
vi.mock('@/components/ui/AppSkeleton.vue', () => ({ default: { template: '<div class="stub"><slot /></div>' } }))
vi.mock('@/components/ui/AppDatePicker.vue', () => ({ default: { template: '<div class="stub"><slot /></div>' } }))
vi.mock('@/components/ui/AppSearchInput.vue', () => ({ default: { template: '<div class="stub"><slot /></div>' } }))
vi.mock('@/components/common/SectionCard.vue', () => ({ default: { template: '<div class="stub"><slot /></div>' } }))
vi.mock('@/components/common/StateBanner.vue', () => ({ default: { template: '<div class="stub"><slot /></div>' } }))
vi.mock('@/components/portal/PortalDocumentList.vue', () => ({ default: { template: '<div class="stub"><slot /></div>' } }))

import Dashboard from '@/pages/portal/PortalDashboardPage.vue'
import Interviews from '@/pages/portal/PortalInterviewsPage.vue'

const round = (date, o = {}) => ({ round: 'R1', date_of_interview: date, status: 'Scheduled', from_time: '10:00', to_time: '11:00', time_zone: 'IST', ...o })
const portal = (o = {}) => ({
  data: ref({ user_name: 'Pat Doe', lead_documents: [] }), loading: ref(false), error: ref(''),
  services: ref([1, 2, 3, 4].map((i) => ({ key: i, label: 'S' + i, rec: { status: 'Pending' } }))), counts: ref({ completed: 1, progress: 2, pending: 1, rework: 0 }),
  unread: ref(0), interviews: ref([]), interviewsLoaded: ref(true), loadInterviews: vi.fn(), accounts: ref(null),
  loadAccounts: vi.fn(), load: vi.fn(), docNames: reactive({}), ...o,
})
beforeEach(() => { h.portal = portal() })

describe('PortalDashboardPage', () => {
  it('loads interviews and accounts on open', () => {
    mount(Dashboard)
    expect(h.portal.loadInterviews).toHaveBeenCalled()
    expect(h.portal.loadAccounts).toHaveBeenCalled()
  })
  it('first name, with a fallback', () => {
    expect(mount(Dashboard).vm.firstName).toBe('Pat')
    h.portal.data.value = { user_name: '', lead_documents: [] }
    expect(mount(Dashboard).vm.firstName).toBe('there')
    h.portal.data.value = null
    expect(mount(Dashboard).vm.firstName).toBe('there')
  })
  it('completion percentage and bar segments', () => {
    const w = mount(Dashboard)
    expect(w.vm.pct).toBe(25)
    expect(w.vm.segments.map((s) => s.width)).toEqual(['25%', '50%', '25%', '0%'])
  })
  it('no services is 0% and never divides by zero', () => {
    h.portal.services.value = []
    h.portal.counts.value = { completed: 0, progress: 0, pending: 0, rework: 0 }
    const w = mount(Dashboard)
    expect(w.vm.pct).toBe(0)
    expect(w.vm.segments.every((s) => s.width === '0%')).toBe(true)
  })

  describe('upcoming interviews', () => {
    const rec = (rounds, o = {}) => ({ name: 'I1', company: 'Acme', role: 'Dev', interview_rounds_table: rounds, ...o })
    it('keeps today and later, drops the past, cancelled and rejected', () => {
      h.portal.interviews.value = [rec([
        round('2026-05-14'), round('2026-05-15'), round('2026-05-20', { status: 'Cancelled' }),
        round('2026-05-21', { status: 'Rejected by client' }), round('2026-06-01'), round(''),
      ])]
      expect(mount(Dashboard).vm.upcoming.map((u) => u.d)).toEqual(['2026-05-15', '2026-06-01'])
    })
    it('sorted soonest first across interviews and capped at four', () => {
      h.portal.interviews.value = [
        rec(['2026-07-01', '2026-06-01', '2026-08-01'].map((d) => round(d)), { name: 'A' }),
        rec(['2026-05-16', '2026-05-17', '2026-05-18'].map((d) => round(d)), { name: 'B' }),
      ]
      const u = mount(Dashboard).vm.upcoming
      expect(u).toHaveLength(4)
      expect(u.map((x) => x.d)).toEqual(['2026-05-16', '2026-05-17', '2026-05-18', '2026-06-01'])
    })
    it('fills blanks and shows the time with its zone', () => {
      h.portal.interviews.value = [{ name: 'I', interview_rounds_table: [round('2026-05-20', { round: '' })] }]
      const u = mount(Dashboard).vm.upcoming[0]
      expect([u.company, u.role, u.round]).toEqual(['-', '-', '-'])
      expect(u.time).toBe('10:00 – 11:00 IST')
      expect(u.day).toBe(20)
    })
    it('no time range, no time text', () => {
      h.portal.interviews.value = [rec([round('2026-05-20', { to_time: '' })])]
      expect(mount(Dashboard).vm.upcoming[0].time).toBe('')
    })
    it('an interview with no rounds is skipped', () => {
      h.portal.interviews.value = [rec(undefined)]
      expect(mount(Dashboard).vm.upcoming).toEqual([])
    })
  })

  describe('documents', () => {
    it('counts a document as uploaded by its file or by a known name', () => {
      h.portal.data.value = { lead_documents: [{ field: 'a', file_name: 'a.pdf' }, { field: 'b' }, { field: 'c' }] }
      h.portal.docNames.c = 'c.pdf'
      const w = mount(Dashboard)
      expect(w.vm.uploadedDocs).toBe(2)
      expect(w.vm.missingDocs.map((d) => d.field)).toEqual(['b'])
      expect(Math.round(w.vm.docPct)).toBe(67)
    })
    it('none required is 0% not NaN', () => {
      expect(mount(Dashboard).vm.docPct).toBe(0)
    })
  })

  describe('kpis', () => {
    it('outstanding is a dash until accounts arrive, then formatted in the invoice currency', () => {
      expect(mount(Dashboard).vm.kpis[3].value).toBe('–')
      h.portal.accounts.value = { totals: { outstanding: 250 }, invoices: [{ currency: 'USD' }], orders: [] }
      expect(mount(Dashboard).vm.kpis[3].value).toBe('USD250')
    })
    it('falls back to the order currency', () => {
      h.portal.accounts.value = { totals: { outstanding: 5 }, invoices: [], orders: [{ currency: 'EUR' }] }
      expect(mount(Dashboard).vm.currency).toBe('EUR')
    })
    it('services, completed and interviews tiles', () => {
      h.portal.interviews.value = [{}, {}]
      const k = mount(Dashboard).vm.kpis
      expect([k[0].value, k[1].value, k[2].value]).toEqual([4, 1, 2])
    })
  })
})

describe('PortalInterviewsPage', () => {
  const data = () => [
    { name: '1', company: 'Acme', role: 'Dev', status: 'Scheduled', interview_rounds_table: [{ date_of_interview: '2026-05-10' }] },
    { name: '2', company: 'Beta', role: 'QA', status: 'Completed', interview_rounds_table: [{ date: '2026-06-10' }] },
    { name: '3', company: 'Gamma', role: 'Ops', status: 'Scheduled', interview_rounds_table: [] },
  ]
  const page = () => { h.portal.interviews.value = data(); return mount(Interviews) }

  it('loads on open', () => {
    mount(Interviews)
    expect(h.portal.load).toHaveBeenCalled()
    expect(h.portal.loadInterviews).toHaveBeenCalled()
  })
  it('no filters shows everything', () => expect(page().vm.rows).toHaveLength(3))
  it('search matches company, role and status, case-insensitively', () => {
    const w = page()
    w.vm.query = 'ACME'; expect(w.vm.rows.map((r) => r.name)).toEqual(['1'])
    w.vm.query = 'qa'; expect(w.vm.rows.map((r) => r.name)).toEqual(['2'])
    w.vm.query = 'scheduled'; expect(w.vm.rows.map((r) => r.name)).toEqual(['1', '3'])
    w.vm.query = '  '; expect(w.vm.rows).toHaveLength(3)
  })
  it('date range keeps interviews with a round inside it, using either date field', () => {
    const w = page()
    w.vm.from = '2026-05-01'; w.vm.to = '2026-05-31'
    expect(w.vm.rows.map((r) => r.name)).toEqual(['1'])
    w.vm.from = '2026-06-01'; w.vm.to = ''
    expect(w.vm.rows.map((r) => r.name)).toEqual(['2'])
    w.vm.from = ''; w.vm.to = '2026-05-31'
    expect(w.vm.rows.map((r) => r.name)).toEqual(['1'])
  })
  it('a date filter drops interviews with no rounds', () => {
    const w = page()
    w.vm.from = '2000-01-01'
    expect(w.vm.rows.map((r) => r.name)).not.toContain('3')
  })
  it('search and dates combine; clear resets all', () => {
    const w = page()
    w.vm.query = 'acme'; w.vm.from = '2026-06-01'
    expect(w.vm.rows).toEqual([])
    w.vm.clear()
    expect([w.vm.query, w.vm.from, w.vm.to]).toEqual(['', '', ''])
    expect(w.vm.rows).toHaveLength(3)
  })
  it('showFull is driven by the selected text and can only be closed', () => {
    const w = page()
    expect(w.vm.showFull).toBe(false)
    w.vm.full = 'long text'
    expect(w.vm.showFull).toBe(true)
    w.vm.showFull = true
    expect(w.vm.full).toBe('long text')
    w.vm.showFull = false
    expect(w.vm.full).toBe('')
  })
})

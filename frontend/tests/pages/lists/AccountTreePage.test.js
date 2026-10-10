import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { reactive, nextTick } from 'vue'

const h = vi.hoisted(() => ({
  route: { query: {} }, push: vi.fn(), call: vi.fn(), notify: { success: vi.fn(), error: vi.fn() },
  res: {}, tree: { expandAll: vi.fn(), collapseAll: vi.fn(), reload: vi.fn(), refreshNode: vi.fn() },
}))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: h.push }) }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), Dialog: { props: ['modelValue'], template: '<div class="dlg" :data-open="modelValue"><slot name="body-content" /><slot name="actions" /></div>' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/errors', () => ({ normalizeError: (e) => ({ message: e.message }) }))
vi.mock('@/utils/common/defaultCurrency', () => ({ moneyOptions: (c) => (c ? { style: 'currency', currency: c } : {}) }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (opts) => {
    const key = opts.url.split('.').pop()
    return h.res[key]
  },
}))
const passthrough = (cls) => ({ props: ['modelValue', 'label', 'tooltip', 'disabled', 'options'], emits: ['click', 'update:modelValue'], template: `<button class="${cls}" :data-tip="tooltip" :data-label="label" :disabled="disabled" @click="$emit('click')"><slot /></button>` })
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { props: ['tooltip', 'disabled', 'loading'], emits: ['click'], template: '<button class="ab" :data-tip="tooltip" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>' } }))
vi.mock('@/components/ui/AppSearchInput.vue', () => ({ default: { props: ['modelValue'], emits: ['update:modelValue'], template: '<div><input class="search" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" /><slot name="suffix" /></div>' } }))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { props: ['modelValue', 'label'], template: '<i class="ai" :data-label="label" />' } }))
vi.mock('@/components/ui/AppCheckbox.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppCombobox.vue', () => ({ default: { props: ['modelValue', 'options'], template: '<div class="combo" :data-v="modelValue" :data-n="options.length" />' } }))
vi.mock('@/components/common/SearchSyntaxPopover.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/AppLinkField.vue', () => ({ default: { template: '<i class="alf" />' } }))
vi.mock('@/components/common/StateBanner.vue', () => ({ default: { props: ['title'], template: '<div class="banner">{{ title }}</div>' } }))
vi.mock('@/components/common/SubNavbar.vue', () => ({ default: { template: '<div><slot /><slot name="right" /></div>' } }))
vi.mock('@/components/tree/DocTreeView.vue', () => ({
  default: { props: ['loader', 'afterLoad', 'columns', 'search'], emits: ['open'], setup(_, { expose }) { expose(h.tree); return {} }, template: '<div class="tree" />' },
}))

import Page from '@/pages/lists/AccountTreePage.vue'

const resource = (data) => reactive({ resource: { data }, isLoading: false })
function setup({ companies = [{ name: 'Acme' }, { name: 'Beta' }], balances = 0, write = true, fields } = {}) {
  h.res = {
    get_list: resource(companies),
    get_single_value: resource(balances),
    get_doc_meta: resource({ perms: { write }, fields: fields || [{ fieldname: 'account_type', options: '\nBank\nCash' }] }),
  }
}
const open = async (opts) => { setup(opts); const w = mount(Page); await flushPromises(); return w }

beforeEach(() => { vi.clearAllMocks(); h.route.query = {}; h.call.mockReset() })

describe('AccountTreePage company', () => {
  it('defaults to the first company', async () => {
    const w = await open()
    expect(w.find('.combo').attributes('data-v')).toBe('Acme')
  })
  it('honours ?company= only if it exists', async () => {
    h.route.query = { company: 'Beta' }
    expect((await open()).find('.combo').attributes('data-v')).toBe('Beta')
    h.route.query = { company: 'Nope' }
    expect((await open()).find('.combo').attributes('data-v')).toBe('Acme')
  })
  it('asks for a company when there is none', async () => {
    expect((await open({ companies: [] })).text()).toContain('No company yet')
  })
  it('?search= seeds the search box', async () => {
    h.route.query = { search: 'bank' }
    expect((await open()).find('.search').element.value).toBe('bank')
  })
})

describe('AccountTreePage loading', () => {
  it('loads children for the company, root vs child', async () => {
    const w = await open()
    h.call.mockResolvedValue([])
    await w.vm.loadChildren(null)
    expect(h.call).toHaveBeenLastCalledWith('verp_staffing.accounts.utils.utils.get_children', { doctype: 'Account', parent: '', company: 'Acme', is_root: true })
    await w.vm.loadChildren('Assets - A')
    expect(h.call.mock.lastCall[1]).toMatchObject({ parent: 'Assets - A', is_root: false })
  })

  it('balance column only when Accounts Settings enables it', async () => {
    expect((await open({ balances: 0 })).vm.columns.map((c) => c.key)).not.toContain('balance')
    expect((await open({ balances: '1' })).vm.columns.map((c) => c.key)).toContain('balance')
  })

  it('balances are attached with signs and currency', async () => {
    const w = await open({ balances: 1 })
    const nodes = [{ value: 'A', account_currency: 'USD' }, { value: 'B', account_currency: 'USD' }]
    h.call.mockResolvedValue([{ value: 'A', balance: 150, company_currency: 'USD' }, { value: 'B', balance: -20, company_currency: 'USD' }, { value: 'zzz', balance: 1 }])
    await w.vm.attachBalances(nodes)
    expect(nodes[0].balanceText).toContain('150')
    expect(nodes[1].balanceText).toMatch(/-.*20|20.*-/)
    expect(nodes[1].balance).toBe(-20)
  })

  it('skips the call without the setting or without nodes, and survives a failure', async () => {
    let w = await open({ balances: 0 })
    await w.vm.attachBalances([{ value: 'A' }])
    expect(h.call).not.toHaveBeenCalled()
    w = await open({ balances: 1 })
    await w.vm.attachBalances([])
    expect(h.call).not.toHaveBeenCalled()
    h.call.mockRejectedValue(new Error('x'))
    await expect(w.vm.attachBalances([{ value: 'A' }])).resolves.toBeUndefined()
  })

  it('opens the ledger for an account', async () => {
    const w = await open()
    w.vm.viewLedger({ value: 'Cash - A' })
    expect(h.push).toHaveBeenCalledWith({ path: '/report/General%20Ledger', query: { company: 'Acme', account: 'Cash - A' } })
  })
})

describe('AccountTreePage creating accounts', () => {
  it('only users who can write get the New Account button', async () => {
    expect((await open({ write: true })).find('[data-tip="New Account"]').exists()).toBe(true)
    expect((await open({ write: false })).find('[data-tip="New Account"]').exists()).toBe(false)
  })

  it('a root account needs a name and a root type', async () => {
    const w = await open()
    w.vm.openNew(null)
    expect(w.vm.canSubmitNew).toBeFalsy()
    w.vm.form.account_name = 'Assets'
    expect(w.vm.canSubmitNew).toBeFalsy()
    w.vm.form.root_type = 'Asset'
    expect(w.vm.canSubmitNew).toBeTruthy()
  })

  it('a child inherits its parents root type and only needs a name', async () => {
    const w = await open()
    w.vm.openNew({ value: 'Assets - A', label: 'Assets', root_type: 'Asset' })
    expect(w.vm.form.root_type).toBe('Asset')
    w.vm.form.account_name = '  Bank  '
    expect(w.vm.canSubmitNew).toBeTruthy()
  })

  it('re-opening resets the form', async () => {
    const w = await open()
    w.vm.openNew(null)
    w.vm.form.account_name = 'old'
    w.vm.openNew(null)
    expect(w.vm.form.account_name).toBe('')
  })

  it('creates a child, trims the name, then refreshes just that node', async () => {
    const w = await open()
    const parent = { value: 'Assets - A', label: 'Assets', root_type: 'Asset' }
    w.vm.openNew(parent)
    w.vm.form.account_name = '  Bank  '
    w.vm.form.is_group = true
    h.call.mockResolvedValue({})
    await w.vm.createAccount()
    expect(h.call).toHaveBeenCalledWith('verp_staffing.accounts.utils.utils.add_ac', expect.objectContaining({
      company: 'Acme', parent: 'Assets - A', is_root: 0, account_name: 'Bank', is_group: 1, root_type: 'Asset',
    }))
    expect(h.notify.success).toHaveBeenCalled()
    expect(h.tree.refreshNode).toHaveBeenCalledWith(parent)
    expect(w.vm.showNew).toBe(false)
  })

  it('creating a root reloads the whole tree', async () => {
    const w = await open()
    w.vm.openNew(null)
    w.vm.form.account_name = 'Assets'; w.vm.form.root_type = 'Asset'
    h.call.mockResolvedValue({})
    await w.vm.createAccount()
    expect(h.call.mock.lastCall[1]).toMatchObject({ parent: '', is_root: 1 })
    expect(h.tree.reload).toHaveBeenCalled()
  })

  it('a failure keeps the dialog open and says why', async () => {
    const w = await open()
    w.vm.openNew(null)
    w.vm.form.account_name = 'Assets'; w.vm.form.root_type = 'Asset'
    h.call.mockRejectedValue(new Error('Duplicate'))
    await w.vm.createAccount()
    expect(h.notify.error).toHaveBeenCalledWith('Duplicate')
    expect(w.vm.showNew).toBe(true)
    expect(w.vm.creating).toBe(false)
  })

  it('Account Type options come from the doctype meta', async () => {
    const w = await open()
    expect(w.vm.accountTypes).toEqual(['', 'Bank', 'Cash'])
  })
})

describe('AccountTreePage search', () => {
  it('the first search expands the whole chart', async () => {
    const w = await open()
    await w.find('.search').setValue('bank')
    await nextTick()
    expect(h.tree.expandAll).toHaveBeenCalledTimes(1)
    await w.find('.search').setValue('bank2')
    expect(h.tree.expandAll).toHaveBeenCalledTimes(1)
  })
  it('clear search is disabled until there is something to clear', async () => {
    const w = await open()
    const clear = w.find('[data-tip="Clear search"]')
    expect(clear.attributes('disabled')).toBeDefined()
    await w.find('.search').setValue('x')
    expect(w.find('[data-tip="Clear search"]').attributes('disabled')).toBeUndefined()
    await w.find('[data-tip="Clear search"]').trigger('click')
    expect(w.find('.search').element.value).toBe('')
  })
})

import { describe, it, expect } from 'vitest'
import { roleModule, groupRolesByModule, MODULE_ORDER } from '@/configs/detail/roleModules'

describe('roleModule', () => {
  it.each([
    ['Accounts Manager', 'Accounts'], ['Account Person', 'Accounts'], ['Purchase User', 'Accounts'], ['_show_accounting', 'Accounts'],
    ['Lead Manager', 'Lead'], ['Sales Person', 'Sales'], ['CR', 'CRM'], ['Recruiter', 'CRM'], ['Senior Recruiter', 'CRM'],
    ['Marketing Master Manager', 'Marketing'], ['Technical Coordinator', 'Technical'],
    ['HR Manager', 'HR'], ['Onboarding Person', 'HR'], ['Resume Person', 'HR'], ['RUC Person', 'HR'],
    ['eSign Manager', 'eSign'], ['E-Sign Admin', 'eSign'], ['Signature Reviewer', 'eSign'], ['OnBoarding Person', 'HR'], ['Website Manager', 'Website'], ['Chat Admin', 'Chat'],
    ['System Manager', 'System'], ['_show_setup', 'System'], ['All', 'System'], ['Guest', 'System'], ['Report Manager', 'System'],
    ['Totally Unknown', 'Other'],
  ])('%s -> %s', (role, module) => expect(roleModule(role)).toBe(module))

  it('does not match on a substring in the middle', () => {
    expect(roleModule('Not A Sales Role')).toBe('Other')
  })
  it('first matching rule wins', () => {
    expect(roleModule('Resume Sales')).toBe('HR')
  })
})

describe('groupRolesByModule', () => {
  it('groups in the fixed module order and omits empty modules', () => {
    const groups = groupRolesByModule(['System Manager', 'Lead Manager', 'Sales Person', 'Mystery', 'Lead Person'])
    expect(groups.map((g) => g.label)).toEqual(['Lead', 'Sales', 'System', 'Other'])
    expect(groups[0].roles).toEqual(['Lead Manager', 'Lead Person'])
  })
  it('empty input, and a stable module list', () => {
    expect(groupRolesByModule([])).toEqual([])
    expect(new Set(MODULE_ORDER).size).toBe(MODULE_ORDER.length)
    expect(MODULE_ORDER.at(-1)).toBe('Other')
  })
  it('every role lands in exactly one group', () => {
    const roles = ['A', 'Sales X', 'Lead Y', 'Chat Z', 'HR Q']
    expect(groupRolesByModule(roles).flatMap((g) => g.roles).sort()).toEqual([...roles].sort())
  })
})

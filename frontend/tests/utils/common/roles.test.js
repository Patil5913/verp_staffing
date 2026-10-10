import { describe, it, expect, afterEach } from 'vitest'
import { isAdministrator, hasRole, isSystemManager } from '@/utils/common/roles'

afterEach(() => { delete window.user; delete window.roles })

describe('roles', () => {
  it('administrator has every role', () => {
    window.user = 'Administrator'
    expect(isAdministrator()).toBe(true)
    expect(hasRole('Anything')).toBe(true)
  })
  it('uses boot roles', () => {
    window.user = 'a@b.com'
    window.roles = ['System Manager']
    expect(isSystemManager()).toBe(true)
    expect(hasRole('Sales')).toBe(false)
  })
  it('tolerates missing roles', () => {
    window.user = 'a@b.com'
    expect(hasRole('x')).toBe(false)
  })
})

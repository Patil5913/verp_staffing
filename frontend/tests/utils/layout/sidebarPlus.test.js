import { describe, it, expect } from 'vitest'
import { canQuickCreateFromSidebar } from '@/utils/layout/sidebarPlus'
import { resolveIconName, ALL_ICON_NAMES } from '@/utils/layout/sidebarIcons'

describe('sidebar', () => {
  it('quick create', () => {
    expect(canQuickCreateFromSidebar('Lead')).toBe(true)
    expect(canQuickCreateFromSidebar('GL Entry')).toBe(false)
    expect(canQuickCreateFromSidebar('ERP Configuration')).toBe(false)
    expect(canQuickCreateFromSidebar('cr')).toBe(false)
    expect(canQuickCreateFromSidebar('')).toBe(false)
    expect(canQuickCreateFromSidebar(null)).toBe(false)
  })
  it('icons resolve to known names', () => {
    expect(resolveIconName('nope')).toBe('circle')
    expect(resolveIconName(undefined, undefined)).toBe('circle')
    expect(ALL_ICON_NAMES).toContain('circle')
    expect(ALL_ICON_NAMES.length).toBe(new Set(ALL_ICON_NAMES).size)
    for (const n of ALL_ICON_NAMES) expect(n).toMatch(/^[a-z0-9-]+$/)
  })
})

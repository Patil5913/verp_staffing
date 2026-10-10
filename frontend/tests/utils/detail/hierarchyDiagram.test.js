import { describe, it, expect } from 'vitest'
import { computeHierarchyDiagram } from '@/utils/detail/hierarchyDiagram'

const H = (parent_role, child_roles) => ({ parent_role, child_roles })

describe('computeHierarchyDiagram validation', () => {
  it('empty', () => {
    expect(computeHierarchyDiagram([]).empty).toBe(true)
    expect(computeHierarchyDiagram(null).empty).toBe(true)
  })
  it('empty parent', () => expect(computeHierarchyDiagram([H('', ['a'])]).error).toMatch(/empty parent/))
  it('self loop', () => expect(computeHierarchyDiagram([H('a', ['a'])]).error).toMatch(/Self-Reference.*a/))
  it('duplicate children', () => expect(computeHierarchyDiagram([H('a', ['b', 'b'])]).error).toMatch(/duplicate children: b/))
  it('no root (cycle of two)', () => expect(computeHierarchyDiagram([H('a', ['b']), H('b', ['a'])]).error).toMatch(/No Root/))
  it('cycle below a root', () => {
    const r = computeHierarchyDiagram([H('r', ['a']), H('a', ['b']), H('b', ['a'])])
    expect(r.error).toMatch(/Circular Reference/)
  })
})

describe('computeHierarchyDiagram layout', () => {
  const r = computeHierarchyDiagram([H('Boss', ['A', 'B']), H('A', ['C'])])
  it('has no error and an entry node', () => {
    expect(r.error).toBeUndefined()
    expect(r.nodes.find((n) => n.isEntry).id).toBe('[Start]')
    expect(r.nodes.map((n) => n.id).sort()).toEqual(['A', 'B', 'Boss', 'C', '[Start]'])
  })
  it('edges include start->root', () => {
    expect(r.edges.map((e) => e.id)).toContain('[Start]->Boss')
    expect(r.edges).toHaveLength(4)
  })
  it('levels increase downward and siblings do not overlap', () => {
    const n = Object.fromEntries(r.nodes.map((x) => [x.id, x]))
    expect(n.Boss.y).toBeGreaterThan(n['[Start]'].y)
    expect(n.C.y).toBeGreaterThan(n.A.y)
    expect(Math.abs(n.A.x - n.B.x)).toBeGreaterThanOrEqual(185)
    expect(n.Boss.isStart).toBe(true)
    expect(n.Boss.reports).toBe(2)
  })
  it('all x inside the canvas', () => {
    for (const n of r.nodes) {
      expect(n.x - 80).toBeGreaterThanOrEqual(0)
      expect(n.x + 80).toBeLessThanOrEqual(r.width)
    }
  })
  it('multiple roots hang from Start', () => {
    const m = computeHierarchyDiagram([H('R1', ['x']), H('R2', ['y'])])
    expect(m.edges.map((e) => e.id)).toEqual(expect.arrayContaining(['[Start]->R1', '[Start]->R2']))
  })
})

import { describe, it, expect } from 'vitest'
import fs from 'fs'
import path from 'path'

// Every local import (`@/...` or relative) in the source must point at a file that exists,
// so a moved or renamed module fails here instead of at build or in the browser.
const SRC = path.resolve(__dirname, '../src')
const EXTENSIONS = ['', '.js', '.vue', '.json', '.css', '/index.js', '/index.vue']
const IMPORT_RE = /(?:import|export)\s[^'"`]*?from\s*['"]([^'"]+)['"]|import\s*['"]([^'"]+)['"]|import\(\s*['"]([^'"]+)['"]\s*\)/g

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) return e.name === 'node_modules' ? [] : walk(p)
    return /\.(js|vue)$/.test(e.name) && !/\.test\.js$/.test(e.name) ? [p] : []
  })
}

function resolves(from, spec) {
  const base = spec.startsWith('@/') ? path.join(SRC, spec.slice(2)) : path.resolve(path.dirname(from), spec)
  return EXTENSIONS.some((ext) => {
    const candidate = base + ext
    return fs.existsSync(candidate) && fs.statSync(candidate).isFile()
  })
}

describe('local imports', () => {
  const files = walk(SRC)
  it('scans a meaningful number of files', () => expect(files.length).toBeGreaterThan(100))

  it('all resolve to existing files', () => {
    const broken = []
    for (const file of files) {
      const src = fs.readFileSync(file, 'utf8')
      for (const m of src.matchAll(IMPORT_RE)) {
        const spec = m[1] || m[2] || m[3]
        if (!spec || !(spec.startsWith('@/') || spec.startsWith('./') || spec.startsWith('../'))) continue
        if (spec.includes('${')) continue
        if (!resolves(file, spec)) broken.push(`${path.relative(SRC, file)} -> ${spec}`)
      }
    }
    expect(broken).toEqual([])
  })
})

import { describe, it, expect } from 'vitest'
import fs from 'fs'
import path from 'path'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'

// Every single-file component must parse and compile: script (incl. <script setup> macros), template and styles.
// A typo that would only surface at `vite build` fails here instead.
const SRC = path.resolve(__dirname, '../../src')

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) return walk(p)
    return e.name.endsWith('.vue') ? [p] : []
  })
}
const files = walk(SRC)

describe('single-file components compile', () => {
  it('finds the components', () => expect(files.length).toBeGreaterThan(100))

  it.each(files.map((f) => [path.relative(SRC, f), f]))('%s', (_rel, file) => {
    const source = fs.readFileSync(file, 'utf8')
    const { descriptor, errors } = parse(source, { filename: file })
    expect(errors.map((e) => e.message)).toEqual([])

    const id = path.basename(file)
    let bindings
    if (descriptor.script || descriptor.scriptSetup) {
      const script = compileScript(descriptor, { id })
      bindings = script.bindings
    }
    if (descriptor.template) {
      const out = compileTemplate({ source: descriptor.template.content, filename: file, id, compilerOptions: { bindingMetadata: bindings } })
      expect(out.errors.map((e) => (typeof e === 'string' ? e : e.message))).toEqual([])
    }
    for (const style of descriptor.styles) {
      const out = compileStyle({ source: style.content, filename: file, id, scoped: style.scoped })
      expect(out.errors.map((e) => e.message)).toEqual([])
    }
  })
})

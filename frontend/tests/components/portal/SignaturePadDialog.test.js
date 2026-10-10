import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// jsdom has no canvas: a recording fake stands in for the 2d context.
const draws = []
const ctx = () => ({
  clearRect: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn((x, y) => draws.push(['m', x, y])), lineTo: vi.fn((x, y) => draws.push(['l', x, y])), stroke: vi.fn(),
  fillText: vi.fn(), measureText: vi.fn((t) => ({ width: t.length * 10 })), drawImage: vi.fn(),
  getImageData: vi.fn(() => ({ data: new Uint8ClampedArray(4) })), font: '', lineWidth: 0,
})
let lastCtx
beforeEach(() => {
  draws.length = 0
  lastCtx = ctx()
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => lastCtx)
  vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockImplementation(() => 'data:image/png;base64,SIG')
  vi.spyOn(HTMLCanvasElement.prototype, 'getBoundingClientRect').mockReturnValue({ left: 0, top: 0, width: 200, height: 100 })
  document.fonts = { load: vi.fn(async () => {}) }
  document.body.style.overflow = ''
})
afterEach(() => vi.restoreAllMocks())

import SignaturePadDialog from '@/components/portal/SignaturePadDialog.vue'

const mk = async () => {
  const w = mount(SignaturePadDialog, { props: { modelValue: false }, global: { stubs: { Teleport: true } } })
  await w.setProps({ modelValue: true })
  await flushPromises()
  return w
}
const save = (w) => w.find('.sg-save').trigger('click')
const tab = (w, label) => w.findAll('.sg-tabs button').find((b) => b.text() === label)

describe('SignaturePadDialog', () => {
  it('opens on the Draw tab and locks page scroll while open, restoring it after', async () => {
    const w = await mk()
    expect(tab(w, 'Draw').classes()).toContain('active')
    expect(document.body.style.overflow).toBe('hidden')
    await w.setProps({ modelValue: false })
    expect(document.body.style.overflow).toBe('')
  })
  it('destroying the dialog while it is open gives the page its scrolling back', async () => {
    const w = await mk()
    expect(document.body.style.overflow).toBe('hidden')
    w.unmount()
    expect(document.body.style.overflow).toBe('')
  })
  it('renders nothing while closed', () => {
    expect(mount(SignaturePadDialog, { props: { modelValue: false }, global: { stubs: { Teleport: true } } }).find('.sg-modal').exists()).toBe(false)
  })
  it('the legal notice is always shown', async () => {
    expect((await mk()).text()).toContain('legally binding electronic signature')
  })

  describe('draw', () => {
    it('an empty pad cannot be saved', async () => {
      const w = await mk()
      await save(w)
      expect(w.text()).toContain('Please draw your signature first.')
      expect(w.emitted('save')).toBeUndefined()
    })
    it('pointer strokes are recorded in canvas pixels, ending on release', async () => {
      const w = await mk()
      const c = w.find('canvas')
      await c.trigger('pointerdown', { clientX: 10, clientY: 20 })
      await c.trigger('pointermove', { clientX: 30, clientY: 40 })
      await c.trigger('pointerup')
      await c.trigger('pointermove', { clientX: 99, clientY: 99 }) // after release: ignored
      expect(w.vm.strokes).toHaveLength(1)
      expect(w.vm.strokes[0]).toHaveLength(2)
      await c.trigger('pointerdown', { clientX: 50, clientY: 50 })
      expect(w.vm.strokes).toHaveLength(2)
    })
    it('Undo removes the last stroke, Clear removes all; both are disabled with nothing drawn', async () => {
      const w = await mk()
      const buttons = () => w.findAll('.sg-tools button')
      expect(buttons().every((b) => b.attributes('disabled') !== undefined)).toBe(true)
      const c = w.find('canvas')
      await c.trigger('pointerdown', { clientX: 1, clientY: 1 }); await c.trigger('pointerup')
      await c.trigger('pointerdown', { clientX: 2, clientY: 2 }); await c.trigger('pointerup')
      expect(w.vm.strokes).toHaveLength(2)
      await buttons()[0].trigger('click')
      expect(w.vm.strokes).toHaveLength(1)
      await buttons()[1].trigger('click')
      expect(w.vm.strokes).toHaveLength(0)
    })
    it('saving hands back the cropped image and says it was drawn, then closes', async () => {
      const w = await mk()
      await w.find('canvas').trigger('pointerdown', { clientX: 5, clientY: 5 })
      await save(w)
      expect(w.emitted('save')).toEqual([[{ dataUrl: 'data:image/png;base64,SIG', method: 'draw' }]])
      expect(w.emitted('update:modelValue').at(-1)).toEqual([false])
    })
    it('the hint disappears once there is ink', async () => {
      const w = await mk()
      expect(w.find('.sg-pad').classes()).not.toContain('has-ink')
      await w.find('canvas').trigger('pointerdown', { clientX: 5, clientY: 5 })
      expect(w.find('.sg-pad').classes()).toContain('has-ink')
    })
  })

  describe('type', () => {
    it('needs a name', async () => {
      const w = await mk()
      await tab(w, 'Type').trigger('click')
      await flushPromises()
      await save(w)
      expect(w.text()).toContain('Please type your name.')
      await w.find('input[type=text]').setValue('   ')
      await save(w)
      expect(w.emitted('save')).toBeUndefined()
    })
    it('previews with the chosen script font and saves it as typed', async () => {
      const w = await mk()
      await tab(w, 'Type').trigger('click')
      await flushPromises()
      await w.find('input[type=text]').setValue('Ann Lee')
      await flushPromises()
      await w.findAll('.font-box')[1].trigger('click')
      await flushPromises()
      expect(document.fonts.load).toHaveBeenLastCalledWith("64px 'Great Vibes', cursive")
      expect(lastCtx.fillText).toHaveBeenCalledWith('Ann Lee', 600, 180)
      await save(w)
      expect(w.emitted('save')).toEqual([[{ dataUrl: 'data:image/png;base64,SIG', method: 'type' }]])
    })
    it('a long name is shrunk to fit the pad, but never below a readable size', async () => {
      const w = await mk()
      await tab(w, 'Type').trigger('click')
      await flushPromises()
      lastCtx.measureText = vi.fn((t) => ({ width: t.length * 100 }))
      await w.find('input[type=text]').setValue('x'.repeat(50))
      await flushPromises()
      const sizes = []
      Object.defineProperty(lastCtx, 'font', { set: (v) => sizes.push(parseInt(v, 10)), get: () => '' })
      w.vm.renderTyped()
      expect(Math.min(...sizes)).toBeGreaterThanOrEqual(30)
      expect(sizes[0]).toBe(150)
    })
    it('offers eight fonts and previews the name in each', async () => {
      const w = await mk()
      await tab(w, 'Type').trigger('click')
      await flushPromises()
      expect(w.findAll('.font-box')).toHaveLength(8)
      expect(w.find('.font-preview').text()).toBe('John Smith')
      await w.find('input[type=text]').setValue('Ann')
      expect(w.find('.font-preview').text()).toBe('Ann')
    })
  })

  describe('upload', () => {
    const choose = async (w, file) => {
      const input = w.find('input[type=file]')
      Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
      await input.trigger('change')
      await new Promise((r) => setTimeout(r, 20))
      await nextTick()
    }
    it('needs an image', async () => {
      const w = await mk()
      await tab(w, 'Upload').trigger('click')
      await save(w)
      expect(w.text()).toContain('Please choose an image of your signature.')
    })
    it('refuses an image over 1 MB and explains', async () => {
      const w = await mk()
      await tab(w, 'Upload').trigger('click')
      await choose(w, new File([new Uint8Array(1024 * 1024 + 1)], 'big.png', { type: 'image/png' }))
      expect(w.text()).toContain('Image size must not exceed 1 MB.')
      expect(w.vm.uploaded).toBe('')
    })
    it('accepts a small image, shows it and saves it as uploaded, untouched', async () => {
      const w = await mk()
      await tab(w, 'Upload').trigger('click')
      await choose(w, new File(['PNGDATA'], 'sig.png', { type: 'image/png' }))
      expect(w.find('.sg-upload-preview img').attributes('src')).toMatch(/^data:image\/png;base64,/)
      await save(w)
      expect(w.emitted('save')[0][0]).toMatchObject({ method: 'upload' })
      expect(w.emitted('save')[0][0].dataUrl).toMatch(/^data:/)
    })
    it('cancelling the file dialog changes nothing', async () => {
      const w = await mk()
      await tab(w, 'Upload').trigger('click')
      const input = w.find('input[type=file]')
      Object.defineProperty(input.element, 'files', { value: [], configurable: true })
      await input.trigger('change')
      expect(w.vm.uploaded).toBe('')
    })
  })

  it('switching tabs clears any message', async () => {
    const w = await mk()
    await save(w)
    expect(w.vm.error).toBeTruthy()
    await tab(w, 'Type').trigger('click')
    expect(w.vm.error).toBe('')
  })
  it('reopening starts clean on Draw', async () => {
    const w = await mk()
    await w.find('canvas').trigger('pointerdown', { clientX: 5, clientY: 5 })
    await tab(w, 'Upload').trigger('click')
    await w.setProps({ modelValue: false })
    await w.setProps({ modelValue: true })
    await flushPromises()
    expect(w.vm.strokes).toEqual([])
    expect(w.vm.mode).toBe('draw')
  })
  it('Cancel, the x and the backdrop all close without saving', async () => {
    for (const sel of ['.sg-cancel', '.sg-x']) {
      const w = await mk()
      await w.find(sel).trigger('click')
      expect(w.emitted('update:modelValue').at(-1)).toEqual([false])
      expect(w.emitted('save')).toBeUndefined()
    }
    const w = await mk()
    await w.find('.sg-overlay').trigger('click')
    expect(w.emitted('update:modelValue').at(-1)).toEqual([false])
  })
  it('clicks inside the dialog do not close it', async () => {
    const w = await mk()
    await w.find('.sg-modal').trigger('click')
    expect(w.emitted('update:modelValue')).toBeUndefined()
  })
})

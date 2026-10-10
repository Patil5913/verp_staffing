import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, nextTick } from 'vue'
import { usePdfPages, PDF_PAGE_SCALE } from '@/composables/detail/usePdfPages'

const fakePdf = (n) => ({
  promise: Promise.resolve({
    numPages: n,
    getPage: async (i) => ({
      getViewport: ({ scale }) => ({ width: 100 * scale, height: 200 * scale }),
      render: () => ({ promise: Promise.resolve() }),
    }),
  }),
})
beforeEach(() => {
  HTMLCanvasElement.prototype.getContext = () => ({})
  HTMLCanvasElement.prototype.toDataURL = () => 'data:image/png;base64,x'
  window.pdfjsLib = { getDocument: vi.fn(() => fakePdf(2)), GlobalWorkerOptions: {} }
})

describe('usePdfPages', () => {
  it('renders every page at the shared scale', async () => {
    const { pages, loading, error } = usePdfPages(ref('/f.pdf'))
    await vi.waitFor(() => expect(pages.value).toHaveLength(2))
    expect(pages.value[0]).toEqual({ number: 1, dataUrl: 'data:image/png;base64,x', width: 100 * PDF_PAGE_SCALE, height: 200 * PDF_PAGE_SCALE })
    expect(loading.value).toBe(false)
    expect(error.value).toBe('')
  })
  it('no url means no pages and no loading', async () => {
    const { pages, loading } = usePdfPages(ref(''))
    await nextTick()
    expect(pages.value).toEqual([])
    expect(loading.value).toBe(false)
    expect(window.pdfjsLib.getDocument).not.toHaveBeenCalled()
  })
  it('reloads when the url changes and clears when it is removed', async () => {
    const url = ref('/a.pdf')
    const { pages } = usePdfPages(url)
    await vi.waitFor(() => expect(pages.value).toHaveLength(2))
    window.pdfjsLib.getDocument.mockReturnValue(fakePdf(1))
    url.value = '/b.pdf'
    await vi.waitFor(() => expect(pages.value).toHaveLength(1))
    url.value = ''
    await vi.waitFor(() => expect(pages.value).toEqual([]))
  })
  it('a render failure is reported, not thrown', async () => {
    window.pdfjsLib.getDocument.mockImplementation(() => ({ promise: Promise.reject(new Error('corrupt')) }))
    const { error, loading, pages } = usePdfPages(ref('/bad.pdf'))
    await vi.waitFor(() => expect(error.value).toBe('corrupt'))
    expect(loading.value).toBe(false)
    expect(pages.value).toEqual([])
  })
  it('a custom scale is used', async () => {
    const { pages } = usePdfPages(ref('/f.pdf'), { scale: 2 })
    await vi.waitFor(() => expect(pages.value[0].width).toBe(200))
  })
})

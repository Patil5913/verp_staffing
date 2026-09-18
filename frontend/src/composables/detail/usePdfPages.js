import { ref, watch } from 'vue'

// Renders every page of a PDF to a plain image once (pdf.js, served from this
// app's own /assets), so an editor can overlay draggable boxes on ordinary
// <img>s instead of a live canvas per page. Shared by the Pdf Agreement
// Template builder and the E Sign builder.
const PDFJS_URL = '/assets/verp_staffing/js/pdf.min.js'
const PDFJS_WORKER = '/assets/verp_staffing/js/pdf.worker.min.js'
let pdfjsPromise = null

function loadPdfjs() {
  if (window.pdfjsLib) return Promise.resolve(window.pdfjsLib)
  if (pdfjsPromise) return pdfjsPromise
  pdfjsPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = PDFJS_URL
    script.onload = () => {
      if (window.pdfjsLib) {
        window.pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS_WORKER
        resolve(window.pdfjsLib)
      } else {
        reject(new Error('pdf.js failed to initialise.'))
      }
    }
    script.onerror = () => reject(new Error('Could not load the PDF viewer (pdf.js).'))
    document.head.appendChild(script)
  })
  return pdfjsPromise
}

export function usePdfPages(pdfUrl, { scale = 1.5 } = {}) {
  const pages = ref([]) // [{ number, dataUrl, width, height }]
  const loading = ref(false)
  const error = ref('')

  async function load() {
    if (!pdfUrl.value) {
      pages.value = []
      return
    }
    loading.value = true
    error.value = ''
    try {
      const pdfjsLib = await loadPdfjs()
      const pdf = await pdfjsLib.getDocument(pdfUrl.value).promise
      const rendered = []
      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i)
        const viewport = page.getViewport({ scale })
        const canvas = document.createElement('canvas')
        canvas.width = viewport.width
        canvas.height = viewport.height
        await page.render({ canvasContext: canvas.getContext('2d'), viewport }).promise
        rendered.push({ number: i, dataUrl: canvas.toDataURL(), width: viewport.width, height: viewport.height })
      }
      pages.value = rendered
    } catch (err) {
      error.value = err?.message || 'Error loading the PDF.'
    } finally {
      loading.value = false
    }
  }

  watch(pdfUrl, load, { immediate: true })
  return { pages, loading, error, reload: load }
}

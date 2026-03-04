// verp_staffing/public/js/pdf_lib_bundle.bundle.js
import * as pdfjs from 'pdfjs-dist/build/pdf.js';

// Attach to window for your existing code
window.pdfjsLib = pdfjs;

// Set worker path
pdfjs.GlobalWorkerOptions.workerSrc = '/assets/verp_staffing/js/pdf.worker.js';

export default pdfjs;

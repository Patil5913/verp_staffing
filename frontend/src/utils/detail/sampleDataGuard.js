import { call } from 'frappe-ui'
import { confirmLeave } from '@/utils/common/confirmDialog'

// Port of public/js/sample_data_guard.js: before a NEW document is saved, warn
// if it links to seeded sample data (which is deleted with it when "Remove
// Sample Data" runs). Same server check, same skip rules, same wording.
const SKIP_DOCTYPES = ['ERP Configuration']

const escapeHtml = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])

// Resolves true to go ahead with the save, false if the user backed out.
export async function confirmSampleDataLinks(doctype, doc) {
  if (SKIP_DOCTYPES.includes(doctype)) return true
  if (window.is_sample_data_removed) return true // cheap in-memory skip

  let links = []
  try {
    links = (await call('verp_staffing.utils.sample_data_guard.check_links_to_sample_data', { doctype, doc })) || []
  } catch {
    return true // never block a save just because the check itself failed
  }
  if (!links.length) return true

  const list = links
    .map((l) => `<li>${escapeHtml(l.label)}: <b>${escapeHtml(l.value)}</b> (${escapeHtml(l.reference_doctype)})</li>`)
    .join('')
  return confirmLeave({
    title: 'Sample data',
    html: `This document links to sample data:<ul>${list}</ul>If the sample data is removed later (via "Remove Sample Data" on ERP Configuration), this entry will be deleted along with it. Save anyway?`,
    leaveLabel: 'Save anyway',
    leaveIcon: 'save',
    cancelLabel: 'Cancel',
  })
}

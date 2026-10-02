// Auto-fills a "Document Title"-style field from an uploaded file's name
// (stripping the extension), without overwriting anything the user already
// typed - used by Resume/Proof Of Work's "Document References" rows.
export function autoTitleFromFile(fileMeta, draft, { titleField = 'document_title' } = {}) {
  if (draft[titleField]) return null
  const name = fileMeta?.file_name || ''
  const title = name.replace(/\.[^./\\]+$/, '')
  return title ? { [titleField]: title } : null
}

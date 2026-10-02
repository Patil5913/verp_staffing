// Doctypes that must never show the sidebar's "+" quick-create action,
// even though they're otherwise ordinary Doctype links (e.g. locked-down
// masters, or doctypes with no sensible standalone "new" form).
export const NO_PLUS_BUTTON_DISPLAY_DOCTYPES = new Set([
  'Onboardings',
  'GL Entry',
  'Supplier Group',
  'CR',
  'Agreement',
  'CRM Note',
  'CRM Event',
  'CRM Task',
  'Lead Detail Form',
  'Sales Stage',
  'Interview Status',
  'Type Of Interview',
  'Other Services',
  'Marketing Other Services',
  'Marketing',
  'Item Category',
  'UOM',
  'Cover Letter',
  'JDC',
  'Resume',
  'RUC',
  'Technical Other Services',
  'Interview Support',
  'Training',
  'Bank Account Type',
  'Bank Account Subtype',
  'Sidebar Master',
  'Email Queue',
  'Erp Configuration',
  'Accounts Settings'
])

// Compared case-insensitively: the doctype is "ERP Configuration", not "Erp Configuration".
const blocked = new Set([...NO_PLUS_BUTTON_DISPLAY_DOCTYPES].map((d) => d.toLowerCase()))

export function canQuickCreateFromSidebar(doctype) {
  return !!doctype && !blocked.has(String(doctype).toLowerCase())
}

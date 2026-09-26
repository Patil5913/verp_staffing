// Which module each role belongs to, for the User page's Roles & Permissions
// tab. First matching rule wins; anything unmatched lands in "Other".
const RULES = [
  ['Accounts', /^(accounts?\b|account person|_show_accounting|purchase)/i],
  ['Lead', /^lead\b/i],
  ['Sales', /^sales\b/i],
  ['CRM', /^(cr|recruiter|senior recruiter)$/i],
  ['Marketing', /^marketing\b/i],
  ['Technical', /^technical\b/i],
  ['HR', /^(hr\b|onboarding|on-?boarding person|resume|senior resume|ruc)/i],
  ['eSign', /e-?sign|signature/i],
  ['Website', /^(website|blogger|newsletter|knowledge base|translator)/i],
  ['Chat', /^chat\b/i],
  ['System', /^(_show_|system manager|administrator|all$|guest$|desk user|dashboard|report|prepared report|script|workspace|inbox|maintenance)/i],
]

export const MODULE_ORDER = ['Accounts', 'Lead', 'Sales', 'CRM', 'Marketing', 'Technical', 'HR', 'eSign', 'Website', 'Chat', 'System', 'Other']

export function roleModule(role) {
  return RULES.find(([, re]) => re.test(role))?.[0] || 'Other'
}

export function groupRolesByModule(roles) {
  const groups = {}
  for (const role of roles) (groups[roleModule(role)] ||= []).push(role)
  return MODULE_ORDER.filter((m) => groups[m]).map((label) => ({ label, roles: groups[label] }))
}

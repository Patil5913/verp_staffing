// Best-effort Badge `theme` for a Select field's value, based on common
// status vocabulary (works across doctypes, not just one specific status
// field) — falls back to plain gray when nothing matches.
const KEYWORD_THEMES = [
  [/won|success|approved|complete|paid|active|accepted/, 'green'],
  [/lost|cancel|reject|fail|inactive|closed|error/, 'red'],
  [/pending|draft|hold|review|interested|waiting/, 'orange'],
  [/open|new|opportunity|progress|working/, 'blue'],
]

export function statusBadgeTheme(value) {
  const v = String(value || '').toLowerCase()
  for (const [pattern, theme] of KEYWORD_THEMES) {
    if (pattern.test(v)) return theme
  }
  return 'gray'
}

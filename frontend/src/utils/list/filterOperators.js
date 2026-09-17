// Frappe's actual supported get_list filter operators, mapped per
// fieldtype. Kept separate from the vendored frappe-ui ListFilter because
// that component only covers Check/Link/Number/Select/Data-ish fields with
// =, !=, like, not like — no Date/Datetime, no between, no is-set/is-not-set
// (see apps/frappe/frappe/model/db_query.py's prepare_filter_condition for
// what the server actually accepts: =, !=, like, not like, in, not in,
// between, >, <, >=, <=, and is "set"/"not set").
export const STRING_FIELDTYPES = [
  'Data',
  'Text',
  'Small Text',
  'Long Text',
  'Text Editor',
  'Code',
  'JSON',
  'Read Only',
]
export const NUMBER_FIELDTYPES = ['Int', 'Float', 'Currency', 'Percent', 'Duration', 'Rating']
export const DATE_FIELDTYPES = ['Date', 'Datetime']
export const LINK_FIELDTYPES = ['Link', 'Dynamic Link']

const IS_OPERATORS = [
  { label: 'Is Set', value: 'is:set' },
  { label: 'Is Not Set', value: 'is:not set' },
]

export function isFilterableField(field) {
  return (
    STRING_FIELDTYPES.includes(field.fieldtype) ||
    NUMBER_FIELDTYPES.includes(field.fieldtype) ||
    DATE_FIELDTYPES.includes(field.fieldtype) ||
    LINK_FIELDTYPES.includes(field.fieldtype) ||
    field.fieldtype === 'Select' ||
    field.fieldtype === 'Check'
  )
}

// Returns the operator dropdown's options. Values are either a real
// backend operator ("=", "like", "between", ...) or a "is:<value>" sentinel
// that onOperatorChange() below expands into the real ["is", "set"/"not set"]
// pair — a plain <select> can only carry one value per option, and "is"
// needs both an operator and a fixed value together.
export function getOperators(fieldtype) {
  if (STRING_FIELDTYPES.includes(fieldtype)) {
    return [
      { label: 'Equals', value: '=' },
      { label: 'Not Equals', value: '!=' },
      { label: 'Like', value: 'like' },
      { label: 'Not Like', value: 'not like' },
      ...IS_OPERATORS,
    ]
  }
  if (LINK_FIELDTYPES.includes(fieldtype)) {
    return [
      { label: 'Equals', value: '=' },
      { label: 'Not Equals', value: '!=' },
      { label: 'Like', value: 'like' },
      { label: 'In', value: 'in' },
      { label: 'Not In', value: 'not in' },
      ...IS_OPERATORS,
    ]
  }
  if (fieldtype === 'Select') {
    return [
      { label: 'Equals', value: '=' },
      { label: 'Not Equals', value: '!=' },
      { label: 'In', value: 'in' },
      { label: 'Not In', value: 'not in' },
    ]
  }
  if (fieldtype === 'Check') {
    return [{ label: 'Equals', value: '=' }]
  }
  if (NUMBER_FIELDTYPES.includes(fieldtype) || DATE_FIELDTYPES.includes(fieldtype)) {
    return [
      { label: 'Equals', value: '=' },
      { label: 'Not Equals', value: '!=' },
      { label: '>', value: '>' },
      { label: '<', value: '<' },
      { label: '>=', value: '>=' },
      { label: '<=', value: '<=' },
      { label: 'Between', value: 'between' },
      ...IS_OPERATORS,
    ]
  }
  return [{ label: 'Equals', value: '=' }]
}

export function getDefaultOperator(fieldtype) {
  return STRING_FIELDTYPES.includes(fieldtype) ? 'like' : '='
}

export function getDefaultValue(field) {
  if (field.fieldtype === 'Select') {
    return (field.options || '').split('\n').filter(Boolean)[0] || ''
  }
  if (field.fieldtype === 'Check') return '1'
  return ''
}

// Which value widget a row should show, given the field and the chosen
// "is:*"-expanded operator. Kept as one function so DocFilterRow doesn't
// have to re-derive this branching itself.
export function getValueKind(field, operator) {
  if (operator === 'is') return 'none'
  if (operator === 'between') {
    return DATE_FIELDTYPES.includes(field.fieldtype) ? 'date-range' : 'number-range'
  }
  if (field.fieldtype === 'Check') return 'check'
  if (field.fieldtype === 'Select') return 'select'
  if (LINK_FIELDTYPES.includes(field.fieldtype) && (operator === '=' || operator === '!=')) {
    return 'link'
  }
  if (operator === 'in' || operator === 'not in') return 'text-list'
  if (DATE_FIELDTYPES.includes(field.fieldtype)) {
    return field.fieldtype === 'Date' ? 'date' : 'datetime'
  }
  if (NUMBER_FIELDTYPES.includes(field.fieldtype)) return 'number'
  return 'text'
}

// Expands the operator dropdown's selected value into the real
// {operator, value} pair to store on the row, resetting `value` to
// something sane for the newly chosen operator so a stale value from the
// previous operator never lingers (e.g. an array left over from "between").
export function applyOperatorChange(field, uiOperator) {
  if (uiOperator.startsWith('is:')) {
    return { operator: 'is', value: uiOperator.slice(3) }
  }
  if (uiOperator === 'between') {
    return { operator: 'between', value: ['', ''] }
  }
  return { operator: uiOperator, value: getDefaultValue(field) }
}

// Inverse of applyOperatorChange, for driving the operator <select>'s value.
export function toUiOperator(operator, value) {
  if (operator === 'is') return `is:${value}`
  return operator
}

const OPERATOR_PHRASES = {
  '=': 'is',
  '!=': 'is not',
  like: 'contains',
  'not like': "doesn't contain",
  in: 'is any of',
  'not in': 'is none of',
  '>': '>',
  '<': '<',
  '>=': '≥',
  '<=': '≤',
  between: 'between',
}

function describeFilterValue(field, operator, value) {
  if (operator === 'is') return value === 'set' ? 'is set' : 'is not set'
  if (operator === 'between') {
    const [a, b] = value || []
    return `${a || '?'} – ${b || '?'}`
  }
  if (field.fieldtype === 'Check') return value == '1' ? 'Yes' : 'No'
  if (operator === 'in' || operator === 'not in') {
    const list = Array.isArray(value)
      ? value
      : String(value || '').split(',').map((v) => v.trim()).filter(Boolean)
    return list.join(', ')
  }
  return value === '' || value == null ? '...' : String(value)
}

// One-line human summary of a filter row, e.g. "Status is Open" or
// "Modified between 2024-01-01 – 2024-02-01" — used by the filter chip bar
// so each active filter is readable without opening its editor.
export function describeFilter(filter) {
  const { field, operator } = filter
  if (operator === 'is') return `${field.label} ${describeFilterValue(field, operator, filter.value)}`
  const phrase = OPERATOR_PHRASES[operator] || operator
  return `${field.label} ${phrase} ${describeFilterValue(field, operator, filter.value)}`
}

import { describe, it, expect } from 'vitest'
import {
  emailProblem, linkedinProblem, phoneProblem, mmYyyyProblem, descriptionLengthProblem,
  ssnDigitProblem, gradeProblem, fieldProblem, rowFieldProblem, rowProblem,
} from '@/utils/detail/fieldProblems'

describe('emailProblem', () => {
  it.each([
    ['a b@c.com', 'Email must not contain spaces'],
    ['abc', 'Email is missing the @ symbol'],
    ['a@b@c.com', 'Email must contain only one @ symbol'],
    ['@c.com', 'Email is missing the part before @'],
    ['a@', 'Email is missing the domain after @ (e.g. gmail.com)'],
    ['a@com', 'Email domain looks incomplete (e.g. name@gmail.com)'],
    ['a@.com', 'Email domain looks incomplete (e.g. name@gmail.com)'],
    ['a@com.', 'Email domain looks incomplete (e.g. name@gmail.com)'],
  ])('%s', (v, msg) => expect(emailProblem(v)).toBe(msg))
  it('accepts valid', () => expect(emailProblem('a@b.com')).toBeNull())
})

describe('linkedinProblem', () => {
  it('flags each case', () => {
    expect(linkedinProblem('linkedin.com/in/x')).toMatch(/start with https/)
    expect(linkedinProblem('https://example.com/in/x')).toMatch(/linkedin\.com/)
    expect(linkedinProblem('https://www.linkedin.com')).toMatch(/profile path/)
    expect(linkedinProblem('https://www.linkedin.com/in/x')).toBeNull()
  })
})

describe('phoneProblem', () => {
  it('flags each case', () => {
    expect(phoneProblem('4155552671')).toMatch(/must start with \+/)
    expect(phoneProblem('+1415abc2671')).toMatch(/only digits/)
    expect(phoneProblem('+0155552671')).toMatch(/cannot start with 0/)
    expect(phoneProblem('+141555')).toMatch(/you entered 6/)
    expect(phoneProblem('+1 (415) 555-2671')).toBeNull()
    expect(phoneProblem('x', 'Mobile')).toMatch(/^Mobile /)
  })
})

describe('misc validators', () => {
  it('mmYyyy', () => {
    expect(mmYyyyProblem('13-2024', 'Start')).toMatch(/^Start must be in MM-YYYY/)
    expect(mmYyyyProblem('01-2024')).toBeNull()
  })
  it('description length ignores whitespace', () => {
    expect(descriptionLengthProblem('a b', 5)).toBe('Description must contain at least 5 characters (currently 2)')
    expect(descriptionLengthProblem('a'.repeat(800))).toBeNull()
  })
  it('ssn', () => {
    expect(ssnDigitProblem('123')).toBeTruthy()
    expect(ssnDigitProblem('1234')).toBeNull()
  })
  it('grade', () => {
    expect(gradeProblem('11')).toBeTruthy()
    expect(gradeProblem('-1')).toBeTruthy()
    expect(gradeProblem('abc')).toBeTruthy()
    expect(gradeProblem('8.5')).toBeNull()
  })
})

describe('fieldProblem', () => {
  it('routes by fieldname', () => {
    expect(fieldProblem({ fieldname: 'email_id' }, 'bad')).toMatch(/@/)
    expect(fieldProblem({ fieldname: 'x', options: 'Email' }, 'bad')).toMatch(/@/)
    expect(fieldProblem({ fieldname: 'personal_linkedin' }, 'x')).toMatch(/LinkedIn/)
    expect(fieldProblem({ fieldname: 'number_for_marketing', label: 'Mkt' }, '1')).toMatch(/^Mkt/)
    expect(fieldProblem({ fieldname: 'entry_date' }, '2024')).toMatch(/MM-YYYY/)
    expect(fieldProblem({ fieldname: 'ssn_digit' }, '1')).toMatch(/SSN/)
    expect(fieldProblem({ fieldname: 'other' }, 'x')).toBeNull()
    expect(fieldProblem({ fieldname: 'email' }, '   ')).toBeNull()
  })
})

describe('row validation', () => {
  it('rowFieldProblem', () => {
    expect(rowFieldProblem('past_experience_table', 'start_date', '2024')).toMatch(/MM-YYYY/)
    expect(rowFieldProblem('address_history', 'to_date', '01-2024')).toBeNull()
    expect(rowFieldProblem('past_experience_table', 'description', 'short')).toMatch(/at least 800/)
    expect(rowFieldProblem('educational_details', 'grade', '99')).toMatch(/Grade/)
    expect(rowFieldProblem('educational_details', 'description', 'x')).toBeNull()
    expect(rowFieldProblem('past_experience_table', 'start_date', '')).toBeNull()
  })
  it('rowProblem requires end_date unless currently working', () => {
    const base = { start_date: '01-2020', description: 'a'.repeat(800) }
    expect(rowProblem('past_experience_table', { ...base })).toMatch(/End date is required/)
    expect(rowProblem('past_experience_table', { ...base, is_currently_working: 1 })).toBeNull()
    expect(rowProblem('past_experience_table', { ...base, end_date: '02-2021' })).toBeNull()
    expect(rowProblem('educational_details', { start_date: 'bad' })).toMatch(/MM-YYYY/)
  })
})

// The server (www/candidate_details.py) enforces the same rules. Both read this one file,
// so the message a user sees on blur is exactly the one the server would return.
import fs from 'fs'
import path from 'path'
const VECTORS = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../../../verp_staffing/tests/validation_vectors.json'), 'utf8'))

describe('shared validation vectors (browser == server)', () => {
  it.each(VECTORS.email)('email %j', (value, expected) => expect(emailProblem(value)).toBe(expected))
  it.each(VECTORS.linkedin)('linkedin %j', (value, expected) => expect(linkedinProblem(value)).toBe(expected))
  it.each(VECTORS.phone)('phone %j', (value, expected) => expect(phoneProblem(value)).toBe(expected))
  it.each(VECTORS.mm_yyyy)('month-year %j', (value, valid) => expect(mmYyyyProblem(value) === null).toBe(valid))
})

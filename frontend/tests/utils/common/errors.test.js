import { describe, it, expect } from 'vitest'
import {
  normalizeError,
  isPermissionError,
  isNotFoundError,
  isAuthError,
  isNetworkError,
  isEmailMissingError,
} from '@/utils/common/errors'

describe('normalizeError', () => {
  it('maps http status via response.status first', () => {
    const e = normalizeError({ response: { status: 403 }, status: 404, message: 'no' })
    expect(e.type).toBe('permission')
    expect(e.statusCode).toBe(403)
    expect(e.title).toBe('Permission denied')
  })

  it('falls back to .status', () => {
    expect(normalizeError({ status: 404 }).type).toBe('not_found')
  })

  it('falls back to exc_type when no status', () => {
    expect(normalizeError({ exc_type: 'frappe.exceptions.DuplicateEntryError' }).type).toBe('conflict')
    expect(normalizeError({ exc_type: 'MandatoryError' }).type).toBe('validation')
  })

  it('prefers messages array, then message, then title', () => {
    expect(normalizeError({ messages: ['a', 'b'] }).message).toBe('a')
    expect(normalizeError({ message: 'm' }).messages).toEqual(['m'])
    expect(normalizeError({}).message).toBe('Something went wrong')
  })

  it('handles string errors', () => {
    const e = normalizeError('boom')
    expect(e).toMatchObject({ type: 'unknown', message: 'boom', messages: ['boom'] })
  })

  it('detects a crashed server (exc_type TypeError)', () => {
    const e = normalizeError(new TypeError("Cannot read properties of undefined (reading 'exc_type')"))
    expect(e.type).toBe('server')
  })

  it('detects a network failure', () => {
    expect(normalizeError(new TypeError('Failed to fetch')).type).toBe('network')
  })

  it('does not treat a TypeError with a response as network', () => {
    expect(normalizeError(Object.assign(new TypeError('x'), { response: { status: 500 } })).type).toBe('unknown')
  })

  it('handles null/undefined', () => {
    expect(normalizeError(null).type).toBe('unknown')
    expect(normalizeError(undefined).type).toBe('unknown')
  })
})

describe('predicates', () => {
  it('classify', () => {
    expect(isPermissionError({ status: 403 })).toBe(true)
    expect(isNotFoundError({ status: 404 })).toBe(true)
    expect(isAuthError({ status: 401 })).toBe(true)
    expect(isNetworkError(new TypeError('Failed to fetch'))).toBe(true)
    expect(isPermissionError({ status: 404 })).toBe(false)
  })
  it('isEmailMissingError matches the server wording', () => {
    expect(isEmailMissingError({ message: 'Customer Email is required to send the form' })).toBe(true)
    expect(isEmailMissingError({ message: 'other' })).toBe(false)
  })
})

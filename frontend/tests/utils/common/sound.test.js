import { describe, it, expect, vi, beforeEach } from 'vitest'

const { play, toastFns } = vi.hoisted(() => ({
  play: vi.fn(),
  toastFns: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))
vi.mock('frappe-ui', () => ({ toast: toastFns }))
vi.mock('@/assets/sounds/on-save.mp3', () => ({ default: 'save.mp3' }))
vi.mock('@/assets/sounds/on-delete.mp3', () => ({ default: 'delete.mp3' }))
vi.mock('@/assets/sounds/other.mp3', () => ({ default: 'other.mp3' }))

import { notify, soundFor } from '@/utils/common/notify'
import { confirmLeave } from '@/utils/common/confirmDialog'
import { playSound } from '@/utils/common/sound'

let played
beforeEach(() => {
  played = []
  play.mockReset()
  play.mockImplementation(function () {
    played.push(this.src)
    return Promise.resolve()
  })
  global.Audio = function (src) {
    this.src = src
    this.play = play
  }
})

describe('soundFor', () => {
  it('maps toast types and delete wording to a cue', () => {
    expect(soundFor('success', 'Saved.')).toBe('save')
    expect(soundFor('success', 'Deleted.')).toBe('delete')
    expect(soundFor('success', '3 records removed')).toBe('delete')
    expect(soundFor('error', 'Something failed')).toBe('delete')
    expect(soundFor('warning', 'Careful')).toBe('delete')
    expect(soundFor('info', 'You have 2 unread messages.')).toBe('other')
  })
})

describe('notify plays the matching sound', () => {
  it.each([
    ['success', 'Saved.', 'save.mp3'],
    ['success', 'Deleted.', 'delete.mp3'],
    ['error', 'Nope', 'delete.mp3'],
    ['warning', 'Hmm', 'delete.mp3'],
    ['info', 'Hello', 'other.mp3'],
  ])('%s "%s"', (type, msg, src) => {
    notify[type](msg)
    expect(played).toEqual([src])
    expect(toastFns[type]).toHaveBeenCalled()
  })

  it('honours an override and silence, and does not pass it to the toast', () => {
    notify.success('New mail', { sound: 'other' })
    notify.success('Saved.', { sound: false })
    expect(played).toEqual(['other.mp3'])
    expect(toastFns.success.mock.calls[0][1]).not.toHaveProperty('sound')
  })

  it('a refused play() never breaks the toast', () => {
    play.mockImplementation(() => Promise.reject(new Error('NotAllowedError')))
    expect(() => notify.success('Saved.')).not.toThrow()
    play.mockImplementation(() => {
      throw new Error('boom')
    })
    expect(() => notify.success('Saved.')).not.toThrow()
  })
})

describe('other places', () => {
  it('an are-you-sure popup plays the delete sound', () => {
    confirmLeave()
    expect(played).toEqual(['delete.mp3'])
  })
  it('unknown kind is ignored', () => {
    playSound('nope')
    expect(played).toEqual([])
  })
})

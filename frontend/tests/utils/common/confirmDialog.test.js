import { describe, it, expect } from 'vitest'
import { confirmLeave, useConfirmDialogState } from '@/utils/common/confirmDialog'

describe('confirmLeave', () => {
  it('opens with defaults and resolves true on leave', async () => {
    const { state, settle } = useConfirmDialogState()
    const p = confirmLeave()
    expect(state.open).toBe(true)
    expect(state.title).toBe('Unsaved changes')
    expect(state.leaveLabel).toBe('Leave without saving')
    expect(state.onSave).toBeNull()
    settle(true)
    await expect(p).resolves.toBe(true)
    expect(state.open).toBe(false)
  })
  it('resolves false on stay and applies custom labels', async () => {
    const { state, settle } = useConfirmDialogState()
    const p = confirmLeave({ title: 'Sure?', leaveLabel: 'Go', cancelLabel: 'No', html: '<b>x</b>' })
    expect([state.title, state.leaveLabel, state.cancelLabel, state.html]).toEqual(['Sure?', 'Go', 'No', '<b>x</b>'])
    settle(false)
    await expect(p).resolves.toBe(false)
  })
  it('a successful save proceeds', async () => {
    const { state, onSaveClick } = useConfirmDialogState()
    const p = confirmLeave({ onSave: async () => true })
    await onSaveClick()
    await expect(p).resolves.toBe(true)
    expect(state.open).toBe(false)
  })
  it('a failed save keeps the dialog open for another choice', async () => {
    const { state, onSaveClick, settle } = useConfirmDialogState()
    const p = confirmLeave({ onSave: async () => false })
    await onSaveClick()
    expect(state.open).toBe(true)
    expect(state.saving).toBe(false)
    settle(false)
    await expect(p).resolves.toBe(false)
  })
  it('save click without a handler does nothing', async () => {
    const { state, onSaveClick, settle } = useConfirmDialogState()
    const p = confirmLeave()
    await onSaveClick()
    expect(state.open).toBe(true)
    settle(false)
    await p
  })
})

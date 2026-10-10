import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { useSaveShortcut } from '@/composables/common/useSaveShortcut'

function setup(dirty = true) {
  const isDirty = ref(dirty)
  const onSave = vi.fn()
  const wrapper = mount(defineComponent({ setup() { useSaveShortcut(isDirty, onSave); return () => null } }))
  return { isDirty, onSave, wrapper }
}
const press = (init) => {
  const e = new KeyboardEvent('keydown', { cancelable: true, bubbles: true, ...init })
  window.dispatchEvent(e)
  return e
}

describe('useSaveShortcut', () => {
  it('Ctrl+S saves when dirty and blocks the browser dialog', () => {
    const { onSave, wrapper } = setup()
    const e = press({ key: 's', ctrlKey: true })
    expect(onSave).toHaveBeenCalledTimes(1)
    expect(e.defaultPrevented).toBe(true)
    wrapper.unmount()
  })
  it('Cmd+S and uppercase S work too', () => {
    const { onSave, wrapper } = setup()
    press({ key: 'S', metaKey: true })
    expect(onSave).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
  it('still blocks the browser dialog when nothing is dirty, without saving', () => {
    const { onSave, wrapper } = setup(false)
    const e = press({ key: 's', ctrlKey: true })
    expect(onSave).not.toHaveBeenCalled()
    expect(e.defaultPrevented).toBe(true)
    wrapper.unmount()
  })
  it('ignores other keys and modifier combinations', () => {
    const { onSave, wrapper } = setup()
    expect(press({ key: 's' }).defaultPrevented).toBe(false)
    expect(press({ key: 'a', ctrlKey: true }).defaultPrevented).toBe(false)
    expect(press({ key: 's', ctrlKey: true, shiftKey: true }).defaultPrevented).toBe(false)
    expect(press({ key: 's', ctrlKey: true, altKey: true }).defaultPrevented).toBe(false)
    expect(onSave).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('stops listening after unmount', () => {
    const { onSave, wrapper } = setup()
    wrapper.unmount()
    press({ key: 's', ctrlKey: true })
    expect(onSave).not.toHaveBeenCalled()
  })
})

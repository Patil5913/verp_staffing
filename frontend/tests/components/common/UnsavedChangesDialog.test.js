import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

vi.mock('frappe-ui', () => ({ FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' } }))

import UnsavedChangesDialog from '@/components/common/UnsavedChangesDialog.vue'
import { confirmLeave } from '@/utils/common/confirmDialog'

const mk = () => mount(UnsavedChangesDialog, { global: { stubs: { Teleport: true, Transition: { template: '<div><slot /></div>' } } } })
const btn = (w, t) => w.findAll('button').find((b) => b.text() === t)

describe('UnsavedChangesDialog', () => {
  it('is hidden until something asks', () => {
    expect(mk().find('[role=alertdialog]').exists()).toBe(false)
  })
  it('shows the default wording and resolves true on leave', async () => {
    const w = mk()
    const p = confirmLeave()
    await nextTick()
    expect(w.text()).toContain('Unsaved changes')
    expect(w.text()).toContain("You have unsaved changes")
    await btn(w, 'Leave without saving').trigger('click')
    await expect(p).resolves.toBe(true)
    await nextTick()
    expect(w.find('[role=alertdialog]').exists()).toBe(false)
  })
  it('Stay resolves false', async () => {
    const w = mk()
    const p = confirmLeave()
    await nextTick()
    await btn(w, 'Stay').trigger('click')
    await expect(p).resolves.toBe(false)
  })
  it('clicking the backdrop stays', async () => {
    const w = mk()
    const p = confirmLeave()
    await nextTick()
    await w.find('.bg-black\\/50').trigger('click')
    await expect(p).resolves.toBe(false)
  })
  it('a Save button appears only when a save handler is given, and a successful save leaves', async () => {
    const w = mk()
    const none = confirmLeave()
    await nextTick()
    expect(btn(w, 'Save')).toBeUndefined()
    await btn(w, 'Stay').trigger('click')
    await none
    const p = confirmLeave({ onSave: async () => true })
    await nextTick()
    await btn(w, 'Save').trigger('click')
    await expect(p).resolves.toBe(true)
  })
  it('custom html is shown, but scripts and handlers never reach the page', async () => {
    const w = mk()
    const p = confirmLeave({ html: '<ul><li>ok <b>bold</b></li></ul><img src=x onerror="window.__pwned=1"><script>window.__pwned=2<\/script>' })
    await nextTick()
    const html = w.html()
    expect(html).toContain('<b>bold</b>')
    expect(html).not.toContain('onerror')
    expect(html).not.toContain('<script')
    expect(window.__pwned).toBeUndefined()
    await btn(w, 'Stay').trigger('click')
    await p
  })
  it('custom labels', async () => {
    const w = mk()
    const p = confirmLeave({ title: 'Delete this note?', message: "This can't be undone.", leaveLabel: 'Delete', cancelLabel: 'Cancel' })
    await nextTick()
    expect(w.text()).toContain('Delete this note?')
    expect(btn(w, 'Delete')).toBeTruthy()
    await btn(w, 'Cancel').trigger('click')
    await p
  })
})

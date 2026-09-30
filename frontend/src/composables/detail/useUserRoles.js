import { computed, ref, watch } from 'vue'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'

// `enabled` holds the fetch back until the viewer may see roles at all (the server refuses otherwise).
export function useUserRoles(user, enabled = computed(() => true)) {
  const matrix = useResource({
    url: 'verp_staffing.utils.user_view.get_roles_matrix',
    makeParams: () => ({ user: user.value }),
  })
  watch(
    [enabled, user],
    ([on]) => {
      if (on) matrix.resource.submit()
    },
    { immediate: true },
  )

  const allRoles = computed(() => matrix.resource.data?.roles || [])
  const checked = ref(new Set())

  watch(
    () => matrix.resource.data,
    (data) => {
      if (data) checked.value = new Set(data.assigned)
    },
  )

  function toggle(role) {
    const next = new Set(checked.value)
    if (next.has(role)) next.delete(role)
    else next.add(role)
    checked.value = next
  }

  const save = useResource({
    url: 'verp_staffing.utils.user_view.set_user_roles',
    onSuccess: (data) => {
      matrix.resource.setData(data)
      checked.value = new Set(data.assigned)
    },
  })

  // Unsaved when the ticked roles differ from what the server has.
  const isDirty = computed(() => {
    const saved = matrix.resource.data?.assigned
    if (!saved) return false
    return saved.length !== checked.value.size || saved.some((r) => !checked.value.has(r))
  })

  // Resolves true/false so the page's Save can fold it in with the main record.
  async function submit() {
    try {
      await save.resource.submit({ user: user.value, roles: [...checked.value] })
      notify.success('Roles saved.')
      return true
    } catch {
      return false
    }
  }

  return {
    matrix,
    allRoles,
    checked,
    toggle,
    submit,
    isDirty,
    saving: computed(() => save.isLoading),
  }
}

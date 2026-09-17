import { computed, ref, watch } from 'vue'
import { useResource } from '@/composables/list/useResource'

export function useUserRoles(user) {
  const matrix = useResource({
    url: 'verp_staffing.utils.user_view.get_roles_matrix',
    makeParams: () => ({ user: user.value }),
    auto: true,
  })

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

  function submit() {
    return save.resource.submit({ user: user.value, roles: [...checked.value] })
  }

  return {
    matrix,
    allRoles,
    checked,
    toggle,
    submit,
    saving: computed(() => save.isLoading),
  }
}

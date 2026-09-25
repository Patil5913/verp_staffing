import { computed, watch } from 'vue'
import { useResource } from '@/composables/list/useResource'

// Whether the current user sits above `assignTo` in `department`'s
// assignment chain - the check the desk Marketing/Interview forms use to
// unlock target, dates and past rows for a manager while keeping them
// locked for the assignee. Fails closed: until the server answers (or if it
// errors) nobody is treated as a superior.
export function useIsSuperior(assignToRef, department) {
  const check = useResource({
    url: 'verp_staffing.crm.api.helpers._is_superior_in_department',
    notifyOnError: false,
  })

  watch(
    assignToRef,
    (assignTo) => {
      if (assignTo) {
        check.resource.submit({ assign_to: assignTo, current_user: window.user, department })
      }
    },
    { immediate: true },
  )

  const isSuperior = computed(() => Boolean(check.resource.data?.is_superior))
  return { isSuperior, loading: computed(() => check.isLoading) }
}

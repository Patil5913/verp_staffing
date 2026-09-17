import { reactive } from 'vue'
import { createResource } from 'frappe-ui'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'
import { useApiState } from './useApiState'

// Thin wrapper around frappe-ui's createResource: every resource in the app
// gets the same "toast on error unless the caller opts out" behavior, plus
// the loading/error/permission/empty flags from useApiState, instead of
// each call site re-deriving them from `resource.loading`/`resource.error`.
//
// Pass `notifyOnError: false` when the caller renders its own error state
// (e.g. inline form validation) instead of a toast.
export function useResource(options, vm) {
  const { notifyOnError = true, onError, ...rest } = options

  const resource = createResource(
    {
      ...rest,
      onError(error) {
        if (notifyOnError) {
          notify.error(normalizeError(error).message)
        }
        onError?.call(this, error)
      },
    },
    vm,
  )

  const state = useApiState({
    loading: () => resource.loading,
    error: () => resource.error,
    data: () => resource.data,
  })

  // `state`'s properties are computed refs (e.g. isPermissionError). Spread
  // into a *plain* object here, they'd stay unwrapped refs — always truthy
  // in a template `v-if`, regardless of their real value. reactive() makes
  // property access on this returned object unwrap them correctly, in both
  // templates and plain JS.
  return reactive({ resource, ...state })
}

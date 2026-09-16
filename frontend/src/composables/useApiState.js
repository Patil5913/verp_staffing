import { computed } from 'vue'
import { normalizeError } from '@/utils/errors'

function isEmptyValue(value) {
  if (value == null) return true
  if (Array.isArray(value)) return value.length === 0
  if (typeof value === 'object') return Object.keys(value).length === 0
  return false
}

// Shared permission/error/empty state for anything shaped like a frappe-ui
// resource (loading + error + data). Takes getters (not the values
// themselves) so the computeds keep tracking the underlying reactive
// resource, whichever of useResource/useList/useDocument built it.
export function useApiState({ loading, error, data, hasData }) {
  const normalized = computed(() => {
    const err = error()
    return err ? normalizeError(err) : null
  })

  return {
    isLoading: computed(() => !!loading()),
    hasError: computed(() => !!normalized.value),
    error: normalized,
    errorMessage: computed(() => normalized.value?.message || ''),
    isPermissionError: computed(() => normalized.value?.type === 'permission'),
    isNotFoundError: computed(() => normalized.value?.type === 'not_found'),
    isAuthError: computed(() => normalized.value?.type === 'unauthenticated'),
    isEmpty: computed(() => {
      if (loading() || normalized.value) return false
      return hasData ? !hasData() : isEmptyValue(data?.())
    }),
  }
}

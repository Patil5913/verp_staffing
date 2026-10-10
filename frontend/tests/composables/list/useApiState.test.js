import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { useApiState } from '@/composables/list/useApiState'

const make = (o = {}) => {
  const loading = ref(false), error = ref(null), data = ref(null)
  const s = useApiState({ loading: () => loading.value, error: () => error.value, data: () => data.value, ...o })
  return { s, loading, error, data }
}

describe('useApiState', () => {
  it('reactive loading', () => {
    const { s, loading } = make()
    expect(s.isLoading.value).toBe(false)
    loading.value = true
    expect(s.isLoading.value).toBe(true)
  })
  it('classifies errors', () => {
    const { s, error } = make()
    expect(s.hasError.value).toBe(false)
    error.value = { status: 403, message: 'no' }
    expect(s.hasError.value).toBe(true)
    expect(s.isPermissionError.value).toBe(true)
    expect(s.errorMessage.value).toBe('no')
    error.value = { status: 404 }
    expect(s.isNotFoundError.value).toBe(true)
    error.value = { status: 401 }
    expect(s.isAuthError.value).toBe(true)
  })
  it('isEmpty for null, [], {} but not while loading or erroring', () => {
    const { s, data, loading, error } = make()
    expect(s.isEmpty.value).toBe(true)
    data.value = []
    expect(s.isEmpty.value).toBe(true)
    data.value = {}
    expect(s.isEmpty.value).toBe(true)
    data.value = [1]
    expect(s.isEmpty.value).toBe(false)
    data.value = null
    loading.value = true
    expect(s.isEmpty.value).toBe(false)
    loading.value = false
    error.value = { status: 500 }
    expect(s.isEmpty.value).toBe(false)
  })
  it('hasData overrides data', () => {
    const has = ref(true)
    const { s } = make({ hasData: () => has.value })
    expect(s.isEmpty.value).toBe(false)
    has.value = false
    expect(s.isEmpty.value).toBe(true)
  })
})

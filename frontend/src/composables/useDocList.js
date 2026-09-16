import { computed, ref, watch } from 'vue'
import { debounce } from 'frappe-ui'
import { useResource } from './useResource'

const PAGE_LENGTH = 10

// Orchestrates a generic doctype list view on top of useResource: field/
// filter metadata (backed by verp_staffing.utils.list_view), the filter
// panel's standard filters, a free-text search box resolved to a
// ["name", "in", [...]] filter server-side (see resolve_search_filter for
// the AND/OR semantics), sorting, and fixed-page-size (10) pagination.
//
// Deliberately built on useResource (frappe.client.get_list) rather than
// useList (createListResource) — createListResource's reload()/next()
// always *concatenate* once `start > 0` (it's built for infinite-scroll
// "load more" lists, see listResource.js's `out.originalData.concat(data)`),
// which would silently merge page 2's rows onto page 1's instead of
// replacing them. A plain createResource fetch always replaces `.data`, so
// each page fetched here fully replaces the previous one, as numbered
// pagination needs.
export function useDocList(doctype) {
  const meta = useResource({
    url: 'verp_staffing.utils.list_view.get_list_view_meta',
    params: { doctype },
    cache: ['doctype-list-meta', doctype],
    auto: true,
  })

  const page = ref(1)
  const filters = ref({}) // filter panel's own shape: { fieldname: [operator, value] }
  const searchText = ref('')
  const sortField = ref('modified')
  const sortOrder = ref('desc') // 'asc' | 'desc'

  const search = useResource({
    url: 'verp_staffing.utils.list_view.resolve_search_filter',
    makeParams: () => ({ doctype, txt: searchText.value }),
    notifyOnError: false,
  })

  const standardFilters = computed(() =>
    Object.entries(filters.value).map(([fieldname, [operator, value]]) => [
      fieldname,
      operator,
      value,
    ]),
  )

  const combinedFilters = computed(() => {
    const list = [...standardFilters.value]
    const searchFilter = search.resource.data?.filter
    if (searchFilter) list.push(searchFilter)
    return list
  })

  const orderBy = computed(() => `${sortField.value} ${sortOrder.value}`)

  const fieldsToFetch = computed(() => {
    const listFields = (meta.resource.data?.list_fields || []).map((f) => f.fieldname)
    return [...new Set([...listFields, 'name', 'modified', 'creation'])]
  })

  const docs = useResource({
    url: 'frappe.client.get_list',
    makeParams: () => ({
      doctype,
      fields: fieldsToFetch.value,
      filters: combinedFilters.value,
      order_by: orderBy.value,
      limit_start: (page.value - 1) * PAGE_LENGTH,
      limit_page_length: PAGE_LENGTH,
    }),
  })

  const count = useResource({
    url: 'frappe.client.get_count',
    makeParams: () => ({ doctype, filters: combinedFilters.value }),
    notifyOnError: false,
  })

  const totalCount = computed(() => count.resource.data || 0)
  const pageCount = computed(() => Math.max(1, Math.ceil(totalCount.value / PAGE_LENGTH)))

  // Guards against the setup-time watchers below firing before the
  // doctype's meta (and therefore fieldsToFetch) has loaded once.
  let ready = false

  function refetchAll() {
    page.value = 1
    docs.resource.submit()
    count.resource.submit()
  }

  watch(
    () => meta.resource.data,
    (value) => {
      if (!value || ready) return
      sortField.value = value.sort_field || 'modified'
      sortOrder.value = value.sort_order || 'desc'
      ready = true
      refetchAll()
    },
  )

  // combinedFilters already reacts to both the standard filter panel and
  // the resolved search filter, so this one watcher covers both.
  watch(combinedFilters, () => {
    if (ready) refetchAll()
  })

  watch(orderBy, () => {
    if (ready) refetchAll()
  })

  watch(page, () => {
    if (ready) docs.resource.submit()
  })

  const debouncedSearch = debounce(() => {
    if (searchText.value.trim()) {
      search.resource.submit()
    } else {
      search.resource.reset()
    }
  }, 300)

  watch(searchText, debouncedSearch)

  function setPage(value) {
    page.value = value
  }

  function toggleSortOrder() {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  }

  function clearFilters() {
    filters.value = {}
  }

  function refresh() {
    meta.resource.reload()
    docs.resource.reload()
    count.resource.reload()
  }

  return {
    meta,
    docs,
    page,
    pageCount,
    totalCount,
    pageLength: PAGE_LENGTH,
    filters,
    searchText,
    // `search` is a reactive() object (see useResource.js), so `search.isLoading`
    // unwraps to a plain boolean *at this access* — re-wrapping in computed()
    // here keeps it live instead of freezing it at whatever it was when
    // useDocList() ran.
    searchLoading: computed(() => search.isLoading),
    sortField,
    sortOrder,
    setPage,
    toggleSortOrder,
    clearFilters,
    refresh,
  }
}

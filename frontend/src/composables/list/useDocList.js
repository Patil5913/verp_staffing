import { computed, ref, watch } from 'vue'
import { debounce } from 'frappe-ui'
import { useResource } from './useResource'
import { ROW_ACTIONS } from '@/configs/detail/listOptions'

const DEFAULT_PAGE_LENGTH = 15

// Orchestrates a generic doctype list view on top of useResource: field
// metadata (backed by verp_staffing.utils.list_view), a search box resolved
// server-side into a list of get_list filters - field-scoped ("status=open")
// and/or free-text terms, AND'd or OR'd together (see resolve_search_filter
// for the full syntax) - sorting, and fixed-page-size (10) pagination.
//
// Deliberately built on useResource (frappe.client.get_list) rather than
// useList (createListResource) - createListResource's reload()/next()
// always *concatenate* once `start > 0` (it's built for infinite-scroll
// "load more" lists, see listResource.js's `out.originalData.concat(data)`),
// which would silently merge page 2's rows onto page 1's instead of
// replacing them. A plain createResource fetch always replaces `.data`, so
// each page fetched here fully replaces the previous one, as numbered
// pagination needs.
export function useDocList(doctype, options = {}) {
  // Optional extra get_list-style filter tuples merged on top of the
  // search-resolved ones - e.g. Interview's "Select Customer" scoping
  // (marketing_link in [...]), which isn't something the search box's own
  // syntax can express and shouldn't have to be.
  const extraFilters = options.extraFilters ?? computed(() => [])
  const meta = useResource({
    url: 'verp_staffing.utils.list_view.get_list_view_meta',
    params: { doctype },
    cache: ['doctype-list-meta', doctype],
    auto: true,
  })

  const page = ref(1)
  const pageLength = ref(DEFAULT_PAGE_LENGTH)
  const searchText = ref('')
  const sortField = ref('modified')
  const sortOrder = ref('desc') // 'asc' | 'desc'

  const search = useResource({
    url: 'verp_staffing.utils.list_view.resolve_search_filter',
    makeParams: () => ({ doctype, txt: searchText.value }),
    notifyOnError: false,
  })

  const combinedFilters = computed(() => [...(search.resource.data?.filters || []), ...extraFilters.value])

  const orderBy = computed(() => `${sortField.value} ${sortOrder.value}`)

  const fieldsToFetch = computed(() => {
    const listFields = (meta.resource.data?.list_fields || []).map((f) => f.fieldname)
    // plus whatever a doctype's row buttons decide on (Email Queue: status)
    const needed = (ROW_ACTIONS[doctype] || []).flatMap((action) => action.needs || [])
    // docstatus is cheap to fetch even for non-submittable doctypes (always
    // 0) and DocListView needs it to render the Draft/Submitted/Cancelled
    // badge for submittable ones. Payment Entry / Sales Invoice additionally
    // need these for their own list-status overrides (see statusTheme.js's
    // listStatusColumn).
    const STATUS_OVERRIDE_FIELDS = {
      'Payment Entry': ['payment_term_row', 'verification_status'],
      'Sales Invoice': ['outstanding_amount', 'rounded_total', 'grand_total', 'disable_rounded_total'],
    }
    const statusOverrideFields = STATUS_OVERRIDE_FIELDS[doctype] || []
    return [...new Set([...listFields, 'name', 'modified', 'creation', 'docstatus', ...statusOverrideFields, ...needed])]
  })

  const docs = useResource({
    // Interview's "Today" status is derived (not stored), so its list/count come
    // from its own API - same arguments as get_list.
    url: doctype === 'Interview' ? 'verp_staffing.marketing.doctype.interview.interview.get_interview_list' : 'frappe.client.get_list',
    makeParams: () => ({
      ...(doctype === 'Interview' ? {} : { doctype }),
      fields: fieldsToFetch.value,
      filters: combinedFilters.value,
      order_by: orderBy.value,
      limit_start: (page.value - 1) * pageLength.value,
      limit_page_length: pageLength.value,
    }),
  })

  const count = useResource({
    url: doctype === 'Interview' ? 'verp_staffing.marketing.doctype.interview.interview.get_interview_count' : 'frappe.client.get_count',
    makeParams: () => (doctype === 'Interview' ? { filters: combinedFilters.value } : { doctype, filters: combinedFilters.value }),
    notifyOnError: false,
  })

  const totalCount = computed(() => count.resource.data || 0)
  const pageCount = computed(() => Math.max(1, Math.ceil(totalCount.value / pageLength.value)))

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

  watch(combinedFilters, () => {
    if (ready) refetchAll()
  })

  watch(orderBy, () => {
    if (ready) refetchAll()
  })

  watch(page, () => {
    if (ready) docs.resource.submit()
  })

  watch(pageLength, () => {
    if (ready) refetchAll()
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

  function setPageLength(value) {
    pageLength.value = value
    page.value = 1
  }

  function toggleSortOrder() {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  }

  function clearFilters() {
    searchText.value = ''
    search.resource.reset()
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
    pageLength,
    searchText,
    // `search` is a reactive() object (see useResource.js), so `search.isLoading`
    // unwraps to a plain boolean *at this access* - re-wrapping in computed()
    // here keeps it live instead of freezing it at whatever it was when
    // useDocList() ran.
    searchLoading: computed(() => search.isLoading),
    sortField,
    sortOrder,
    setPage,
    setPageLength,
    toggleSortOrder,
    clearFilters,
    refresh,
  }
}

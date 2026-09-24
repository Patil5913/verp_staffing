<template>
  <div class="mx-auto flex max-w-4xl flex-col gap-5 px-3 py-6 md:px-6">
    <div>
      <h1 class="text-xl font-semibold text-app-text">Candidate Details</h1>
      <p class="text-p-sm text-app-text-muted">
        {{ readOnly ? 'Your submitted details. Contact us if something needs to change.' : 'Fill in the details below for the services you signed up for.' }}
      </p>
    </div>

    <div v-if="loading" class="flex justify-center py-16"><LoadingIndicator class="h-6 w-6 text-app-text-muted" /></div>
    <p v-else-if="!layout.length" class="rounded-xl border border-dashed border-app-border py-12 text-center text-p-sm text-app-text-muted">
      Nothing to fill in right now.
    </p>

    <template v-else>
      <div v-if="errorList.length" class="rounded-xl border border-red-500/40 bg-red-500/10 p-4">
        <p class="mb-1 text-p-sm font-semibold text-red-700 dark:text-red-300">Please fix the following</p>
        <ul class="list-disc pl-5 text-p-sm text-red-700 dark:text-red-300">
          <li v-for="e in errorList" :key="e.key">{{ e.message }}</li>
        </ul>
      </div>

      <section v-for="(section, si) in layout" :key="si" class="rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
        <h2 v-if="section.label" class="mb-4 text-base font-semibold text-app-text">{{ section.label }}</h2>
        <div class="grid grid-cols-1 gap-x-6 gap-y-5" :class="colClass(section.columns.length)">
          <div v-for="(col, ci) in section.columns" :key="ci" class="flex min-w-0 flex-col gap-5">
            <template v-for="name in col" :key="name">
              <div v-if="tableOf(name)" :data-field="name">
                <ChildTableField :table="tableOf(name)" :rows="values[name] || []" :disabled="readOnly" @update:rows="(rows) => (values[name] = rows)" />
                <p v-if="errors[name]" class="mt-1 text-p-xs text-red-600">{{ errors[name] }}</p>
                <ul v-if="rowErrors(name).length" class="mt-1 list-disc pl-5 text-p-xs text-red-600">
                  <li v-for="e in rowErrors(name)" :key="e.key">{{ e.message }}</li>
                </ul>
              </div>
              <div v-else :data-field="name" @focusout="checkField(fieldOf(name))">
                <FieldControl :field="fieldOf(name)" v-model="values[name]" :disabled="readOnly || fieldOf(name).read_only" />
                <p v-if="errors[name]" class="mt-1 text-p-xs text-red-600">{{ errors[name] }}</p>
              </div>
            </template>
          </div>
        </div>
      </section>

      <div v-if="!readOnly" class="flex justify-end">
        <AppButton icon="check" :loading="saving" @click="save">Submit details</AppButton>
      </div>
    </template>
  </div>
</template>

<script setup>
// The customer's own Candidate Details form (replaces the emailed-token
// webform for portal users). Which fields show, and which are required, come
// from the server (ERP Configuration for the services on their open Sales
// Orders); saving returns per-field errors shown inline, and locks the form
// (Customer.lock_form = 1) on success.
import { computed, reactive, ref } from 'vue'
import { call, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import FieldControl from '@/components/detail/FieldControl.vue'
import ChildTableField from '@/components/detail/ChildTableField.vue'
import { notify } from '@/utils/common/notify'
import { fieldProblem } from '@/utils/detail/fieldProblems'
import { normalizeError } from '@/utils/common/errors'

const loading = ref(true)
const saving = ref(false)
const readOnly = ref(true)
const fields = ref([])
const tables = ref([])
const values = reactive({})
const errors = ref({})

const layout = ref([])
const fieldOf = (name) => fields.value.find((f) => f.fieldname === name)
const tableOf = (name) => tables.value.find((t) => t.fieldname === name)
const colClass = (n) => (n >= 3 ? 'sm:grid-cols-2 lg:grid-cols-3' : n === 2 ? 'sm:grid-cols-2' : '')
const labelOf = (name) => [...fields.value, ...tables.value].find((f) => f.fieldname === name)?.label || name
const errorList = computed(() =>
  Object.entries(errors.value).map(([key, message]) => ({
    key,
    message: key.includes('.') ? `${labelOf(key.split('.')[0])}, row ${key.split('.')[1]}: ${message}` : message,
  })),
)
const rowErrors = (table) =>
  Object.entries(errors.value)
    .filter(([k]) => k.startsWith(`${table}.`))
    .map(([key, message]) => ({ key, message: `Row ${key.split('.')[1]}: ${message}` }))

// Say what's wrong as soon as the user leaves an email/LinkedIn/phone input.
function checkField(field) {
  const problem = fieldProblem(field, values[field.fieldname])
  const next = { ...errors.value }
  if (problem) next[field.fieldname] = problem
  else delete next[field.fieldname]
  errors.value = next
}

async function load() {
  try {
    const res = await call('verp_staffing.www.candidate_details.get_candidate_form')
    fields.value = res.fields
    tables.value = res.tables
    layout.value = res.layout || []
    Object.assign(values, res.values || {})
    readOnly.value = !!res.lock_form
  } catch (e) {
    notify.error(normalizeError(e).message)
  } finally {
    loading.value = false
  }
}
load()

async function save() {
  saving.value = true
  errors.value = {}
  try {
    const res = await call('verp_staffing.www.candidate_details.save_candidate_form', { data: JSON.stringify(values) })
    if (!res.ok) {
      errors.value = res.errors
      notify.error('Please fix the highlighted fields.')
      document.querySelector(`[data-field="${Object.keys(res.errors)[0]?.split('.')[0]}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }
    notify.success('Details submitted. Thank you!')
    readOnly.value = true
  } catch (e) {
    notify.error(normalizeError(e).message)
  } finally {
    saving.value = false
  }
}
</script>

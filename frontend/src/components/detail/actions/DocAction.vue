<template>
  <AppButton :variant="variant" :icon="icon" :loading="running" @click="onClick">{{ label }}</AppButton>

  <Dialog v-model="askOpen" :options="{ title: label, size: 'md' }">
    <template #body-content>
      <div class="flex flex-col gap-4">
        <p v-if="confirm" class="text-p-base text-app-text-muted">{{ confirm }}</p>
        <AppInput
          v-for="field in prompt"
          :key="field.fieldname"
          :type="field.type || 'text'"
          :label="field.label"
          v-model="answers[field.fieldname]"
          :required="field.required"
        />
      </div>
    </template>
    <template #actions>
      <AppButton :loading="running" :disabled="!answered" @click="run">{{ label }}</AppButton>
    </template>
  </Dialog>
</template>

<script setup>
import AppInput from '@/components/ui/AppInput.vue'
// One "server action" button for any record's action bar, configured from
// detailConfigs: click (optionally after a confirm / a small prompt), call a
// whitelisted method, then either refresh the record, open the doc the
// method returned, or jump to a route.
//
//   { label, icon?, variant?, method,
//     nestPrompt?: 'args',   // prompt answers go under this param
//     args?: { arg: '$name' | '$doctype' | '$values.<field>' | <literal> },
//     confirm?: 'text', prompt?: [{ fieldname, label, type?, required? }],
//     success?: 'toast text',
//     // the method returns an unsaved mapped doc (make_payment_entry, ...):
//     // insert it as a draft of `create` and open it
//     create?: 'Payment Entry',
//     // where to go after: a path template ('$name' / '$result' substituted)
//     then?: 'refresh' (default) | 'stay' | 'open-file' (the result's file_url) | '/some/$result' }
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { call, Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  doctype: { type: String, required: true },
  name: { type: String, required: true },
  label: { type: String, required: true },
  icon: { type: String, default: '' },
  variant: { type: String, default: 'outline' },
  method: { type: String, required: true },
  args: { type: Object, default: () => ({}) },
  confirm: { type: String, default: '' },
  prompt: { type: Array, default: () => [] },
  success: { type: String, default: '' },
  create: { type: String, default: '' },
  then: { type: String, default: 'refresh' },
  // Put the prompt answers under this param (run_doc_method's `args`)
  // instead of at the top level.
  nestPrompt: { type: String, default: '' },
})

const router = useRouter()
const running = ref(false)
const askOpen = ref(false)
const answers = reactive({})

const answered = computed(() => props.prompt.every((f) => !f.required || String(answers[f.fieldname] ?? '').trim()))

function resolveArg(value) {
  if (typeof value !== 'string' || !value.startsWith('$')) return value
  if (value === '$name') return props.name
  if (value === '$doctype') return props.doctype
  if (value.startsWith('$values.')) return props.detail.values[value.slice(8)]
  return value
}

function onClick() {
  if (props.confirm || props.prompt.length) {
    for (const f of props.prompt) answers[f.fieldname] = ''
    askOpen.value = true
  } else {
    run()
  }
}

// A mapped doc arrives as a client-side draft (temp names, __islocal, ...);
// strip that so the server treats it, and each child row, as plain new data.
const DROP = new Set(['name', 'owner', 'creation', 'modified', 'modified_by', 'idx', 'docstatus'])
function cleanDoc(value) {
  if (Array.isArray(value)) return value.map(cleanDoc)
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(
    Object.entries(value)
      .filter(([k]) => !k.startsWith('__') && !DROP.has(k))
      .map(([k, v]) => [k, cleanDoc(v)]),
  )
}

async function run() {
  running.value = true
  try {
    const params = Object.fromEntries(Object.entries(props.args).map(([k, v]) => [k, resolveArg(v)]))
    const answered = Object.fromEntries(props.prompt.map((f) => [f.fieldname, answers[f.fieldname]]))
    if (props.nestPrompt) params[props.nestPrompt] = answered
    else Object.assign(params, answered)
    let result = await call(props.method, params)
    askOpen.value = false

    if (props.create) {
      const doc = await call('frappe.client.insert', { doc: cleanDoc(result) })
      result = doc.name
      router.push(`/${encodeURIComponent(props.create)}/${encodeURIComponent(result)}`)
      notify.success(props.success || `${props.create} ${result} created.`)
      return
    }

    if (props.success) notify.success(props.success)
    if (props.then === 'refresh') props.detail.refresh()
    else if (props.then === 'stay') return
    else if (props.then === 'open-file') {
      // the method answered { file_url } — open the file in a new tab
      const url = result?.file_url
      if (url) window.open(url, '_blank', 'noopener')
      else notify.error('No file found.')
    }
    else router.push(props.then.replace('$name', encodeURIComponent(props.name)).replace('$result', encodeURIComponent(result ?? '')))
  } catch (error) {
    notify.error(normalizeError(error).message)
  } finally {
    running.value = false
  }
}
</script>

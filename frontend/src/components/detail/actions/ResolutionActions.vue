<template>
  <template v-if="visible">
    <AppButton v-for="opt in options" :key="opt.action" :variant="opt.variant || 'outline'" :icon="opt.icon" @click="start(opt)">
      {{ opt.label }}
    </AppButton>

    <Dialog v-model="open" :options="{ title: pending?.label || '', size: 'md' }">
      <template #body-content>
        <p v-if="!pending?.remarks" class="text-p-base text-app-text-muted">
          {{ pending?.confirm || `Mark this ${doctype} as ${pending?.action}? This cannot be undone.` }}
        </p>
        <AppInput v-else type="textarea" label="Reason" v-model="remarks" required />
      </template>
      <template #actions>
        <AppButton :loading="running" :disabled="pending?.remarks && !remarks.trim()" @click="run">
          {{ pending?.label }}
        </AppButton>
      </template>
    </Dialog>
  </template>
</template>

<script setup>
import AppInput from '@/components/ui/AppInput.vue'
// The Actions-menu buttons on CR ("Resolve"/"Refund" with a reason) and
// Onboardings ("Mark Completed"/"Mark Returned" with a confirm) - only
// offered while the latest history row is still in its open status, and each
// one calls the doctype's own whitelisted resolver, then reloads the record.
import { computed, ref } from 'vue'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  doctype: { type: String, required: true },
  name: { type: String, required: true },
  historyField: { type: String, required: true },
  // The status the case must be in for these buttons to show - or any of several.
  openStatus: { type: [String, Array], required: true },
  method: { type: String, required: true },
  nameArg: { type: String, required: true },
  // [{ label, action, remarks?: bool, variant?, icon?, confirm?, method?, nameArg? }] - method/nameArg override the
  // component's own for one button (e.g. a backout that has its own endpoint).
  options: { type: Array, required: true },
})

const rows = computed(() => props.detail.values[props.historyField] || [])
const visible = computed(
  () => !props.detail.isNew.value && rows.value.length && [].concat(props.openStatus).includes(rows.value[rows.value.length - 1].status),
)

const open = ref(false)
const pending = ref(null)
const remarks = ref('')

function start(opt) {
  pending.value = opt
  remarks.value = ''
  open.value = true
}

const resolver = useResource({ url: props.method })
const resolvers = {}
const resolverFor = (opt) => {
  if (!opt.method) return resolver
  return (resolvers[opt.method] ||= useResource({ url: opt.method }))
}
const running = computed(() => resolver.isLoading || Object.values(resolvers).some((r) => r.isLoading))

async function run() {
  const args = { [pending.value.nameArg || props.nameArg]: props.name, action: pending.value.action }
  if (pending.value.remarks) args.remarks = remarks.value.trim()
  const result = await resolverFor(pending.value).resource.submit(args)
  if (!result) return
  notify.success(`${props.doctype} marked ${pending.value.action}.`)
  open.value = false
  props.detail.refresh()
}
</script>

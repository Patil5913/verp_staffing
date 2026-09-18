<template>
  <AppButton :variant="variant" :icon="icon" @click="go">{{ label }}</AppButton>
</template>

<script setup>
// A navigation button for a record's action bar: "View Chart of Accounts",
// "View Ledger", ... `to` is a path where `$name` and `$values.<field>` are
// filled in from the record; `query` values likewise.
import { useRouter } from 'vue-router'
import AppButton from '@/components/common/AppButton.vue'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  name: { type: String, required: true },
  label: { type: String, required: true },
  to: { type: String, required: true },
  query: { type: Object, default: () => ({}) },
  icon: { type: String, default: '' },
  variant: { type: String, default: 'outline' },
})
const router = useRouter()

function fill(value) {
  if (typeof value !== 'string') return value
  if (value === '$name') return props.name
  if (value.startsWith('$values.')) return props.detail.values[value.slice(8)]
  return value.replace('$name', encodeURIComponent(props.name))
}

function go() {
  const query = Object.fromEntries(
    Object.entries(props.query)
      .map(([k, v]) => [k, fill(v)])
      .filter(([, v]) => v !== undefined && v !== null && v !== ''),
  )
  router.push({ path: fill(props.to), query })
}
</script>

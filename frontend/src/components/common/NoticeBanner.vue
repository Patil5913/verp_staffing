<template>
  <div class="flex items-start gap-3 rounded-xl border px-4 py-3 text-p-sm" :class="TONES[tone]">
    <span class="mt-0.5 size-4 shrink-0" :class="`lucide-${ICONS[tone]}`" />
    <p>{{ message }}</p>
  </div>
</template>

<script setup>
// An inline notice inside a record (a locked-record explanation, a warning
// before a permanent action) — the desk's frm.set_intro / dashboard comment.
defineOptions({ inheritAttrs: false })
defineProps({
  message: { type: String, required: true },
  tone: { type: String, default: 'warning' }, // info | warning | danger
})
const TONES = {
  info: 'border-sky-300 bg-sky-50 text-sky-800',
  warning: 'border-amber-300 bg-amber-50 text-amber-800',
  danger: 'border-red-300 bg-red-50 text-red-800',
}
const ICONS = { info: 'info', warning: 'alert-triangle', danger: 'octagon-alert' }
</script>

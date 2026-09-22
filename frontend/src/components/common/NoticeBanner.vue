<template>
  <div class="notice-banner flex items-start gap-3 rounded-xl border px-4 py-3 text-p-sm" :class="[TONES[tone], `notice-banner--${tone}`]">
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

<style scoped>
/* The TONES classes above are fixed light-mode Tailwind colors (this app's
   dark mode is an attribute toggle — [data-theme='dark'] — not Tailwind's
   own dark: variant, which isn't configured here), so in dark mode this
   banner kept its near-white light background with dark text instead of
   following the theme — most visibly the "This Lead is locked" notice. */
/* Literal hex, not theme('colors.*.950') — frappe-ui's preset ships its own
   amber/red scales without a 950 shade, unlike the families this app's own
   tailwind.config.js re-adds from the full palette (sky included, but kept
   consistent with the other two here rather than mixing sources). */
[data-theme='dark'] .notice-banner--info {
  border-color: #075985;
  background-color: #082f49;
  color: #bae6fd;
}
[data-theme='dark'] .notice-banner--warning {
  border-color: #92400e;
  background-color: #451a03;
  color: #fde68a;
}
[data-theme='dark'] .notice-banner--danger {
  border-color: #991b1b;
  background-color: #450a0a;
  color: #fecaca;
}
</style>

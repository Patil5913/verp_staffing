<template>
  <!-- Height-clamped mode: maxHeight set — used for a whole paragraph
       (Customer Details' long text fields), where a character count can't
       tell you how many lines it'll actually wrap to. -->
  <span v-if="maxHeight" class="inline-flex max-w-full flex-col gap-1">
    <p
      ref="contentEl"
      class="whitespace-pre-wrap break-words"
      :class="expanded ? '' : 'overflow-hidden'"
      :style="expanded ? '' : { maxHeight }"
    >
      {{ text }}
    </p>
    <button
      v-if="clamped"
      type="button"
      class="w-fit shrink-0 text-p-xs font-medium text-app-primary hover:underline"
      @click.stop="expanded = !expanded"
    >
      {{ expanded ? 'View less' : 'View more' }}
    </button>
  </span>

  <!-- Character-count mode: a single-line grid/card cell. -->
  <span v-else-if="!isLong" class="truncate">{{ text }}</span>
  <span v-else class="inline-flex max-w-full flex-col gap-0.5">
    <span :class="expanded ? '' : 'truncate'">{{ text }}</span>
    <button
      type="button"
      class="w-fit shrink-0 text-p-xs font-medium text-app-primary hover:underline"
      @click.stop="expanded = !expanded"
    >
      {{ expanded ? 'View less' : 'View more' }}
    </button>
  </span>
</template>

<script setup>
// A long field value rendered somewhere tight — a course description or
// interview feedback in a grid cell (character-count mode, the original use
// case here), or a whole paragraph field shown read-only (Customer Details'
// Candidate Profile long-text fields, where a fixed character count can't
// predict how many lines something wraps to — height-clamped mode instead).
// Either way: plain CSS truncation/clamping cuts content off with no way
// back to the full text, so both modes add the missing expand/collapse.
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  text: { type: String, default: '' },
  // Character-count mode (default) — ignored once maxHeight is set.
  limit: { type: Number, default: 120 },
  // Height-clamped mode — any CSS length ('4.5em', '96px', ...). Passed
  // through by the caller instead of hardcoded per field/usage, per-field
  // callers can size this however fits their layout.
  maxHeight: { type: String, default: '' },
})

const isLong = computed(() => props.text.length > props.limit)
const expanded = ref(false)

// Height mode: only a real overflow (content taller than the clamp) gets a
// View More button — a short field that already fits shouldn't show one.
const contentEl = ref(null)
const clamped = ref(false)
// Only measured while still clamped — once expanded, maxHeight is removed
// and the element naturally grows to fit, which would otherwise read as
// "no overflow" and make the View Less button vanish right after showing it.
async function measure() {
  if (!props.maxHeight || expanded.value) return
  await nextTick()
  const el = contentEl.value
  clamped.value = !!el && el.scrollHeight > el.clientHeight + 1
}
watch(() => [props.text, props.maxHeight], () => {
  expanded.value = false
  measure()
}, { immediate: true })
</script>

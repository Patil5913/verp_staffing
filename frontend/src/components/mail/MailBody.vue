<template>
  <iframe
    ref="frame"
    class="block w-full border-0"
    :style="{ height: `${height}px` }"
    sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
    :srcdoc="doc"
    title="Message"
    @load="fit"
  />
</template>

<script setup>
// An email body, shown the safe way: sanitised, then rendered in a sandboxed
// frame (no scripts, links open in a new tab) so a message's own styles and
// markup can't touch the app. The frame grows to fit its content.
import { computed, onBeforeUnmount, ref } from 'vue'
import DOMPurify from 'dompurify'

const props = defineProps({ html: { type: String, default: '' } })

const frame = ref(null)
const height = ref(80)
let observer

const css = () => {
  const style = getComputedStyle(document.documentElement)
  const text = style.getPropertyValue('--app-text').trim() || '#1f2937'
  const muted = style.getPropertyValue('--app-text-muted').trim() || '#6b7280'
  const link = style.getPropertyValue('--app-primary').trim() || '#2563eb'
  return `<style>
    html,body{margin:0;padding:0;background:transparent}
    body{font:14px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;color:${text};word-break:break-word;overflow-wrap:anywhere}
    a{color:${link}} img{max-width:100%;height:auto} table{max-width:100%}
    blockquote{margin:.5em 0 .5em .25em;padding-left:.85em;border-left:3px solid ${muted}55;color:${muted}}
    pre{white-space:pre-wrap} p{margin:0 0 .75em}
  </style>`
}

// The frame's document is about:srcdoc, so a logo or footer image stored as a
// site-relative path ("/files/logo.png") has nothing to resolve against -
// <base href> points those at this site.
const origin = window.location.origin

const doc = computed(() => {
  const clean = DOMPurify.sanitize(props.html || '', { FORBID_TAGS: ['style', 'form', 'input', 'button', 'iframe', 'object', 'embed'], ADD_ATTR: ['target'] })
  return `<!doctype html><html><head><meta charset="utf-8"><base href="${origin}/" target="_blank">${css()}</head><body>${clean || '<p style="opacity:.6">(no content)</p>'}</body></html>`
})

// A logo/footer image that has no source or fails to load would show the
// browser's broken-image icon - take it out instead. The sandbox blocks the
// message's own scripts, so listen from out here.
function dropBrokenImages(body) {
  for (const img of body.querySelectorAll('img')) {
    const remove = () => img.remove()
    if (!img.getAttribute('src')?.trim()) remove()
    else if (img.complete && img.naturalWidth === 0) remove()
    else img.addEventListener('error', remove, { once: true })
  }
}

function fit() {
  const body = frame.value?.contentDocument?.body
  if (!body) return
  dropBrokenImages(body)
  const measure = () => (height.value = Math.max(60, body.scrollHeight + 4))
  measure()
  observer?.disconnect()
  if (typeof ResizeObserver !== 'undefined') {
    observer = new ResizeObserver(measure)
    observer.observe(body)
  }
}
onBeforeUnmount(() => observer?.disconnect())
</script>

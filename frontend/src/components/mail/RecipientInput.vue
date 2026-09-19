<template>
  <div
    class="flex min-h-9 flex-wrap items-center gap-1.5 rounded-lg border bg-app-panel px-2 py-1 transition-colors focus-within:border-app-primary focus-within:ring-2 focus-within:ring-app-primary/20"
    :class="invalidCount ? 'border-red-400' : 'border-app-border'"
    @click="input?.focus()"
  >
    <span
      v-for="(email, i) in model"
      :key="email + i"
      class="inline-flex max-w-full items-center gap-1 rounded-full py-0.5 pl-2.5 pr-1 text-p-sm"
      :class="EMAIL_RE.test(email) ? 'bg-app-primary-tint text-app-primary' : 'bg-red-500/10 text-red-700'"
      :title="EMAIL_RE.test(email) ? email : `${email} is not a valid email address`"
    >
      <span class="truncate">{{ email }}</span>
      <button type="button" class="flex size-4 items-center justify-center rounded-full hover:bg-black/10" :aria-label="`Remove ${email}`" @click.stop="remove(i)">
        <span class="lucide-x size-3" />
      </button>
    </span>
    <input
      ref="input"
      v-model="draft"
      type="text"
      :placeholder="model.length ? '' : placeholder"
      class="min-w-[8rem] flex-1 bg-transparent py-0.5 text-p-sm text-app-text placeholder:text-app-text-muted focus:outline-none"
      @keydown.enter.prevent="commit"
      @keydown.tab="commit"
      @keydown="onKey"
      @blur="commit"
      @paste="onPaste"
    />
  </div>
</template>

<script setup>
// A field of email "chips": type an address and press Enter, comma, space or
// Tab; paste a list; Backspace on an empty field removes the last one. Bad
// addresses stay visible in red so they can be fixed rather than vanishing.
import { computed, ref } from 'vue'
import { EMAIL_RE, parseAddresses } from '@/utils/mail/format'

const model = defineModel({ type: Array, default: () => [] })
defineProps({ placeholder: { type: String, default: '' } })

const input = ref(null)
const draft = ref('')
const invalidCount = computed(() => model.value.filter((e) => !EMAIL_RE.test(e)).length)

function add(text) {
  const emails = parseAddresses(text).map((a) => a.email)
  if (!emails.length) return
  model.value = [...new Set([...model.value, ...emails])]
}
function commit() {
  if (draft.value.trim()) add(draft.value)
  draft.value = ''
}
function remove(i) {
  model.value = model.value.filter((_, idx) => idx !== i)
}
function onKey(e) {
  if ((e.key === ',' || e.key === ';' || e.key === ' ') && draft.value.trim()) {
    e.preventDefault()
    commit()
  } else if (e.key === 'Backspace' && !draft.value && model.value.length) {
    remove(model.value.length - 1)
  }
}
function onPaste(e) {
  const text = e.clipboardData?.getData('text')
  if (text && /[,;\n]/.test(text)) {
    e.preventDefault()
    add(text)
  }
}
</script>

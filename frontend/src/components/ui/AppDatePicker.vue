<template>
  <div class="flex min-w-0 flex-col gap-1.5" :class="$attrs.class" :style="$attrs.style">
    <label v-if="label" class="text-p-sm font-medium text-app-text-muted">
      {{ label }}<span v-if="required" class="text-red-600"> *</span>
    </label>

    <Popover placement="bottom-start" class="w-full" @update:show="(v) => v && syncView()">
      <template #target="{ isOpen, togglePopover }">
        <button
          type="button"
          :disabled="disabled"
          class="group flex w-full min-w-0 items-center gap-2 rounded-lg border bg-app-panel text-left text-p-sm outline-none transition-colors disabled:cursor-not-allowed disabled:opacity-60"
          :class="[
            compact ? 'h-8 px-2' : 'h-9 px-3',
            error ? 'border-red-500' : isOpen ? 'border-app-primary ring-2 ring-app-primary/20' : 'border-app-border hover:border-app-primary/50',
          ]"
          @click="togglePopover()"
        >
          <span class="lucide-calendar size-4 shrink-0 text-app-text-muted group-hover:text-app-primary" />
          <span class="min-w-0 flex-1 truncate" :class="display ? 'text-app-text' : 'text-app-text-muted'">
            {{ display || placeholder }}
          </span>
          <span
            v-if="display && !required && !disabled"
            class="lucide-x size-3.5 shrink-0 text-app-text-muted hover:text-app-text"
            role="button"
            aria-label="Clear date"
            @click.stop="clear"
          />
        </button>
      </template>

      <template #body="{ close }">
        <div class="mt-1.5 w-[19rem] select-none rounded-2xl border border-app-border bg-app-panel p-3 shadow-2xl">
          <!-- Header: month/year switcher -->
          <div class="mb-2 flex items-center justify-between">
            <button type="button" class="nav-btn" aria-label="Previous" @click="step(-1)"><span class="lucide-chevron-left size-4" /></button>
            <button
              type="button"
              class="rounded-lg px-2.5 py-1 text-p-sm font-semibold text-app-text transition-colors hover:bg-app-panel-2"
              @click="view = view === 'days' ? 'months' : 'days'"
            >
              {{ view === 'days' ? `${MONTHS[cursor.month]} ${cursor.year}` : cursor.year }}
              <span class="lucide-chevron-down ml-0.5 inline-block size-3.5 align-[-2px] text-app-text-muted" />
            </button>
            <button type="button" class="nav-btn" aria-label="Next" @click="step(1)"><span class="lucide-chevron-right size-4" /></button>
          </div>

          <!-- Months -->
          <div v-if="view === 'months'" class="grid grid-cols-3 gap-1.5 py-1">
            <button
              v-for="(m, i) in MONTHS"
              :key="m"
              type="button"
              class="h-10 rounded-lg text-p-sm font-medium transition-colors"
              :class="i === cursor.month ? 'bg-app-primary text-white' : 'text-app-text hover:bg-app-panel-2'"
              @click="pickMonth(i)"
            >{{ m.slice(0, 3) }}</button>
          </div>

          <!-- Days -->
          <template v-else>
            <div class="grid grid-cols-7 pb-1">
              <span v-for="d in WEEKDAYS" :key="d" class="py-1 text-center text-p-xs font-medium text-app-text-muted">{{ d }}</span>
            </div>
            <div class="grid grid-cols-7 gap-y-0.5" @mouseleave="hover = ''">
              <button
                v-for="cell in cells"
                :key="cell.iso"
                type="button"
                class="relative h-9 text-p-sm transition-colors"
                :class="cellClasses(cell)"
                @mouseenter="hover = cell.iso"
                @click="pickDay(cell.iso, close)"
              >
                <span
                  class="mx-auto flex size-8 items-center justify-center rounded-full"
                  :class="dayClasses(cell)"
                >{{ cell.day }}</span>
              </button>
            </div>
          </template>

          <!-- Time (datetime mode) -->
          <div v-if="mode === 'datetime'" class="mt-2 flex items-center gap-2 border-t border-app-border pt-3">
            <span class="lucide-clock size-4 text-app-text-muted" />
            <input type="number" min="0" max="23" :value="pad(time.h)" class="time-input" aria-label="Hour" @input="setTime('h', $event.target.value)" />
            <span class="text-app-text-muted">:</span>
            <input type="number" min="0" max="59" :value="pad(time.m)" class="time-input" aria-label="Minute" @input="setTime('m', $event.target.value)" />
            <button type="button" class="ml-auto rounded-lg bg-app-primary px-3 py-1.5 text-p-xs font-medium text-white hover:bg-app-primary-hover" @click="close()">Done</button>
          </div>

          <!-- Footer -->
          <div v-else class="mt-2 flex items-center justify-between border-t border-app-border pt-2">
            <button type="button" class="foot-btn" @click="goToday(close)">{{ mode === 'range' ? 'This month' : 'Today' }}</button>
            <button v-if="!required" type="button" class="foot-btn" @click="clear(); close()">Clear</button>
          </div>
        </div>
      </template>
    </Popover>

    <p v-if="error" class="text-p-xs text-red-600">{{ error }}</p>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { Popover } from 'frappe-ui'

// The app's date control — a calendar popover instead of the browser's native
// picker. Values stay plain strings, so it drops in where <input type=date>
// was: 'YYYY-MM-DD' (date), 'YYYY-MM-DDTHH:mm' (datetime, same as
// datetime-local) and 'from,to' (range).
defineOptions({ inheritAttrs: false })
const props = defineProps({
  modelValue: { type: String, default: '' },
  mode: { type: String, default: 'date' }, // date | datetime | range
  label: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  error: { type: String, default: '' },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const WEEKDAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']

const pad = (n) => String(n).padStart(2, '0')
const toIso = (y, m, d) => `${y}-${pad(m + 1)}-${pad(d)}`
const todayIso = () => {
  const t = new Date()
  return toIso(t.getFullYear(), t.getMonth(), t.getDate())
}
const parts = (iso) => {
  const [y, m, d] = iso.split('-').map(Number)
  return { year: y, month: m - 1, day: d }
}
const fmt = (iso) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return ''
  const { year, month, day } = parts(iso)
  return `${day} ${MONTHS[month].slice(0, 3)} ${year}`
}

// --- value <-> parts -------------------------------------------------------
const range = computed(() => {
  if (props.mode !== 'range') return { from: '', to: '' }
  const [from = '', to = ''] = (props.modelValue || '').split(',')
  return { from, to }
})
const selectedDate = computed(() => (props.modelValue || '').slice(0, 10))
const time = reactive({ h: 9, m: 0 })
const readTime = () => {
  const t = (props.modelValue || '').slice(11, 16)
  if (/^\d{2}:\d{2}$/.test(t)) [time.h, time.m] = t.split(':').map(Number)
}

const display = computed(() => {
  if (!props.modelValue) return ''
  if (props.mode === 'range') {
    const { from, to } = range.value
    return from && to ? `${fmt(from)} – ${fmt(to)}` : ''
  }
  const d = fmt(selectedDate.value)
  return props.mode === 'datetime' && d ? `${d}, ${pad(time.h)}:${pad(time.m)}` : d
})

// --- calendar state --------------------------------------------------------
const cursor = reactive({ year: 0, month: 0 })
const view = ref('days')
const hover = ref('')
const pendingStart = ref('') // range: first click made, waiting for the second

function syncView() {
  readTime()
  const anchor = (props.mode === 'range' ? range.value.from : selectedDate.value) || todayIso()
  const { year, month } = parts(/^\d{4}-\d{2}-\d{2}$/.test(anchor) ? anchor : todayIso())
  cursor.year = year
  cursor.month = month
  view.value = 'days'
  pendingStart.value = ''
}
syncView()

const cells = computed(() => {
  const first = new Date(cursor.year, cursor.month, 1)
  const offset = (first.getDay() + 6) % 7 // Monday first
  const start = new Date(cursor.year, cursor.month, 1 - offset)
  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)
    return { iso: toIso(d.getFullYear(), d.getMonth(), d.getDate()), day: d.getDate(), outside: d.getMonth() !== cursor.month }
  })
})

function step(dir) {
  if (view.value === 'months') {
    cursor.year += dir
    return
  }
  const d = new Date(cursor.year, cursor.month + dir, 1)
  cursor.year = d.getFullYear()
  cursor.month = d.getMonth()
}
function pickMonth(i) {
  cursor.month = i
  view.value = 'days'
}

// --- selection -------------------------------------------------------------
const bounds = computed(() => {
  if (props.mode !== 'range') return { from: '', to: '' }
  if (pendingStart.value) {
    const other = hover.value || pendingStart.value
    return other < pendingStart.value ? { from: other, to: pendingStart.value } : { from: pendingStart.value, to: other }
  }
  return range.value
})
const isEdge = (iso) => iso === bounds.value.from || iso === bounds.value.to
const inRange = (iso) => bounds.value.from && bounds.value.to && iso > bounds.value.from && iso < bounds.value.to

function cellClasses(cell) {
  if (props.mode !== 'range') return ''
  const { from, to } = bounds.value
  if (!from || !to || from === to) return ''
  if (cell.iso === from) return 'rounded-l-full bg-app-primary-tint'
  if (cell.iso === to) return 'rounded-r-full bg-app-primary-tint'
  return inRange(cell.iso) ? 'bg-app-primary-tint' : ''
}
function dayClasses(cell) {
  const selected = props.mode === 'range' ? isEdge(cell.iso) : cell.iso === selectedDate.value
  if (selected) return 'bg-app-primary font-semibold text-white shadow-sm'
  if (cell.iso === todayIso()) return 'font-semibold text-app-primary ring-1 ring-inset ring-app-primary/50 hover:bg-app-panel-2'
  return [cell.outside ? 'text-app-text-muted/50' : 'text-app-text', 'hover:bg-app-panel-2']
}

function pickDay(iso, close) {
  if (props.mode === 'range') {
    if (!pendingStart.value) {
      pendingStart.value = iso
      return
    }
    const [from, to] = iso < pendingStart.value ? [iso, pendingStart.value] : [pendingStart.value, iso]
    pendingStart.value = ''
    emit('update:modelValue', `${from},${to}`)
    close()
    return
  }
  if (props.mode === 'datetime') {
    emit('update:modelValue', `${iso}T${pad(time.h)}:${pad(time.m)}`)
    return
  }
  emit('update:modelValue', iso)
  close()
}
function setTime(key, raw) {
  const max = key === 'h' ? 23 : 59
  time[key] = Math.min(max, Math.max(0, Number(raw) || 0))
  if (selectedDate.value) emit('update:modelValue', `${selectedDate.value}T${pad(time.h)}:${pad(time.m)}`)
}
function goToday(close) {
  const t = todayIso()
  if (props.mode === 'range') {
    const { year, month } = parts(t)
    emit('update:modelValue', `${toIso(year, month, 1)},${toIso(year, month, new Date(year, month + 1, 0).getDate())}`)
  } else {
    emit('update:modelValue', t)
  }
  close()
}
function clear() {
  pendingStart.value = ''
  emit('update:modelValue', '')
}
</script>

<style scoped>
.nav-btn {
  display: inline-flex;
  height: 2rem;
  width: 2rem;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem;
  color: var(--app-text-muted);
  transition: background-color 0.15s, color 0.15s;
}
.nav-btn:hover {
  background-color: var(--app-panel-2);
  color: var(--app-text);
}
.foot-btn {
  border-radius: 0.5rem;
  padding: 0.25rem 0.625rem;
  font-size: 12px;
  font-weight: 500;
  color: var(--app-primary);
}
.foot-btn:hover {
  background-color: var(--app-primary-tint);
}
.time-input {
  width: 3rem;
  height: 2rem;
  border-radius: 0.5rem;
  border: 1px solid var(--app-border);
  background: var(--app-panel);
  text-align: center;
  font-size: 13px;
  color: var(--app-text);
  outline: none;
}
.time-input:focus {
  border-color: var(--app-primary);
}
</style>

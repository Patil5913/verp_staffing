<template>
  <div class="sign-page">
    <AppSkeleton v-if="loading" variant="block" height="14rem" />
    <StateBanner v-else-if="error" icon="triangle-alert" title="This agreement isn't available" :description="error" />

    <template v-else-if="agreement">
      <div class="sign-title">
        <button type="button" class="back-link" @click="router.push('/portal/agreements')"><span class="lucide-arrow-left" /> All agreements</button>
        <h1>{{ agreement.title || agreement.name }}</h1>
      </div>

      <!-- already signed / just signed -->
      <div v-if="agreement.signed || (done && !showSuccess)" class="done-card">
        <svg class="success-checkmark" viewBox="0 0 52 52"><circle class="checkmark-circle" cx="26" cy="26" r="25" fill="none" /><path class="checkmark-check" fill="none" d="M14 27l8 8 16-17" /></svg>
        <p class="done-title">{{ done ? 'Your document has been signed' : 'You have already signed this agreement' }}</p>
        <div class="done-actions">
          <button type="button" class="btn-primary" @click="router.push('/portal/agreements')">Back to agreements</button>
          <a v-if="agreement.pdf" :href="agreement.pdf" target="_blank" rel="noopener" class="btn-ghost">Download signed copy</a>
        </div>
      </div>

      <template v-else>
        <!-- progress -->
        <div id="field-progress-bar">
          <span id="fp-left">{{ completed }} of {{ total }} fields completed</span>
          <span id="fp-right">{{ percent }}%</span>
          <div id="fp-track"><div id="fp-fill" :style="{ width: `${percent}%` }" /></div>
        </div>
        <div id="fp-next-hint">
          <span>{{ hint }}</span>
          <button v-if="nextField" type="button" class="hint-btn" @click="goNext">Go to field</button>
        </div>

        <!-- document -->
        <div ref="stage" class="pdf-stage">
          <div v-if="pdfLoading" class="doc-loading">Loading your document, please wait…</div>
          <StateBanner v-else-if="pdfError" icon="alert-triangle" title="Couldn't load the document" :description="pdfError" />
          <div v-for="page in pages" :key="page.number" class="pdf-page" :style="{ width: `${page.width * scale}px`, height: `${page.height * scale}px` }">
            <img :src="page.dataUrl" draggable="false" />
            <div class="overlay">
              <div
                v-for="f in fieldsOn(page.number)"
                :key="f.name"
                :ref="(el) => setEl(f.name, el)"
                class="field-box"
                :class="[stateOf(f), f.field_type === 'signature' ? 'is-signature' : f.field_type === 'checkbox' ? 'checkbox-field' : 'text-field']"
                :style="boxStyle(f)"
                @click="f.field_type === 'signature' && openPad(f)"
              >
                <span v-if="f.field_type !== 'checkbox'" class="field-label-tag">{{ f.field_label || f.field_type }}</span>
                <template v-if="f.field_type === 'signature'">
                  <img v-if="values[f.name]" :src="values[f.name]" class="signed-image" />
                  <span v-else class="sig-prompt" :style="{ fontSize: `${Math.max(10, 12 * Math.min(scale * 1.3, 1.1))}px` }">{{ f.field_label || 'Sign Here' }}</span>
                </template>
                <input v-else-if="f.field_type === 'checkbox'" v-model="values[f.name]" type="checkbox" />
                <textarea v-else-if="f.field_type === 'text'" v-model="values[f.name]" rows="1" :placeholder="f.field_label" :style="textStyle(f)" />
                <input v-else v-model="values[f.name]" :type="f.field_type === 'number' ? 'number' : 'date'" :placeholder="f.field_label" :style="textStyle(f)" />
              </div>
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- consent + submit bar (same as the emailed signing page) -->
    <div v-if="agreement && !agreement.signed && !done" id="fp-submit-wrap">
      <div class="submit-inner">
        <fieldset class="consent-card">
          <legend>Before you submit</legend>
          <label v-for="[key, label] in agreement.consents" :key="key" class="consent-row">
            <input v-model="concerns[key]" type="checkbox" />
            <span class="consent-tick" aria-hidden="true" />
            <span class="consent-text">{{ label }}</span>
          </label>
        </fieldset>
        <div class="submit-side">
          <button class="finish-btn" :disabled="!ready || saving" @click="submit">{{ saving ? 'Submitting…' : 'Submit Signed Document' }}</button>
          <p id="consent-hint" :class="{ ok: ready }">{{ ready ? 'All set - you can submit.' : !nextField ? 'Accept all three statements to submit.' : 'Complete all fields to submit.' }}</p>
        </div>
      </div>
    </div>

    <SignaturePadDialog v-model="padOpen" @save="onSignature" />

    <!-- success -->
    <Teleport to="body">
      <div v-if="showSuccess" class="success-overlay">
        <div class="success-card">
          <div class="success-icon-wrap">
            <svg class="success-checkmark" viewBox="0 0 52 52"><circle class="checkmark-circle" cx="26" cy="26" r="25" fill="none" /><path class="checkmark-check" fill="none" d="M14 27l8 8 16-17" /></svg>
          </div>
          <h2>Congratulations!</h2>
          <p>Your document has been signed and submitted securely. A signed copy and certificate will be available under Agreements.</p>
          <button type="button" class="btn-primary" @click="finishSuccess">Continue</button>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
// Sign an E Sign document inside the customer portal. The signed-in session is the authentication (no emailed link or
// one-time code); the fields to complete are drawn over the PDF at their exact positions and scale with the page, a
// progress bar and "Next field" guide the customer through, the three consent statements are required, and the server
// records the audit trail and issues the certificate.
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call } from 'frappe-ui'
import AppSkeleton from '@/components/ui/AppSkeleton.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import SignaturePadDialog from '@/components/portal/SignaturePadDialog.vue'
import { usePdfPages, PDF_PAGE_SCALE } from '@/composables/detail/usePdfPages'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

const API = 'verp_staffing.esign.portal.'
const route = useRoute()
const router = useRouter()

const agreement = ref(null)
const loading = ref(true)
const error = ref('')
const done = ref(false)
const showSuccess = ref(false)
const saving = ref(false)
const values = reactive({})
const methods = reactive({})
const concerns = reactive({})
const tried = ref(false)

const pdfUrl = computed(() => (agreement.value && !agreement.value.signed ? agreement.value.pdf : ''))
const { pages, loading: pdfLoading, error: pdfError } = usePdfPages(pdfUrl)

// Fit the pages to the screen: never wider than the container, and fields/fonts scale with it.
const stage = ref(null)
const stageWidth = ref(0)
let observer = null
onMounted(() => {
  observer = new ResizeObserver(([e]) => (stageWidth.value = e.contentRect.width))
})
watch(stage, (el, old) => {
  if (old) observer?.unobserve(old)
  if (el) observer?.observe(el)
})
onBeforeUnmount(() => observer?.disconnect())
const scale = computed(() => {
  const w = pages.value[0]?.width
  const avail = stageWidth.value - (stageWidth.value < 640 ? 16 : 32)
  return w && avail > 0 ? Math.min(1, avail / w) : 1
})

const fields = computed(() => agreement.value?.fields || [])
const fieldsOn = (n) => fields.value.filter((f) => Number(f.page_number) === n)
const boxStyle = (f) => ({ left: `${f.x_percent}%`, top: `${f.y_percent}%`, width: `${f.width_percent}%`, height: `${f.height_percent}%` })
const textStyle = (f) => ({
  // pt -> px at the render scale, so it reads the way it will be drawn on the PDF
  fontSize: `${(Number(f.font_size) || 12) * PDF_PAGE_SCALE * scale.value}px`,
  lineHeight: 1,
  fontFamily: 'Helvetica, Arial, sans-serif',
})

const isFilled = (f) => (f.field_type === 'checkbox' ? !!values[f.name] : !!String(values[f.name] ?? '').trim())
const completed = computed(() => fields.value.filter(isFilled).length)
const total = computed(() => fields.value.length)
const percent = computed(() => (total.value ? Math.round((completed.value / total.value) * 100) : 100))
const nextField = computed(() => fields.value.find((f) => !isFilled(f)) || null)
const allConsents = computed(() => (agreement.value?.consents || []).every(([key]) => concerns[key]))
const ready = computed(() => !nextField.value && allConsents.value)

// Same guided states as the emailed signing page: the next empty field is highlighted blue, finished ones green,
// and after a failed submit the missing ones red.
const stateOf = (f) => ({
  'fp-done-field': isFilled(f),
  'fp-active-field': !isFilled(f) && nextField.value?.name === f.name && !tried.value,
  error: !isFilled(f) && tried.value,
})
const hint = computed(() => {
  const f = nextField.value
  if (f) return `Next: ${f.field_label || f.field_type} (page ${f.page_number})`
  return allConsents.value ? 'All fields completed. Review your document and submit below.' : 'All fields completed. Accept the three statements below to submit.'
})

const els = {}
const setEl = (name, el) => el && (els[name] = el)
function goNext() {
  const f = nextField.value
  if (!f) return
  els[f.name]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  if (f.field_type === 'signature') setTimeout(() => openPad(f), 350)
  else els[f.name]?.querySelector('input,textarea')?.focus({ preventScroll: true })
}

onMounted(async () => {
  try {
    const a = await call(API + 'get_agreement', { esign: route.params.name })
    for (const [key] of a.consents) concerns[key] = false
    for (const f of a.fields) values[f.name] = f.field_type === 'checkbox' ? ['1', 'true', 'yes', 'checked', 'on'].includes(String(f.field_value || '').toLowerCase()) : f.field_value || ''
    agreement.value = a
    await nextTick()
  } catch (e) {
    error.value = normalizeError(e).message
  } finally {
    loading.value = false
  }
})

const padOpen = ref(false)
let padField = null
function openPad(f) {
  padField = f
  padOpen.value = true
}
function onSignature({ dataUrl, method }) {
  values[padField.name] = dataUrl
  methods[padField.name] = method
}

async function submit() {
  tried.value = true
  if (!ready.value) return notify.error(nextField.value ? `Please complete "${nextField.value.field_label || nextField.value.field_type}".` : 'Please accept all the confirmation statements.')
  const payload = {}
  for (const f of fields.value) {
    const v = values[f.name]
    payload[f.name] = f.field_type === 'checkbox' ? (v ? '1' : '0') : f.field_type === 'signature' ? v : String(v).trim()
  }
  saving.value = true
  try {
    await call(API + 'submit_agreement', {
      esign: route.params.name,
      fields: JSON.stringify(payload),
      concerns: JSON.stringify(Object.fromEntries(Object.entries(concerns).map(([k, v]) => [k, v ? 1 : 0]))),
      audit: JSON.stringify({ signature_methods: { ...methods } }),
    })
    done.value = true
    showSuccess.value = true
  } catch (e) {
    notify.error(normalizeError(e).message)
  } finally {
    saving.value = false
  }
}

function finishSuccess() {
  showSuccess.value = false
  router.push('/portal/agreements')
}
</script>

<style scoped>
.sign-page { max-width: 940px; margin: 0 auto; padding: 20px 12px 0; font-family: Inter, sans-serif; }
.sign-title { margin-bottom: 14px; }
.sign-title h1 { margin: 2px 0 0; font-size: 20px; font-weight: 600; color: var(--app-text); }
.back-link { display: inline-flex; align-items: center; gap: 4px; border: 0; background: none; padding: 0; font-size: 12px; color: var(--app-text-muted); cursor: pointer; }
.back-link:hover { color: var(--app-text); }

/* ── progress ── */
#field-progress-bar { margin: 0 auto 6px; padding: 14px 18px 10px; border: 1px solid var(--app-border); border-radius: 10px; position: sticky; top: 0; z-index: 30; background: var(--app-panel); color: var(--app-text); }
#fp-left { font-size: 13px; font-weight: 500; color: var(--app-text); margin-bottom: 8px; float: left; }
#fp-right { font-size: 13px; color: var(--app-text-muted); float: right; }
#fp-track { clear: both; width: 100%; height: 6px; background: var(--app-panel-2); border-radius: 999px; overflow: hidden; margin-top: 4px; }
#fp-fill { height: 100%; background: var(--app-primary); border-radius: 999px; transition: width 0.35s ease; }
#fp-next-hint { margin: 0 auto 16px; padding: 9px 14px; background: var(--app-panel-2); border: 1px solid var(--app-border); border-radius: 8px; font-size: 12px; color: var(--app-text-muted); position: sticky; top: 74px; z-index: 29; display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.hint-btn { border: 0; background: none; font-size: 12px; font-weight: 600; color: var(--app-primary); cursor: pointer; }

/* ── document ── */
.pdf-stage { background: var(--app-panel-2); border-radius: 12px; padding: 20px 8px; display: flex; flex-direction: column; align-items: center; gap: 24px; }
.pdf-page { position: relative; background: var(--app-panel); box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25); }
.pdf-page > img { display: block; width: 100%; height: 100%; user-select: none; }
.overlay { position: absolute; inset: 0; }
.doc-loading { display: flex; align-items: center; justify-content: center; gap: 10px; padding: 40px 16px; color: var(--app-text-muted); font-size: 15px; }
.doc-loading::before { content: ""; width: 18px; height: 18px; border: 2px solid var(--app-border); border-top-color: var(--app-primary); border-radius: 50%; animation: doc-spin 0.8s linear infinite; }
@keyframes doc-spin { to { transform: rotate(360deg); } }

.field-label-tag { position: absolute; top: -18px; left: 0; font-size: 10px; font-weight: 600; letter-spacing: 0.7px; text-transform: uppercase; color: var(--app-text-muted); white-space: nowrap; pointer-events: none; }
.field-box { position: absolute; z-index: 20; display: flex; align-items: center; justify-content: center; border-radius: 6px; transition: border-color 0.15s, background 0.15s, box-shadow 0.15s; }
.field-box.is-signature { border: 1.5px dashed var(--app-primary); background: var(--app-primary-tint); cursor: pointer; font-weight: 600; letter-spacing: 0.5px; color: var(--app-primary); }
.field-box.is-signature:hover { background: var(--app-primary-tint); border-color: var(--app-primary-hover); box-shadow: 0 0 0 3px var(--app-primary-tint); }
.sig-prompt { padding: 0 4px; text-align: center; }
.signed-image { width: 100%; height: 100%; object-fit: contain; pointer-events: none; }
.field-box.text-field { border: 1px solid var(--app-border); background: var(--app-panel); padding: 0; }
.field-box.text-field:focus-within { border-color: var(--app-primary); box-shadow: 0 0 0 3px var(--app-primary-tint); }
.field-box input[type='number'], .field-box input[type='date'] { width: 100%; height: 100%; border: none; outline: none; background: transparent; color: var(--app-text); padding: 0 8px; font-family: Inter, sans-serif; }
.field-box input[type='date']::-webkit-calendar-picker-indicator { filter: var(--app-date-icon-filter, none); }
.field-box textarea { display: block; width: 100%; height: 100%; border: none; outline: none; resize: none; overflow: hidden; background: transparent; color: var(--app-text); padding: 0; margin: 0; box-sizing: border-box; white-space: pre-wrap; overflow-wrap: anywhere; font-family: Helvetica, Arial, sans-serif; }
.field-box input::placeholder, .field-box textarea::placeholder { color: var(--app-text-muted); font-size: 12px; }
.field-box.checkbox-field { border: 1px solid var(--app-border); background: var(--app-panel); }
.field-box.checkbox-field:hover { border-color: var(--app-primary); background: var(--app-primary-tint); }
.field-box input[type='checkbox'] { width: 16px; height: 16px; accent-color: var(--app-primary); cursor: pointer; }
.field-box.error { border: 1.5px solid #ef4444 !important; background: rgba(239, 68, 68, 0.08) !important; box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15) !important; }
.field-box.fp-active-field { border-color: var(--app-primary) !important; box-shadow: 0 0 0 3px var(--app-primary-tint) !important; background: var(--app-primary-tint) !important; }
.field-box.fp-done-field { border-color: #16a34a !important; background: rgba(22, 163, 74, 0.08) !important; }
.field-box.is-signature.fp-done-field { border-style: solid !important; }

/* ── consent + submit bar ── */
/* Sticky inside the page (not fixed to the window), so it stays clear of the portal sidebar and header. */
#fp-submit-wrap { position: sticky; bottom: 0; z-index: 30; margin-top: 16px; border-radius: 12px 12px 0 0; padding: 14px 20px; background: var(--app-panel); border-top: 1px solid var(--app-border); box-shadow: 0 -6px 24px rgba(0, 0, 0, 0.2); color: var(--app-text); }
.submit-inner { max-width: 920px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; gap: 24px; }
.consent-card { flex: 1; min-width: 0; margin: 0; padding: 10px 14px 12px; border: 1px solid var(--app-border); border-radius: 10px; background: var(--app-panel-2); display: flex; flex-direction: column; gap: 8px; }
.consent-card legend { float: left; width: 100%; margin: 0 0 2px; padding: 0; font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--app-text-muted); }
.consent-row { display: flex; align-items: flex-start; gap: 10px; margin: 0; font-size: 13px; line-height: 1.4; color: var(--app-text); cursor: pointer; }
.consent-row input { position: absolute; opacity: 0; pointer-events: none; }
.consent-tick { flex: 0 0 auto; width: 18px; height: 18px; margin-top: 1px; border: 1.5px solid var(--app-text-muted); border-radius: 5px; background: var(--app-panel); display: inline-flex; align-items: center; justify-content: center; transition: background 0.15s, border-color 0.15s; }
.consent-tick::after { content: ''; width: 5px; height: 9px; margin-top: -2px; border: solid #fff; border-width: 0 2px 2px 0; transform: rotate(45deg) scale(0); transition: transform 0.12s ease; }
.consent-row:hover .consent-tick { border-color: var(--app-primary); }
.consent-row input:checked + .consent-tick { background: var(--app-primary); border-color: var(--app-primary); }
.consent-row input:checked + .consent-tick::after { transform: rotate(45deg) scale(1); }
.consent-row input:focus-visible + .consent-tick { outline: 2px solid var(--app-primary-tint); outline-offset: 2px; }
.submit-side { flex: 0 0 auto; display: flex; flex-direction: column; align-items: center; gap: 6px; }
.finish-btn { background: var(--app-primary); color: #fff; border: none; padding: 13px 40px; border-radius: 8px; font-size: 14px; font-weight: 600; letter-spacing: 0.3px; cursor: pointer; white-space: nowrap; transition: background 0.2s ease; }
.finish-btn:hover { background: var(--app-primary-hover); }
.finish-btn:disabled { background: var(--app-border); color: var(--app-text-muted); cursor: not-allowed; }
#consent-hint { margin: 0; font-size: 12px; color: var(--app-text-muted); }
#consent-hint.ok { color: #16a34a; }

/* ── done / success ── */
.done-card { display: flex; flex-direction: column; align-items: center; gap: 14px; padding: 40px 20px; background: var(--app-panel); border: 1px solid var(--app-border); border-radius: 16px; text-align: center; color: var(--app-text); }
.done-title { margin: 0; font-size: 18px; font-weight: 600; }
.done-actions { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; }
.btn-primary { background: var(--app-primary); color: #fff; border: none; padding: 11px 22px; border-radius: 10px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-primary:hover { background: var(--app-primary-hover); }
.btn-ghost { display: inline-flex; align-items: center; padding: 10px 20px; border: 1px solid var(--app-border); border-radius: 10px; font-size: 14px; font-weight: 600; color: var(--app-text); text-decoration: none; background: var(--app-panel); }
.btn-ghost:hover { background: var(--app-panel-2); }
.success-overlay { position: fixed; inset: 0; z-index: 1100; display: flex; align-items: center; justify-content: center; background: rgba(0, 0, 0, 0.6); padding: 12px; }
.success-card { background: var(--app-panel); border-radius: 20px; padding: 40px 32px 32px; max-width: 460px; width: 95%; text-align: center; box-shadow: 0 24px 60px rgba(0, 0, 0, 0.35); animation: pop 0.35s ease both; color: var(--app-text); }
.success-card h2 { margin: 0 0 8px; font-size: 22px; font-weight: 700; color: var(--app-text); }
.success-card p { margin: 0 0 22px; font-size: 14px; color: var(--app-text-muted); line-height: 1.5; }
.success-icon-wrap { display: flex; justify-content: center; margin-bottom: 18px; }
.success-checkmark { width: 64px; height: 64px; }
.checkmark-circle { stroke: #16a34a; stroke-width: 2; stroke-dasharray: 166; stroke-dashoffset: 166; animation: stroke-circle 0.5s ease forwards 0.1s; }
.checkmark-check { stroke: #16a34a; stroke-width: 3.5; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 48; stroke-dashoffset: 48; animation: stroke-check 0.35s ease forwards 0.5s; }
@keyframes stroke-circle { to { stroke-dashoffset: 0; } }
@keyframes stroke-check { to { stroke-dashoffset: 0; } }
@keyframes pop { from { opacity: 0; transform: scale(0.92) translateY(16px); } to { opacity: 1; transform: none; } }

@media (max-width: 640px) {
  #fp-submit-wrap { padding: 12px; border-radius: 0; }
  .submit-inner { flex-direction: column; align-items: stretch; gap: 10px; }
  .finish-btn { width: 100%; }
  #fp-next-hint { top: 78px; }
}
</style>

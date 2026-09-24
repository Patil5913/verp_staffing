<template>
  <div class="mx-auto flex min-h-screen max-w-4xl flex-col gap-5 px-3 py-6 md:px-6">
    <h1 class="text-xl font-semibold text-app-text">Sign Agreement</h1>

    <div v-if="loading" class="flex justify-center py-16"><LoadingIndicator class="h-6 w-6 text-app-text-muted" /></div>

    <div v-else-if="state === 'invalid'" class="rounded-xl border border-app-border bg-app-panel p-8 text-center text-p-sm text-app-text-muted">
      {{ invalidMessage }}
    </div>

    <div v-else-if="state === 'signed' || done" class="rounded-xl border border-green-500/40 bg-green-500/10 p-8 text-center">
      <p class="text-base font-semibold text-green-700 dark:text-green-300">
        {{ done ? 'Agreement signed. Thank you!' : 'This agreement has already been signed.' }}
      </p>
      <AppButton class="mt-4" icon="arrow-right" @click="router.push('/portal/dashboard')">Go to Portal</AppButton>
    </div>

    <div v-else-if="state === 'expired'" class="rounded-xl border border-red-500/40 bg-red-500/10 p-8 text-center">
      <p class="text-base font-semibold text-red-700 dark:text-red-300">This agreement link has expired</p>
      <p class="mt-1 text-p-sm text-app-text-muted">Request a fresh link and our team will send it to you shortly.</p>
      <AppButton class="mt-4" :loading="requesting" :disabled="requested" @click="requestLink">
        {{ requested ? 'Request sent' : 'Request new link' }}
      </AppButton>
    </div>

    <template v-else>
      <div class="flex flex-col gap-4">
        <img v-for="(src, i) in images" :key="i" :src="src" class="w-full rounded border border-app-border" />
      </div>

      <div class="flex flex-col gap-4 rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
        <h2 class="text-base font-semibold text-app-text">Signature</h2>
        <div class="flex gap-2">
          <AppButton v-for="m in ['Draw', 'Upload', 'Text']" :key="m" :variant="method === m ? 'solid' : 'outline'" :disabled="methodLocked" @click="pickMethod(m)">{{ m }}</AppButton>
        </div>

        <div v-if="method === 'Draw'">
          <canvas ref="pad" width="600" height="180" class="w-full max-w-xl touch-none rounded border border-app-border bg-white"
            @pointerdown="startDraw" @pointermove="moveDraw" @pointerup="endDraw" @pointerleave="endDraw" />
          <AppButton class="mt-2" variant="outline" size="sm" @click="clearPad">Clear</AppButton>
        </div>

        <div v-else>
          <div v-if="uploadedUrl"><img :src="uploadedUrl" class="max-w-[200px]" /><p class="text-p-xs text-app-text-muted">Signature locked.</p></div>
          <template v-else-if="method === 'Upload'">
            <input type="file" accept="image/*" @change="onFile" />
            <p class="mt-1 text-p-xs text-red-600">Max file size allowed: 1 MB. Image upload is compulsory. Once uploaded it cannot be changed.</p>
          </template>
          <template v-else>
            <AppButton @click="showText = true">Provide Text Signature</AppButton>
            <p class="mt-1 text-p-xs text-red-600">Text signature is compulsory.</p>
          </template>
        </div>
        <p v-if="errors.signature" class="text-p-xs text-red-600">{{ errors.signature }}</p>

        <div class="flex flex-col gap-2">
          <label v-for="c in CONCERNS" :key="c.fieldname" class="flex items-start gap-2 text-p-sm text-app-text">
            <input type="checkbox" class="mt-1" v-model="concerns[c.fieldname]" @change="onConcern(c, $event.target.checked)" />
            <span>{{ c.label }} <span class="text-red-600">*</span></span>
          </label>
          <p v-if="errors.concerns" class="text-p-xs text-red-600">{{ errors.concerns }}</p>
        </div>

        <div class="flex justify-end"><AppButton icon="check" :loading="saving" @click="submit">Sign agreement</AppButton></div>
      </div>
    </template>

    <Dialog v-model="showText" :options="{ title: 'Create Text Signature' }">
      <template #body-content>
        <div class="flex flex-col gap-3">
          <input v-model="textValue" placeholder="Your name" class="rounded border border-app-border bg-transparent px-3 py-2 text-p-sm" />
          <div class="border-b border-app-border p-3 text-4xl" :style="{ fontFamily: `'${font}'` }">{{ textValue }}</div>
          <div class="grid grid-cols-2 gap-2">
            <button v-for="f in FONTS" :key="f" type="button" class="rounded border px-2 py-2 text-p-sm"
              :class="f === font ? 'border-blue-600 bg-blue-500/10' : 'border-app-border'" :style="{ fontFamily: `'${f}'` }" @click="font = f">{{ f }}</button>
          </div>
          <p class="rounded bg-red-500/10 p-3 text-p-xs text-red-700 dark:text-red-300">
            <b>Important:</b> Once you click <b>Upload Signature</b>, this signature will be locked and cannot be changed.
          </p>
          <AppButton :loading="uploading" @click="uploadText">Upload Signature</AppButton>
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
// Portal version of the emailed signing webform (?ia=1). Same token, same
// consent checkboxes, Draw/Upload/Text signature options and audit trail; the
// backend authenticates via the portal session instead of an email OTP.
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call, Dialog, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

const API = 'verp_staffing.www.agreement_sign.'
const MAX_IMAGE = 1024 * 1024
const FONTS = ['Sacramento', 'Mr Dafoe', 'Yellowtail', 'Marck Script', 'Alex Brush']
const CONCERNS = [
  { fieldname: 'my_electronic_signature_has_same_effect_as_handwritten', label: 'My electronic signature has same effect as handwritten.' },
  { fieldname: 'i_consent_to_receive_sign_and_store_documents_electronically', label: 'I consent to receive, sign, and store documents electronically.' },
  { fieldname: 'i_confirm_my_identity_and_signing_this_document_intentionally', label: 'I confirm my identity and signing this document intentionally.' },
]

const route = useRoute()
const router = useRouter()
const token = route.query.t
const loading = ref(true)
const state = ref('ready')
const invalidMessage = ref('This agreement link is not valid.')
const images = ref([])
const done = ref(false)
const saving = ref(false)
const requesting = ref(false)
const requested = ref(false)
const method = ref('Draw')
const methodLocked = ref(false)
const uploadedUrl = ref('')
const concerns = reactive(Object.fromEntries(CONCERNS.map((c) => [c.fieldname, false])))
const errors = reactive({ signature: '', concerns: '' })
const showText = ref(false)
const textValue = ref('')
const font = ref(FONTS[0])
const uploading = ref(false)
const pad = ref(null)

// ---- audit trail (same shape/keys as the webform's localStorage trail) ----
const audit = { 'form visit logs': [], 'signature update logs': [], 'authentication logs': [], 'concern accepted': [] }
function stamp() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getUTCDate())}-${p(d.getUTCMonth() + 1)}-${d.getUTCFullYear()}, ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())} UTC`
}
async function log(key, data) {
  const fp = await call('verp_staffing.crm.doctype.lead_detail_form.lead_detail_form.get_ip_and_device').catch(() => ({}))
  audit[key].push({ event: data.event, timestamp: stamp(), ...data, ip: fp.ip, user_agent: fp.user_agent })
}
const onConcern = (c, checked) => {
  if (checked) log('concern accepted', { event: 'concern accepted', fieldname: c.fieldname, label: c.label, accepted: true })
}

onMounted(async () => {
  if (!token) {
    state.value = 'invalid'
    loading.value = false
    return
  }
  try {
    const res = await call(API + 'get_agreement', { token })
    state.value = res.state
    images.value = res.images || []
    if (res.state === 'ready') {
      log('form visit logs', { event: 'form_opened' })
      window.addEventListener('beforeunload', () => (audit['signature update logs'] = []))
    }
  } catch (e) {
    state.value = 'invalid'
    invalidMessage.value = normalizeError(e).message
  } finally {
    loading.value = false
  }
})

async function requestLink() {
  requesting.value = true
  try {
    await call(API + 'request_new_link', { token })
    requested.value = true
    notify.success('Your request has been sent. You will receive a new agreement link shortly.')
  } catch (e) {
    notify.error(normalizeError(e).message)
  } finally {
    requesting.value = false
  }
}

function pickMethod(m) {
  method.value = m
  errors.signature = ''
}

// ---- Draw ----
let drawing = false
let drawn = false
const ctx = () => pad.value.getContext('2d')
function pos(e) {
  const r = pad.value.getBoundingClientRect()
  return [((e.clientX - r.left) * pad.value.width) / r.width, ((e.clientY - r.top) * pad.value.height) / r.height]
}
function startDraw(e) {
  drawing = true
  const [x, y] = pos(e)
  const c = ctx()
  c.lineWidth = 2.5
  c.lineCap = 'round'
  c.strokeStyle = '#000'
  c.beginPath()
  c.moveTo(x, y)
}
function moveDraw(e) {
  if (!drawing) return
  const [x, y] = pos(e)
  ctx().lineTo(x, y)
  ctx().stroke()
  drawn = true
}
function endDraw() {
  if (drawing && drawn) log('signature update logs', { event: 'signature_updated', method: 'Draw' })
  drawing = false
}
function clearPad() {
  ctx().clearRect(0, 0, pad.value.width, pad.value.height)
  drawn = false
}

// ---- Upload / Text ----
async function storeSignature(dataUrl, filename, kind) {
  uploading.value = true
  try {
    const r = await call('verp_staffing.crm.api.upload.upload_file', { filename, filedata: dataUrl })
    if (!r?.success) throw new Error(r?.error || 'Upload failed')
    await call(API + 'set_signature', { token, file_name: r.file_name })
    log('signature update logs', { event: 'signature_added', method: kind })
    uploadedUrl.value = r.file_url
    methodLocked.value = true
    errors.signature = ''
    showText.value = false
    notify.success('Signature uploaded successfully.')
  } catch (e) {
    notify.error(normalizeError(e).message)
  } finally {
    uploading.value = false
  }
}
function onFile(e) {
  const file = e.target.files[0]
  if (!file) return
  if (file.size > MAX_IMAGE) {
    notify.error('Image size must not exceed 1 MB.')
    e.target.value = ''
    return
  }
  const reader = new FileReader()
  reader.onload = () => storeSignature(reader.result, file.name, 'Upload')
  reader.readAsDataURL(file)
}
async function uploadText() {
  if (!textValue.value.trim()) return notify.error('Please enter your name.')
  await document.fonts.load(`48px "${font.value}"`).catch(() => {})
  const canvas = document.createElement('canvas')
  canvas.width = 600
  canvas.height = 150
  const c = canvas.getContext('2d')
  c.fillStyle = '#000'
  c.font = `48px "${font.value}"`
  c.textBaseline = 'middle'
  c.fillText(textValue.value, 20, 75)
  storeSignature(canvas.toDataURL('image/png'), 'signature.png', 'Text')
}

// Signature web fonts (as the webform loads them).
if (!document.getElementById('signature-fonts')) {
  const link = document.createElement('link')
  link.id = 'signature-fonts'
  link.rel = 'stylesheet'
  link.href = 'https://fonts.googleapis.com/css2?family=Sacramento&family=Mr+Dafoe&family=Yellowtail&family=Marck+Script&family=Alex+Brush&display=swap'
  document.head.appendChild(link)
}

async function submit() {
  errors.signature = errors.concerns = ''
  let signature = null
  if (method.value === 'Draw') {
    if (!drawn) return (errors.signature = 'Please draw your signature.')
    signature = pad.value.toDataURL('image/png')
  } else if (!uploadedUrl.value) {
    return (errors.signature = 'Please upload or provide your signature.')
  }
  if (CONCERNS.some((c) => !concerns[c.fieldname])) return (errors.concerns = 'Please accept all the consent statements.')

  saving.value = true
  try {
    await log('form visit logs', { event: 'form_submit' })
    await call(API + 'submit_agreement', {
      token,
      signature_method: method.value,
      signature,
      concerns: JSON.stringify(Object.fromEntries(CONCERNS.map((c) => [c.fieldname, 1]))),
      audit: JSON.stringify(audit),
    })
    done.value = true
  } catch (e) {
    notify.error(normalizeError(e).message)
  } finally {
    saving.value = false
  }
}
</script>

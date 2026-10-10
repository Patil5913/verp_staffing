<template>
  <Teleport to="body">
    <div v-if="open" class="sg-overlay" @click.self="close">
      <div class="sg-modal" role="dialog" aria-modal="true" aria-labelledby="sg-title">
        <div class="sg-head">
          <h3 id="sg-title">Add your signature</h3>
          <button type="button" class="sg-x" aria-label="Close" @click="close">&times;</button>
        </div>

        <div class="sg-tabs" role="tablist">
          <button v-for="m in MODES" :key="m.key" type="button" role="tab" :class="{ active: mode === m.key }" @click="setMode(m.key)">{{ m.label }}</button>
        </div>

        <!-- DRAW -->
        <div v-show="mode === 'draw'">
          <div class="sg-pad" :class="{ 'has-ink': strokes.length }">
            <canvas
              ref="pad"
              @pointerdown="startStroke"
              @pointermove="moveStroke"
              @pointerup="endStroke"
              @pointercancel="endStroke"
              @pointerleave="endStroke"
            />
            <span class="sg-hint">Sign here with your mouse, finger or stylus</span>
            <span class="sg-baseline" />
          </div>
          <div class="sg-tools">
            <button type="button" class="sg-link" :disabled="!strokes.length" @click="undo">Undo</button>
            <button type="button" class="sg-link" :disabled="!strokes.length" @click="clearPad">Clear</button>
          </div>
        </div>

        <!-- TYPE -->
        <div v-if="mode === 'type'">
          <input v-model="typed" class="sg-input" type="text" placeholder="Type your full name" autocomplete="name" maxlength="60" />
          <div class="sg-pad sg-pad-type"><canvas ref="preview" width="1200" height="360" /><span class="sg-baseline" /></div>
          <div class="font-grid">
            <div v-for="f in FONTS" :key="f.css" class="font-box" :class="{ active: font === f.css }" @click="font = f.css">
              <span class="font-preview" :style="{ fontFamily: f.css }">{{ typed.trim() || 'John Smith' }}</span>
            </div>
          </div>
        </div>

        <!-- UPLOAD -->
        <div v-if="mode === 'upload'">
          <label class="sg-drop" for="portal-sig-upload">
            <span>Choose an image of your signature</span>
            <small>PNG or JPG, up to 1 MB</small>
          </label>
          <input id="portal-sig-upload" type="file" accept="image/*" hidden @change="onFile" />
          <div v-if="uploaded" class="sg-upload-preview"><img :src="uploaded" alt="Your signature" /></div>
        </div>

        <p v-if="error" class="sg-error">{{ error }}</p>
        <p class="sg-legal">By signing, you agree this is your legally binding electronic signature.</p>

        <div class="sg-actions">
          <button type="button" class="sg-cancel" @click="close">Cancel</button>
          <button type="button" class="sg-save" @click="save">Apply signature</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
// The same signature dialog as the emailed signing page: Draw (with undo / clear and a baseline), Type (eight
// script fonts) or Upload; hands back a cropped PNG data URL and the method used, for the audit trail.
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['save'])

const MODES = [
  { key: 'draw', label: 'Draw' },
  { key: 'type', label: 'Type' },
  { key: 'upload', label: 'Upload' },
]
const FONTS = [
  { css: "'Pacifico', cursive" },
  { css: "'Great Vibes', cursive" },
  { css: "'Dancing Script', cursive" },
  { css: "'Alex Brush', cursive" },
  { css: "'Satisfy', cursive" },
  { css: "'Playfair Display', serif" },
  { css: "'Libre Baskerville', serif" },
  { css: "'Roboto', sans-serif" },
]
const MAX_IMAGE = 1024 * 1024

const mode = ref('draw')
const error = ref('')
const pad = ref(null)
const preview = ref(null)
const typed = ref('')
const font = ref(FONTS[0].css)
const uploaded = ref('')
const strokes = ref([]) // [[ [x,y], ... ], ...] in canvas pixels
let current = null

if (!document.getElementById('portal-signature-fonts')) {
  const link = document.createElement('link')
  link.id = 'portal-signature-fonts'
  link.rel = 'stylesheet'
  link.href =
    'https://fonts.googleapis.com/css2?family=Pacifico&family=Great+Vibes&family=Dancing+Script&family=Alex+Brush&family=Playfair+Display&family=Roboto&family=Libre+Baskerville&family=Satisfy&display=swap'
  document.head.appendChild(link)
}

watch(open, async (v) => {
  document.body.style.overflow = v ? 'hidden' : ''
  if (!v) return
  error.value = ''
  strokes.value = []
  uploaded.value = ''
  setMode('draw')
})

// Leaving the page with the dialog still open must not leave the page unscrollable.
onBeforeUnmount(() => {
  if (open.value) document.body.style.overflow = ''
})

async function setMode(m) {
  mode.value = m
  error.value = ''
  await nextTick()
  if (m === 'draw') sizePad()
  if (m === 'type') renderTyped()
}

// ── draw ──
function sizePad() {
  const c = pad.value
  if (!c) return
  const r = c.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  c.width = Math.max(1, Math.round(r.width * dpr))
  c.height = Math.max(1, Math.round(r.height * dpr))
  redraw()
}
function redraw() {
  const c = pad.value
  if (!c) return
  const g = c.getContext('2d')
  g.clearRect(0, 0, c.width, c.height)
  g.lineWidth = 2.6 * (window.devicePixelRatio || 1)
  g.lineCap = g.lineJoin = 'round'
  g.strokeStyle = '#000'
  for (const s of strokes.value) {
    g.beginPath()
    s.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y)))
    if (s.length === 1) g.lineTo(s[0][0] + 0.1, s[0][1])
    g.stroke()
  }
}
function point(e) {
  const r = pad.value.getBoundingClientRect()
  return [((e.clientX - r.left) * pad.value.width) / r.width, ((e.clientY - r.top) * pad.value.height) / r.height]
}
function startStroke(e) {
  pad.value.setPointerCapture?.(e.pointerId)
  current = [point(e)]
  strokes.value = [...strokes.value, current]
  redraw()
}
function moveStroke(e) {
  if (!current) return
  current.push(point(e))
  redraw()
}
const endStroke = () => (current = null)
const undo = () => {
  strokes.value = strokes.value.slice(0, -1)
  redraw()
}
const clearPad = () => {
  strokes.value = []
  redraw()
}

// ── type ──
watch([typed, font], async () => {
  if (mode.value !== 'type') return
  await document.fonts.load(`64px ${font.value}`).catch(() => {})
  renderTyped()
})
function renderTyped() {
  const c = preview.value
  if (!c) return
  const g = c.getContext('2d')
  g.clearRect(0, 0, c.width, c.height)
  const text = typed.value.trim()
  if (!text) return
  let size = 150
  g.font = `${size}px ${font.value}`
  while (g.measureText(text).width > c.width - 60 && size > 30) {
    size -= 6
    g.font = `${size}px ${font.value}`
  }
  g.fillStyle = '#000'
  g.textBaseline = 'middle'
  g.textAlign = 'center'
  g.fillText(text, c.width / 2, c.height / 2)
}

// ── upload ──
function onFile(e) {
  const file = e.target.files[0]
  if (!file) return
  if (file.size > MAX_IMAGE) {
    error.value = 'Image size must not exceed 1 MB.'
    e.target.value = ''
    return
  }
  const reader = new FileReader()
  reader.onload = () => (uploaded.value = reader.result)
  reader.readAsDataURL(file)
}

// Crop transparent margins so the signature fills its box on the PDF.
function trim(canvas) {
  const g = canvas.getContext('2d')
  const { width, height } = canvas
  const data = g.getImageData(0, 0, width, height).data
  let minX = width, minY = height, maxX = 0, maxY = 0
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (data[(y * width + x) * 4 + 3] > 0) {
        minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y)
      }
    }
  }
  if (maxX <= minX) return canvas.toDataURL('image/png')
  const m = 8
  const out = document.createElement('canvas')
  out.width = maxX - minX + m * 2
  out.height = maxY - minY + m * 2
  out.getContext('2d').drawImage(canvas, minX - m, minY - m, out.width, out.height, 0, 0, out.width, out.height)
  return out.toDataURL('image/png')
}

function save() {
  error.value = ''
  let dataUrl = ''
  if (mode.value === 'draw') {
    if (!strokes.value.length) return (error.value = 'Please draw your signature first.')
    dataUrl = trim(pad.value)
  } else if (mode.value === 'type') {
    if (!typed.value.trim()) return (error.value = 'Please type your name.')
    dataUrl = trim(preview.value)
  } else {
    if (!uploaded.value) return (error.value = 'Please choose an image of your signature.')
    dataUrl = uploaded.value
  }
  emit('save', { dataUrl, method: mode.value })
  close()
}
function close() {
  open.value = false
}
</script>

<style scoped>
.sg-overlay { position: fixed; inset: 0; z-index: 1000; display: flex; align-items: center; justify-content: center; background: rgba(15, 23, 42, 0.5); padding: 12px; }
.sg-modal {
  width: 100%; max-width: 560px; max-height: calc(100dvh - 24px); overflow-y: auto; box-sizing: border-box; padding: 20px;
  background: #fff; color: #0f172a; border-radius: 16px; box-shadow: 0 24px 60px rgba(15, 23, 42, 0.28); overscroll-behavior: contain;
}
.sg-modal button { font-family: inherit; }
.sg-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.sg-head h3 { margin: 0; font-size: 18px; font-weight: 600; color: #0f172a; }
.sg-x { border: 0; background: none; font-size: 26px; line-height: 1; color: #64748b; cursor: pointer; padding: 0 4px; }
.sg-x:hover { color: #0f172a; }

.sg-tabs { display: flex; gap: 4px; padding: 4px; background: #f1f5f9; border-radius: 10px; margin-bottom: 14px; }
.sg-tabs button { flex: 1; border: 0; background: transparent; padding: 9px 0; border-radius: 7px; font-size: 14px; font-weight: 500; color: #475569; cursor: pointer; transition: background 0.15s, color 0.15s; }
.sg-tabs button.active { background: #fff; color: #1d4ed8; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.12); }

.sg-pad { position: relative; height: 200px; background: #fff; border: 1.5px dashed #cbd5e1; border-radius: 12px; overflow: hidden; }
.sg-pad:focus-within { border-color: #2563eb; }
.sg-pad-type { height: 130px; margin-bottom: 12px; }
.sg-pad canvas { width: 100%; height: 100%; display: block; touch-action: none; cursor: crosshair; user-select: none; }
.sg-pad-type canvas { cursor: default; }
.sg-baseline { position: absolute; left: 6%; right: 6%; bottom: 32%; border-bottom: 1px solid #e2e8f0; pointer-events: none; }
.sg-hint { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: #94a3b8; font-size: 14px; pointer-events: none; }
.sg-pad.has-ink .sg-hint { display: none; }

.sg-tools { display: flex; justify-content: flex-end; gap: 14px; margin-top: 8px; }
.sg-link { border: 0; background: none; padding: 2px 0; font-size: 13px; font-weight: 500; color: #2563eb; cursor: pointer; }
.sg-link:disabled { color: #cbd5e1; cursor: default; }

.sg-input { width: 100%; box-sizing: border-box; padding: 11px 12px; margin-bottom: 12px; font-size: 16px; color: #0f172a; border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; }
.sg-input:focus { border-color: #2563eb; outline: none; box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15); }

.font-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.font-box { padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 10px; text-align: center; background: #fff; cursor: pointer; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; transition: border-color 0.15s, background 0.15s; }
.font-box:hover { background: #f8fafc; }
.font-box.active { background: #eff6ff; border-color: #2563eb; box-shadow: 0 0 0 1px #2563eb inset; }
.font-preview { font-size: 20px; color: #111827; }

.sg-drop { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; height: 140px; border: 1.5px dashed #cbd5e1; border-radius: 12px; color: #334155; font-size: 14px; cursor: pointer; text-align: center; }
.sg-drop:hover { border-color: #2563eb; background: #f8fafc; }
.sg-drop small { color: #94a3b8; font-size: 12px; }
.sg-upload-preview { margin-top: 10px; text-align: center; }
.sg-upload-preview img { max-width: 100%; max-height: 140px; display: inline-block; }

.sg-error { margin: 10px 0 0; font-size: 13px; color: #dc2626; }
.sg-legal { margin: 14px 0 0; font-size: 12px; color: #94a3b8; }
.sg-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 14px; }
.sg-actions button { padding: 10px 18px; border-radius: 10px; font-size: 14px; font-weight: 600; cursor: pointer; }
.sg-cancel { background: #fff; border: 1px solid #e2e8f0; color: #334155; }
.sg-cancel:hover { background: #f8fafc; }
.sg-save { background: #2563eb; border: 1px solid #2563eb; color: #fff; }
.sg-save:hover { background: #1d4ed8; }

@media (max-width: 520px) {
  .sg-overlay { align-items: flex-end; padding: 0; }
  .sg-modal { max-width: none; border-radius: 16px 16px 0 0; padding: 16px 16px 20px; }
  .sg-pad { height: 220px; }
  .sg-actions button { flex: 1; }
}
</style>

<template>
  <div class="flex flex-col gap-6">
    <SectionCard title="Agreements" :subtitle="`${cards.length} ${cards.length === 1 ? 'agreement' : 'agreements'}`">
      <template #actions>
        <AppButton variant="outline" size="sm" icon="refresh-cw" :loading="loadingCards" @click="loadCards">Refresh</AppButton>
      </template>

      <p v-if="detail.isNew.value" class="py-4 text-center text-p-sm text-app-text-muted">Save the Sales Order first to create agreements.</p>
      <p v-else-if="!cards.length && !loadingCards" class="rounded-lg border border-dashed border-app-border py-8 text-center text-p-sm text-app-text-muted">
        No agreements created yet.
      </p>

      <div v-else class="flex flex-col gap-3">
        <div v-for="ag in cards" :key="ag.name" class="flex flex-col gap-2 rounded-lg border border-app-border bg-app-panel-2/40 p-4">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <router-link :to="`/Agreement/${encodeURIComponent(ag.name)}`" class="text-p-sm font-medium text-app-primary hover:underline">{{ ag.name }}</router-link>
              <p class="text-p-xs text-app-text-muted">Template: <span class="text-app-text">{{ ag.template || '—' }}</span></p>
            </div>
            <DocStatusBadge :status="ag.status || 'Draft'" />
          </div>

          <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-p-xs text-app-text-muted">
            <template v-if="ag.email_status">
              <span class="inline-flex items-center gap-1.5">Email <DocStatusBadge :status="ag.email_status" /></span>
              <span>{{ formatDatetime(ag.email_modified) }}</span>
              <span v-if="ag.email_error" class="text-red-600">{{ ag.email_error }}</span>
            </template>
            <span v-else>Email: not sent</span>
          </div>

          <div class="flex flex-wrap gap-2">
            <a v-if="ag.pdf" :href="ag.pdf" target="_blank" rel="noopener">
              <AppButton variant="outline" size="sm" icon="file-text">View PDF</AppButton>
            </a>
            <template v-if="ag.status !== 'Agreement signed'">
              <AppButton v-if="ag.can_resend || !ag.email_status" size="sm" icon="send" :loading="sendingName === ag.name" @click="send(ag)">
                {{ ag.email_status ? 'Resend Email' : 'Send Email' }}
              </AppButton>
              <AppButton v-else size="sm" variant="outline" disabled>Resend available in {{ remaining(ag.resend_after) }}</AppButton>
            </template>
          </div>
        </div>
      </div>
    </SectionCard>

    <SectionCard v-if="!detail.isNew.value && !locked" title="Create Agreement" subtitle="Fill a template with this order's details.">
      <div class="flex max-w-md flex-col gap-1.5">
        <label class="text-p-sm font-medium text-app-text-muted">Template</label>
        <AppCombobox v-model="template" :options="templateOptions" placeholder="Select template…" />
      </div>

      <div v-if="loadingTemplate" class="flex justify-center py-6"><LoadingIndicator class="h-5 w-5 text-app-text-muted" /></div>
      <div v-else-if="blocks.length" class="flex flex-col gap-4 border-t border-app-border pt-4">
        <p class="text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">Template fields</p>
        <div v-for="b in blocks" :key="keyOf(b)" :class="b.type === 'Rich_Text' || b.type === 'Text' ? 'max-w-3xl' : 'max-w-md'">
          <label class="mb-1.5 block text-p-sm font-medium text-app-text-muted">{{ b.label || b.name }}</label>
          <TextEditor
            v-if="b.type === 'Rich_Text'"
            :content="values[keyOf(b)] || ''"
            fixed-menu
            editor-class="min-h-[120px] rounded-b-lg border border-t-0 border-app-border px-3 py-2 text-p-sm"
            @change="(html) => (values[keyOf(b)] = html)"
          />
          <AppInput v-else :type="b.type === 'Number' ? 'number' : b.type === 'Date' ? 'date' : 'text'" :placeholder="`Enter ${b.label || b.name}…`" :model-value="values[keyOf(b)] || ''" @update:model-value="(v) => (values[keyOf(b)] = v)" />
        </div>
      </div>

      <div v-if="template" class="flex flex-wrap gap-2">
        <AppButton variant="outline" icon="eye" @click="preview">Preview</AppButton>
        <AppButton icon="save" :loading="saving && !sendAfter" :disabled="saving" @click="create(false)">Save</AppButton>
        <AppButton variant="outline" icon="send" :loading="saving && sendAfter" :disabled="saving" @click="create(true)">Save &amp; Send</AppButton>
      </div>
    </SectionCard>
  </div>
</template>

<script setup>
import AppInput from '@/components/ui/AppInput.vue'
// The Sales Order "Agreements" module (public/js/salesOrder.js's
// render_agreement_module): every agreement raised for this order with its
// PDF and email status (Send / Resend, throttled server-side to one every
// ten minutes), and a builder that fills a Pdf Agreement Template — Text /
// Number / Date / rich-text blocks, de-duplicated by type+name exactly as on
// desk — then previews it (a PDF in a new tab) or saves it, optionally
// emailing it straight away.
//
// Not ported: the desk's "auto mode" (draft an agreement while the Sales Order
// is still unsaved) stashed the draft in localStorage and nothing ever read it
// back, so here an agreement is created once the order exists.
import { computed, reactive, ref, watch } from 'vue'
import { call, LoadingIndicator, TextEditor } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import { useResource } from '@/composables/list/useResource'
import { formatDatetime } from '@/utils/list/formatValue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  name: { type: String, required: true },
  locked: { type: Boolean, default: false },
})

const cards = ref([])
const loadingCards = ref(false)
async function loadCards() {
  if (props.detail.isNew.value) return
  loadingCards.value = true
  try {
    cards.value = (await call('verp_staffing.crm.api.agreement.get_agreement_cards', { sales_order: props.name })) || []
  } finally {
    loadingCards.value = false
  }
}
watch(() => props.name, loadCards, { immediate: true })

function remaining(seconds) {
  if (seconds <= 0) return 'now'
  const mins = Math.floor(seconds / 60)
  return mins > 0 ? `${mins} min${mins > 1 ? 's' : ''}` : `${seconds % 60} sec`
}

const sendingName = ref('')
async function send(ag) {
  sendingName.value = ag.name
  try {
    const r = await call('verp_staffing.crm.api.agreement.send_existing_agreement', { agreement: ag.name })
    if (r?.success) notify.success('Agreement sent.')
    else notify.error('Failed to send the agreement.')
    loadCards()
  } catch (error) {
    notify.error(normalizeError(error).message)
  } finally {
    sendingName.value = ''
  }
}

// ── builder ───────────────────────────────────────────────────────────
const templates = useResource({
  url: 'frappe.client.get_list',
  params: { doctype: 'Pdf Agreement Template', filters: { is_active: 1 }, fields: ['name', 'title'], limit_page_length: 100 },
  notifyOnError: false,
  auto: true,
})

const template = ref('')
const templateOptions = computed(() => (templates.resource.data || []).map((t) => ({ label: t.title || t.name, value: t.name })))
const blocks = ref([])
const values = reactive({})
const loadingTemplate = ref(false)
// Same key the server reads back: "<type>::<name>".
const keyOf = (b) => `${b.type}::${b.name}`

watch(template, async (name) => {
  blocks.value = []
  Object.keys(values).forEach((k) => delete values[k])
  if (!name) return
  loadingTemplate.value = true
  try {
    const tpl = await call('frappe.client.get', { doctype: 'Pdf Agreement Template', name })
    let parsed = []
    try {
      parsed = JSON.parse(tpl.fields_json || '[]')
    } catch {
      parsed = []
    }
    const seen = new Set()
    blocks.value = parsed.filter((b) => {
      if (!b.name || !b.type || !['Text', 'Number', 'Date', 'Rich_Text'].includes(b.type)) return false
      const key = `${b.type.trim().toLowerCase()}|${b.name.trim().toLowerCase()}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  } finally {
    loadingTemplate.value = false
  }
})

const payload = () => JSON.stringify(Object.fromEntries(blocks.value.map((b) => [keyOf(b), String(values[keyOf(b)] ?? '').trim()])))

// The preview endpoint answers with a PDF download, so it's a plain form POST
// into a new tab rather than an XHR.
function preview() {
  const form = document.createElement('form')
  form.method = 'POST'
  form.action = '/api/method/verp_staffing.crm.api.agreement.preview_agreement'
  form.target = '_blank'
  form.style.display = 'none'
  for (const [name, value] of Object.entries({ template: template.value, data: payload(), csrf_token: window.csrf_token })) {
    const input = document.createElement('input')
    input.type = 'hidden'
    input.name = name
    input.value = value
    form.appendChild(input)
  }
  document.body.appendChild(form)
  form.submit()
  document.body.removeChild(form)
}

const saving = ref(false)
const sendAfter = ref(false)
async function create(send) {
  saving.value = true
  sendAfter.value = send
  try {
    await call('verp_staffing.crm.api.agreement.submit_and_generate', {
      sales_order: props.name,
      template: template.value,
      data: payload(),
      send_email: send ? 1 : 0,
    })
    notify.success(send ? 'Agreement created and sent.' : 'Agreement created.')
    template.value = ''
    loadCards()
  } catch (error) {
    notify.error(normalizeError(error).message)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-start justify-center bg-app-bg px-4 py-10">
    <div class="w-full max-w-2xl">
      <div class="mb-6 text-center">
        <h1 class="text-xl font-semibold text-app-text">Set up your workspace</h1>
        <p class="mt-1 text-p-sm text-app-text-muted">A few details to get this site ready.</p>
        <div class="mt-4 flex items-center justify-center gap-2">
          <template v-for="(s, i) in STEPS" :key="s">
            <span
              class="flex size-7 items-center justify-center rounded-full text-p-xs font-semibold"
              :class="i <= step ? 'bg-app-primary text-white' : 'bg-app-panel-2 text-app-text-muted'"
            >{{ i + 1 }}</span>
            <span class="text-p-sm" :class="i === step ? 'font-medium text-app-text' : 'text-app-text-muted'">{{ s }}</span>
            <span v-if="i < STEPS.length - 1" class="h-px w-8 bg-app-border" />
          </template>
        </div>
      </div>

      <div v-if="loading" class="flex justify-center py-16"><LoadingIndicator class="h-6 w-6 text-app-text-muted" /></div>

      <div v-else-if="working" class="flex flex-col items-center gap-3 rounded-xl border border-app-border bg-app-panel p-10 text-center shadow-sm">
        <LoadingIndicator class="h-6 w-6 text-app-primary" />
        <p class="text-p-base font-medium text-app-text">{{ workingMessage }}</p>
        <p class="text-p-sm text-app-text-muted">This can take a minute. Please don't close this page.</p>
      </div>

      <form v-else class="flex flex-col gap-5 rounded-xl border border-app-border bg-app-panel p-6 shadow-sm" @submit.prevent="next">
        <div v-if="errorMessage" class="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-p-sm text-red-700 dark:text-red-300">{{ errorMessage }}</div>

        <!-- Step 1: Welcome -->
        <template v-if="step === 0">
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <AppInput type="select" label="Your Language" required :options="languageOptions" v-model="form.language" />
            <AppInput type="select" label="Your Country" required :options="countryOptions" placeholder="Select Country" v-model="form.country" />
            <AppInput type="select" label="Time Zone" required :options="timezoneOptions" placeholder="Select Time Zone" v-model="form.timezone" />
            <AppInput type="select" label="Currency" required :options="data.currencies" placeholder="Select Currency" v-model="form.currency" />
          </div>
        </template>

        <!-- Step 2: Organization Setup -->
        <template v-else>
          <AppInput label="Company Name" required v-model="form.company_name" />

          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <AppDatePicker label="Fiscal Year Start Date" required v-model="form.fy_start_date" />
            <AppDatePicker label="Fiscal Year End Date" required v-model="form.fy_end_date" />
          </div>

          <label class="flex items-start gap-2 text-p-sm text-app-text">
            <input type="checkbox" class="mt-1" v-model="form.add_sample_data" />
            <span>
              Add Sample Data
              <span class="block text-p-xs text-app-text-muted">
                Seeds departments, users, employees, leads, opportunities, customers, orders and invoices so you can explore the system immediately. You can safely skip this on a production setup.
              </span>
            </span>
          </label>

          <div class="flex flex-col gap-4 border-t border-app-border pt-4">
            <h2 class="text-p-base font-semibold text-app-text">Email Configuration</h2>
            <AppInput label="Business Email" type="email" required v-model="form.business_email" @update:model-value="onEmailInput" />
            <AppInput label="Password / App Password" type="password" required v-model="form.email_password" />
            <AppInput type="select" label="Provider" :options="providerOptions" placeholder="Select provider" v-model="form.email_provider" @update:model-value="onProviderChange" />
          </div>

          <div class="rounded-lg border border-app-border">
            <button type="button" class="flex w-full items-center justify-between px-4 py-3 text-left text-p-sm font-semibold text-app-text" @click="showAdvanced = !showAdvanced">
              Additional Domain Settings
              <span class="size-4 text-app-text-muted" :class="showAdvanced ? 'lucide-chevron-up' : 'lucide-chevron-down'" />
            </button>
            <div v-if="showAdvanced" class="grid grid-cols-1 gap-x-6 gap-y-4 border-t border-app-border p-4 sm:grid-cols-2">
              <div class="flex flex-col gap-4">
                <AppInput label="Incoming Server" v-model="form.email_server" />
                <AppInput label="Incoming Port" type="number" v-model="form.incoming_port" />
                <label class="flex items-center gap-2 text-p-sm text-app-text"><input type="checkbox" v-model="form.use_imap" /> Use IMAP</label>
                <label class="flex items-center gap-2 text-p-sm text-app-text"><input type="checkbox" v-model="form.use_ssl" /> Use SSL</label>
                <label class="flex items-center gap-2 text-p-sm text-app-text"><input type="checkbox" v-model="form.use_tls" /> Use TLS</label>
              </div>
              <div class="flex flex-col gap-4">
                <AppInput label="SMTP Server" v-model="form.smtp_server" />
                <AppInput label="SMTP Port" type="number" v-model="form.smtp_port" />
                <label class="flex items-center gap-2 text-p-sm text-app-text"><input type="checkbox" v-model="form.use_starttls" /> Use STARTTLS</label>
                <label class="flex items-center gap-2 text-p-sm text-app-text"><input type="checkbox" v-model="form.use_ssl_for_outgoing" /> Use SSL for Outgoing</label>
              </div>
            </div>
          </div>
        </template>

        <div class="flex justify-between pt-1">
          <AppButton v-if="step > 0" variant="outline" type="button" @click="step--">Back</AppButton>
          <span v-else />
          <AppButton type="submit" :icon="step === STEPS.length - 1 ? 'check' : 'arrow-right'">
            {{ step === STEPS.length - 1 ? 'Complete Setup' : 'Next' }}
          </AppButton>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
// First-run setup for a fresh site - the SPA version of Frappe's setup wizard
// with this app's overridden second step (public/js/setup/setup_wizard.js):
// Welcome (language / country / time zone / currency), then Organization Setup
// (company, fiscal year, sample data, email account + mail-server presets).
// The router sends System Managers here while boot.setup_complete is false -
// the same test Desk uses (frappe.is_setup_complete).
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { call, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppDatePicker from '@/components/ui/AppDatePicker.vue'
import { EMAIL_PROVIDERS } from '@/utils/setup/emailProviders'
import { normalizeError } from '@/utils/common/errors'

const STEPS = ['Welcome', 'Organization Setup']
const step = ref(0)
const loading = ref(true)
const working = ref(false)
const workingMessage = ref('')
const errorMessage = ref('')
const showAdvanced = ref(false)
const data = reactive({ languages: { languages: [] }, country_info: {}, all_timezones: [], currencies: [], current: {} })

const form = reactive({
  language: 'English', country: '', timezone: '', currency: '',
  company_name: '', fy_start_date: '', fy_end_date: '', add_sample_data: false,
  business_email: '', email_password: '', email_provider: '',
  email_server: '', incoming_port: '', use_imap: true, use_ssl: false, use_tls: false,
  smtp_server: '', smtp_port: '', use_starttls: false, use_ssl_for_outgoing: false,
  append_emails_to_sent_folder: true, sent_folder_name: '',
})

const languageOptions = computed(() => data.languages.languages || [])
const countryOptions = computed(() => Object.keys(data.country_info).sort())
// Country-specific zones first, then every zone (as the Desk wizard lists them).
const timezoneOptions = computed(() => {
  const own = data.country_info[form.country]?.timezones || []
  return [...new Set([...[...own].sort(), ...data.all_timezones])]
})
const providerOptions = computed(() => Object.values(EMAIL_PROVIDERS).map((p) => p.label).sort((a, b) => a.localeCompare(b)))

onMounted(async () => {
  try {
    Object.assign(data, await call('verp_staffing.setup.wizard_api.get_wizard_data'))
    const cur = data.current || {}
    form.language = data.languages.default_language || 'English'
    form.country = cur.country || guessCountry() || ''
    form.timezone = cur.time_zone || ''
    form.currency = cur.currency || ''
    if (form.country) onCountryChange(form.country, !cur.time_zone, !cur.currency)
  } catch (e) {
    errorMessage.value = normalizeError(e).message
  } finally {
    loading.value = false
  }
})

function guessCountry() {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone === 'Asia/Calcutta' ? 'Asia/Kolkata' : Intl.DateTimeFormat().resolvedOptions().timeZone
    return Object.entries(data.country_info).find(([, info]) => (info.timezones || []).includes(tz))?.[0]
  } catch {
    return null
  }
}

function onCountryChange(country, setTimezone = true, setCurrency = true) {
  const info = data.country_info[country]
  if (!info) return
  if (setTimezone) form.timezone = (info.timezones || [])[0] || form.timezone
  if (setCurrency && info.currency) form.currency = info.currency
}
watch(() => form.country, (c) => c && onCountryChange(c))

// ---- email provider detection / presets (same rules as the Desk wizard) ----
const providerKey = (label) => label.toLowerCase().split(' ').join('_')
function detectProvider(email) {
  if (!email?.includes('@')) return null
  const domain = email.split('@').pop().toLowerCase()
  return Object.entries(EMAIL_PROVIDERS).find(([, p]) => p.domains.includes(domain))?.[0] || null
}
function applyDefaults(label) {
  const config = EMAIL_PROVIDERS[providerKey(label)]
  if (!config) return
  for (const [field, value] of Object.entries(config.defaults || {})) {
    form[field] = typeof form[field] === 'boolean' ? Boolean(value) : value
  }
}
function onEmailInput(email) {
  const key = detectProvider(email)
  if (key) {
    form.email_provider = EMAIL_PROVIDERS[key].label
    applyDefaults(form.email_provider)
  }
}
function onProviderChange(label) {
  applyDefaults(label)
}

// ---- validation (validate_organization_setup) ----
function validateOrganization() {
  if (!form.company_name.trim()) return 'Company Name is required.'
  if (!form.fy_start_date || !form.fy_end_date) return 'Fiscal Year dates are required.'
  if (!detectProvider(form.business_email) && !form.email_provider) return 'Please select your email provider.'
  if (form.fy_start_date >= form.fy_end_date) return 'Fiscal Year End Date must be after Start Date.'
  if (!form.business_email) return 'Business Email is required.'
  if (!form.email_password) return 'Email Password is required.'
  return ''
}

function next() {
  errorMessage.value = ''
  if (step.value === 0) {
    if (!form.language || !form.country || !form.timezone || !form.currency) {
      errorMessage.value = 'Language, country, time zone and currency are required.'
      return
    }
    step.value = 1
    return
  }
  const problem = validateOrganization()
  if (problem) {
    errorMessage.value = problem
    return
  }
  complete()
}

// setup_email first (validates/creates the mail domain + account), then Frappe's
// own setup_complete - the same two calls as the Desk wizard's action_on_complete.
async function complete() {
  const values = { ...form, lang: form.language }
  for (const k of ['add_sample_data', 'use_imap', 'use_ssl', 'use_tls', 'use_starttls', 'use_ssl_for_outgoing', 'append_emails_to_sent_folder']) {
    values[k] = form[k] ? 1 : 0
  }
  working.value = true
  workingMessage.value = 'Validating Email Configuration...'
  try {
    await call('verp_staffing.setup.email_utils.setup_email', { args: values })
    workingMessage.value = 'Setting up your site...'
    const r = await call('frappe.desk.page.setup_wizard.setup_wizard.setup_complete', { args: values })
    if (r?.status === 'ok') return finish()
    if (r?.status === 'registered') return waitForBackgroundSetup()
    throw new Error(r?.fail || 'Setup did not complete.')
  } catch (e) {
    working.value = false
    errorMessage.value = normalizeError(e).message
  }
}

// trigger_site_setup_in_background: setup runs as a queued job - poll until done.
async function waitForBackgroundSetup() {
  workingMessage.value = 'Starting the setup...'
  for (let i = 0; i < 150; i++) {
    await new Promise((r) => setTimeout(r, 2000))
    const s = await call('verp_staffing.setup.wizard_api.get_setup_status').catch(() => null)
    if (s?.setup_complete) return finish()
  }
  working.value = false
  errorMessage.value = 'Setup is taking longer than expected. Reload this page to check its progress.'
}

// Full reload so boot (setup_complete, sample-data flag, roles) is re-read.
function finish() {
  workingMessage.value = 'All set! Loading your workspace...'
  window.location.href = '/verp'
}
</script>

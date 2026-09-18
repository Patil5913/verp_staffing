<template>
  <SectionCard title="Addresses & Contacts">
    <p v-if="detail.isNew.value" class="py-4 text-center text-p-sm text-app-text-muted">Save first to add addresses and contacts.</p>
    <div v-else class="grid grid-cols-1 gap-6 md:grid-cols-2">
      <div v-for="group in groups" :key="group.doctype" class="flex flex-col gap-2">
        <div class="flex items-center justify-between">
          <p class="text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">{{ group.label }}</p>
          <AppButton v-if="canAdd" variant="outline" size="sm" icon="plus" @click="group.open()">New {{ group.doctype }}</AppButton>
        </div>
        <router-link
          v-for="row in group.rows"
          :key="row.name"
          :to="`/${group.doctype}/${encodeURIComponent(row.name)}`"
          class="rounded-lg border border-app-border bg-app-panel-2/40 px-3 py-2 text-p-sm text-app-text transition-colors hover:border-app-primary/40"
        >
          <p class="truncate font-medium">{{ row.title }}</p>
          <p v-if="row.subtitle" class="truncate text-p-xs text-app-text-muted">{{ row.subtitle }}</p>
        </router-link>
        <p v-if="!group.rows.length" class="rounded-lg border border-dashed border-app-border px-3 py-4 text-center text-p-xs text-app-text-muted">None yet.</p>
      </div>
    </div>

    <Dialog v-model="addressOpen" :options="{ title: 'New Address', size: 'lg' }">
      <template #body-content>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormControl label="Address Title" v-model="address.address_title" class="sm:col-span-2" />
          <FormControl type="select" label="Address Type" v-model="address.address_type" :options="ADDRESS_TYPES" required />
          <div class="pt-6"><Checkbox label="Is Primary Address" v-model="address.is_primary_address" /></div>
          <FormControl label="Address Line 1" v-model="address.address_line1" required class="sm:col-span-2" />
          <FormControl label="Address Line 2" v-model="address.address_line2" class="sm:col-span-2" />
          <FormControl label="City / Town" v-model="address.city" required />
          <FormControl label="State / Province" v-model="address.state" />
          <AppLinkField label="Country" doctype="Country" v-model="address.country" hide-add-new />
          <FormControl label="Postal Code" v-model="address.pincode" />
          <FormControl type="email" label="Email" v-model="address.email_id" />
          <FormControl label="Phone" v-model="address.phone" />
        </div>
      </template>
      <template #actions>
        <AppButton icon="save" :loading="saving" :disabled="!addressValid" @click="createAddress">Create</AppButton>
      </template>
    </Dialog>

    <Dialog v-model="contactOpen" :options="{ title: 'New Contact', size: 'lg' }">
      <template #body-content>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormControl label="First Name" v-model="contact.first_name" required />
          <FormControl label="Last Name" v-model="contact.last_name" />
          <FormControl type="email" label="Email" v-model="contact.email_id" />
          <FormControl label="Phone" v-model="contact.phone" />
          <FormControl label="Designation" v-model="contact.designation" />
          <FormControl label="Department" v-model="contact.department" />
          <div class="pt-6 sm:col-span-2"><Checkbox label="Is Primary Contact" v-model="contact.is_primary_contact" /></div>
        </div>
      </template>
      <template #actions>
        <AppButton icon="save" :loading="saving" :disabled="!contact.first_name.trim()" @click="createContact">Create</AppButton>
      </template>
    </Dialog>
  </SectionCard>
</template>

<script setup>
// Addresses and Contacts linked to this record (desk's address_html /
// contact_html blocks). Lists what's linked, and — new — creates either one
// linked back to this record (the Dynamic Link row Frappe's own "New Address"
// / "New Contact" buttons add), so a Company, Bank, Bank Account or Supplier
// can get its address and contacts without leaving the page. Each entry opens
// its own record for anything beyond these essentials.
import { computed, reactive, ref, watch } from 'vue'
import { call, Checkbox, Dialog, FormControl } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  doctype: { type: String, required: true },
  name: { type: String, required: true },
})

const ADDRESS_TYPES = ['Billing', 'Shipping', 'Office', 'Personal', 'Plant', 'Postal', 'Shop', 'Subsidiary', 'Warehouse', 'Other']
const addresses = ref([])
const contacts = ref([])
const canAdd = computed(() => props.detail.canWrite.value)

async function load() {
  const filters = [
    ['Dynamic Link', 'link_doctype', '=', props.doctype],
    ['Dynamic Link', 'link_name', '=', props.name],
  ]
  const [a, c] = await Promise.all([
    call('frappe.client.get_list', { doctype: 'Address', filters, fields: ['name', 'address_title', 'address_line1', 'city', 'country'], limit_page_length: 20 }).catch(() => []),
    call('frappe.client.get_list', { doctype: 'Contact', filters, fields: ['name', 'first_name', 'last_name', 'email_id'], limit_page_length: 20 }).catch(() => []),
  ])
  addresses.value = a || []
  contacts.value = c || []
}
watch(() => props.name, (n) => n && n !== 'new' && load(), { immediate: true })

const addressOpen = ref(false)
const contactOpen = ref(false)
const saving = ref(false)
const blankAddress = () => ({ address_title: '', address_type: 'Billing', address_line1: '', address_line2: '', city: '', state: '', country: '', pincode: '', email_id: '', phone: '', is_primary_address: false })
const blankContact = () => ({ first_name: '', last_name: '', email_id: '', phone: '', designation: '', department: '', is_primary_contact: false })
const address = reactive(blankAddress())
const contact = reactive(blankContact())

const addressValid = computed(() => address.address_line1.trim() && address.city.trim() && address.country && address.address_type)

const link = () => [{ link_doctype: props.doctype, link_name: props.name }]

async function insert(doc, label, done) {
  saving.value = true
  try {
    await call('frappe.client.insert', { doc: { ...doc, links: link() } })
    notify.success(`${label} created.`)
    done()
    await load()
  } catch (error) {
    notify.error(normalizeError(error).message)
  } finally {
    saving.value = false
  }
}

function createAddress() {
  const { is_primary_address, ...rest } = address
  const doc = { doctype: 'Address', ...rest, address_title: rest.address_title.trim() || props.name, is_primary_address: is_primary_address ? 1 : 0 }
  return insert(doc, 'Address', () => (addressOpen.value = false))
}

function createContact() {
  const c = contact
  const doc = {
    doctype: 'Contact',
    first_name: c.first_name.trim(),
    last_name: c.last_name.trim(),
    designation: c.designation,
    department: c.department,
    is_primary_contact: c.is_primary_contact ? 1 : 0,
    email_ids: c.email_id.trim() ? [{ email_id: c.email_id.trim(), is_primary: 1 }] : [],
    phone_nos: c.phone.trim() ? [{ phone: c.phone.trim(), is_primary_phone: 1 }] : [],
  }
  return insert(doc, 'Contact', () => (contactOpen.value = false))
}

const groups = computed(() => [
  {
    doctype: 'Address',
    label: 'Addresses',
    open: () => (Object.assign(address, blankAddress()), (addressOpen.value = true)),
    rows: addresses.value.map((r) => ({ name: r.name, title: r.address_title || r.name, subtitle: [r.address_line1, r.city, r.country].filter(Boolean).join(', ') })),
  },
  {
    doctype: 'Contact',
    label: 'Contacts',
    open: () => (Object.assign(contact, blankContact()), (contactOpen.value = true)),
    rows: contacts.value.map((r) => ({ name: r.name, title: [r.first_name, r.last_name].filter(Boolean).join(' ') || r.name, subtitle: r.email_id })),
  },
])
</script>

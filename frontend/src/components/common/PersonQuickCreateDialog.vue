<template>
  <Dialog v-model="isOpen" :options="{ title: `New ${doctype}`, size: 'sm' }">
    <template #body-content>
      <StateBanner
        v-if="detail.meta.isPermissionError"
        icon="lock"
        title="Permission denied"
        :description="`You don't have access to create ${doctype}.`"
      />
      <StateBanner
        v-else-if="detail.meta.hasError"
        icon="alert-triangle"
        title="Couldn't load this form"
        :description="detail.meta.errorMessage"
      />
      <div v-else-if="detail.meta.isLoading && !detail.meta.resource.data" class="flex justify-center py-12">
        <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
      </div>

      <div v-else class="flex flex-col gap-4">
        <AppInput v-model="name" :label="nameLabel" required :error="triedSave && !name ? `${nameLabel} is required` : ''" />
        <template v-if="isCustomer">
          <AppLinkField
            label="Customer From"
            doctype="DocType"
            :filters="{ name: ['in', ['Lead', 'Opportunity']] }"
            hide-add-new
            v-model="customerFrom"
          />
          <FieldControl
            v-if="customerFrom"
            :field="{ fieldname: 'party_name', label: 'Party', fieldtype: 'Link', options: customerFrom }"
            v-model="partyName"
          />
        </template>
        <AppInput v-model="phone" type="text" label="Phone Number" placeholder="Exp: +1xxxxxxxxxx" :error="phoneError" />
        <AppInput v-model="email" type="email" label="Email" :error="emailError" />
      </div>
    </template>

    <template #actions>
      <div class="flex w-full items-center justify-between gap-2">
        <AppButton variant="outline" icon="external-link" @click="openFullForm">Edit full form</AppButton>
        <div class="flex gap-2">
          <AppButton variant="outline" @click="isOpen = false">Cancel</AppButton>
          <AppButton variant="primary" icon="save" :loading="detail.save.isLoading" @click="onSave">Save</AppButton>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
// Quick-create for Lead / Opportunity / Customer - these don't use the
// generic meta-driven QuickCreateDialog (see DocListView.vue's per-doctype
// override wiring). Only `name1` is a real field on the doctype itself;
// phone/email go to the linked Lead Detail Form instead, via the same
// `_<fieldname>` convention Lead.create_lead_detail / Opportunity.after_insert
// / Customer.after_insert read off the in-memory doc at insert time - see
// those controllers for the other half of this.
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import FieldControl from '@/components/detail/FieldControl.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { useDocDetail } from '@/composables/detail/useDocDetail'
import { isValidPhone, isValidEmail, sanitizePhone } from '@/utils/detail/fieldFormats'
import { notify } from '@/utils/common/notify'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  doctype: { type: String, required: true },
  initialValue: { type: String, default: '' },
  navigateOnCreate: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue', 'created'])

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const router = useRouter()

const doctypeRef = computed(() => props.doctype)
const nameRef = ref('new')
const detail = useDocDetail(doctypeRef, nameRef)

const nameLabel = computed(() => detail.fields.value.find((f) => f.fieldname === 'name1')?.label || 'Name')

const name = ref(props.initialValue)
// A new Lead starts with the +1 country code already typed in.
const DEFAULT_PHONE = ['Lead', 'Opportunity', 'Customer'].includes(props.doctype) ? '+1' : ''
const phone = ref(DEFAULT_PHONE)
// Just the untouched prefix is "no phone", not an invalid one.
const phoneEntered = computed(() => phone.value.trim() && phone.value.trim() !== DEFAULT_PHONE)
const email = ref('')
const triedSave = ref(false)

// Only Customer actually has a "where did this come from" concept - a
// Customer quick-created without it is indistinguishable from one
// created standalone (Customer.after_insert's CASE 2), losing the link to
// whichever Lead/Opportunity it should trace back to.
const isCustomer = computed(() => props.doctype === 'Customer')
const customerFrom = ref('')
const partyName = ref('')

const phoneError = computed(() => (triedSave.value && phoneEntered.value && !isValidPhone(phone.value) ? 'Must include country code' : ''))
const emailError = computed(() => (triedSave.value && email.value && !isValidEmail(email.value) ? 'Must be a valid email address' : ''))

function openFullForm() {
  isOpen.value = false
  router.push(`/${encodeURIComponent(props.doctype)}/new`)
}

async function onSave() {
  triedSave.value = true
  if (!name.value || phoneError.value || emailError.value) return

  const values = { name1: name.value }
  if (phoneEntered.value) values._personal_phone_number = sanitizePhone(phone.value)
  if (email.value) values._email = email.value
  if (isCustomer.value && customerFrom.value) values.customer_from = customerFrom.value
  if (isCustomer.value && partyName.value) values.party_name = partyName.value

  const ok = await detail.submit(values)
  if (!ok) return

  const newName = detail.meta.resource.data?.name
  notify.success(`${props.doctype} created.`)
  isOpen.value = false
  emit('created', newName)
  if (newName && props.navigateOnCreate) {
    router.push(`/${encodeURIComponent(props.doctype)}/${encodeURIComponent(newName)}`)
  }
}
</script>

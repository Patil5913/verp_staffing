<template>
  <AppButton variant="outline" icon="calendar-plus" @click="open = true">Create Interview</AppButton>

  <Dialog v-model="open" :options="{ title: 'Create Interview', size: 'md' }">
    <template #body-content>
      <div class="flex flex-col gap-4">
        <AppInput label="Company" v-model="company" required />
        <AppInput label="Role" v-model="role" required />
      </div>
    </template>
    <template #actions>
      <AppButton icon="check" :loading="creating" :disabled="!company.trim() || !role.trim()" @click="create">
        Create Interview
      </AppButton>
    </template>
  </Dialog>
</template>

<script setup>
import AppInput from '@/components/ui/AppInput.vue'
// marketing.js's "Create Interview" dialog: company + role, status taken
// from ERP Configuration's default_interview_status, inserted with the
// Marketing record as its link, then straight to the new Interview.
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { call, Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

defineOptions({ inheritAttrs: false })
const props = defineProps({ name: { type: String, required: true } })

const router = useRouter()
const open = ref(false)
const company = ref('')
const role = ref('')
const creating = ref(false)

async function create() {
  creating.value = true
  try {
    const status = await call('frappe.client.get_single_value', {
      doctype: 'ERP Configuration',
      field: 'default_interview_status',
    })
    if (!status) {
      notify.error('Default Interview Status is not set in ERP Configuration.')
      return
    }
    const doc = await call('frappe.client.insert', {
      doc: { doctype: 'Interview', marketing_link: props.name, company: company.value.trim(), role: role.value.trim(), status },
    })
    notify.success('Interview created.')
    open.value = false
    company.value = role.value = ''
    router.push(`/Interview/${encodeURIComponent(doc.name)}`)
  } catch (error) {
    notify.error(normalizeError(error).message)
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <AppButton variant="outline" icon="calendar-plus" @click="open = true">Create Interview</AppButton>

  <Dialog v-model="open" :options="{ title: 'Create Interview', size: 'md' }">
    <template #body-content>
      <div class="flex flex-col gap-4">
        <AppInput label="Company" v-model="company" required />
        <AppInput label="Role" v-model="role" required />
        <!-- The application behind this interview may have been filled by an earlier holder of the record. -->
        <div v-if="previousTeam.length" class="flex flex-col gap-1">
          <AppInput label="Add interview for" type="select" v-model="assignTo" :options="assigneeOptions" />
          <p class="text-p-xs text-app-text-muted">Pick an earlier team member if their application brought this interview in.</p>
        </div>
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
import { computed, ref, watch } from 'vue'
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
const assignTo = ref('')
const previousTeam = ref([])
const assigneeOptions = computed(() => [
  { label: 'Me', value: '' },
  ...previousTeam.value.map((p) => ({ label: `${p.employee_name} (earlier team)`, value: p.employee })),
])

watch(open, async (isOpen) => {
  if (!isOpen) return
  assignTo.value = ''
  try {
    previousTeam.value = (await call('verp_staffing.crm.api.helpers.get_interview_assignee_options', { marketing: props.name })) || []
  } catch {
    previousTeam.value = []
  }
})

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
      doc: { doctype: 'Interview', marketing_link: props.name, company: company.value.trim(), role: role.value.trim(), status, ...(assignTo.value ? { assign_to: assignTo.value } : {}) },
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

<template>
  <Dialog v-model="open" :options="{ title: 'Create Opportunity from Lead', size: 'md' }">
    <template #body-content>
      <div class="flex flex-col gap-4">
        <p class="text-p-sm text-app-text-muted">
          The Opportunity is assigned to a Sales employee automatically, unless you choose the owner yourself.
        </p>
        <AppCheckbox label="Want to assign Opportunity Owner Manually?" v-model="manualAssign" />
        <AppLinkField v-if="manualAssign" label="Opportunity Owner" doctype="Employee" :filters="{ department: 'Sales' }" v-model="owner" />
      </div>
    </template>
    <template #actions>
      <AppButton icon="target" :loading="creating" @click="create">Create</AppButton>
    </template>
  </Dialog>
</template>

<script setup>
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
// The "Create Opportunity" dialog from lead.js (open_create_opportunity_dialog):
// auto-assign to Sales via get_auto_assign_employee, or pick the owner by
// hand, then create_opportunity_from_lead.
import { ref } from 'vue'
import { call, Dialog } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

const props = defineProps({ leadName: { type: String, required: true } })
const emit = defineEmits(['created'])
const open = defineModel({ type: Boolean, default: false })

const manualAssign = ref(false)
const owner = ref('')
const creating = ref(false)

async function create() {
  creating.value = true
  try {
    let assignee = owner.value
    if (!manualAssign.value) {
      assignee = await call('verp_staffing.crm.api.auto_assign.get_auto_assign_employee', {
        department: 'Sales',
        target_doctype: 'Opportunity',
        owner_field: 'opportunity_owner',
      })
    } else if (!assignee) {
      notify.error('Select an Opportunity Owner.')
      return
    }
    const name = await call('verp_staffing.crm.doctype.lead.lead.create_opportunity_from_lead', { lead: props.leadName, owner: assignee })
    notify.success(`Opportunity created: ${name}`)
    open.value = false
    emit('created', name)
  } catch (error) {
    notify.error(normalizeError(error).message)
  } finally {
    creating.value = false
  }
}
</script>

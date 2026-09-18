<template>
  <div class="flex flex-col gap-4">
    <StateBanner
      v-if="opportunity.resource.data"
      icon="lock"
      title="This Lead is locked"
      description="An Opportunity already exists for this Lead, so it can no longer be edited."
    />

    <template v-if="leadDetail.exists.value">
      <div class="flex flex-col gap-4 rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
        <h2 class="text-p-lg font-medium text-app-text">Lead Detail Form</h2>

        <div class="grid grid-cols-1 items-start gap-x-6 gap-y-5 sm:grid-cols-2">
          <div
            v-for="field in leadDetail.fields.value"
            :key="field.fieldname"
            :class="isWide(field) ? 'col-span-full' : ''"
          >
            <FieldControl
              :field="field"
              v-model="leadDetail.values[field.fieldname]"
              :disabled="locked || !leadDetail.canWrite.value || field.read_only"
              :show-errors="triedSave"
            />
          </div>
        </div>
      </div>

      <ChildTableField
        v-for="table in leadDetail.tables.value"
        :key="table.fieldname"
        :table="table"
        :rows="leadDetail.values[table.fieldname] || []"
        :disabled="locked || !leadDetail.canWrite.value"
        @update:rows="(rows) => (leadDetail.values[table.fieldname] = rows)"
      />

      <div v-if="!locked && leadDetail.canWrite.value" class="flex justify-end">
        <AppButton
          icon="save"
          :disabled="!leadDetail.isDirty.value"
          :loading="leadDetail.save.isLoading"
          @click="onSaveLeadDetail"
        >
          Save Lead Details
        </AppButton>
      </div>
    </template>

    <Dialog
      v-model="showOpportunityDialog"
      :options="{ title: 'Create Opportunity from Lead' }"
    >
      <template #body-content>
        <div class="flex flex-col gap-4">
          <Checkbox label="Want to assign Opportunity Owner Manually?" v-model="manualAssign" />
          <AppLinkField
            v-if="manualAssign"
            label="Opportunity Owner"
            doctype="Employee"
            :filters="{ department: 'Sales' }"
            v-model="opportunityOwner"
          />
        </div>
      </template>
      <template #actions>
        <AppButton icon="target" :loading="creatingOpportunity" @click="onCreateOpportunity">Create</AppButton>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Checkbox, Dialog } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import FieldControl from './FieldControl.vue'
import ChildTableField from './ChildTableField.vue'
import { useResource } from '@/composables/list/useResource'
import { useLeadDetailForm } from '@/composables/detail/useLeadDetailForm'
import { notify } from '@/utils/common/notify'
import { validateFieldValue } from '@/utils/detail/fieldFormats'

const props = defineProps({
  leadName: { type: String, required: true },
})
const emit = defineEmits(['locked-change'])

const leadName = computed(() => props.leadName)

const opportunity = useResource({
  url: 'verp_staffing.crm.doctype.lead.lead.lead_has_opportunity',
  makeParams: () => ({ lead_name: leadName.value }),
  notifyOnError: false,
  auto: true,
})

const locked = computed(() => !!opportunity.resource.data)
watch(locked, (value) => emit('locked-change', value), { immediate: true })

const leadDetail = useLeadDetailForm(leadName)

function isWide(field) {
  return ['Small Text', 'Long Text', 'Text Editor'].includes(field.fieldtype)
}

const triedSave = ref(false)
async function onSaveLeadDetail() {
  triedSave.value = true
  const firstError = leadDetail.fields.value.find(
    (f) => !f.read_only && validateFieldValue(f, leadDetail.values[f.fieldname]),
  )
  if (firstError) return false
  return leadDetail.submit()
}

const showOpportunityDialog = ref(false)
const manualAssign = ref(false)
const opportunityOwner = ref('')
const creatingOpportunity = ref(false)

async function onCreateOpportunity() {
  creatingOpportunity.value = true
  try {
    let owner = opportunityOwner.value
    if (!manualAssign.value) {
      const autoAssign = useResource({ url: 'verp_staffing.crm.api.auto_assign.get_auto_assign_employee' })
      owner = await autoAssign.resource.submit({
        department: 'Sales',
        target_doctype: 'Opportunity',
        owner_field: 'opportunity_owner',
      })
      if (!owner) return // error already toasted by useResource
    } else if (!owner) {
      notify.error('Select an Opportunity Owner.')
      return
    }

    const createOpportunity = useResource({
      url: 'verp_staffing.crm.doctype.lead.lead.create_opportunity_from_lead',
    })
    const name = await createOpportunity.resource.submit({ lead: leadName.value, owner })
    if (!name) return // error already toasted by useResource

    notify.success(`Opportunity created: ${name}`)
    showOpportunityDialog.value = false
    opportunity.resource.reload()
  } finally {
    creatingOpportunity.value = false
  }
}

defineExpose({
  locked,
  isDirty: computed(() => leadDetail.isDirty.value),
  save: onSaveLeadDetail,
  showCreateOpportunity: () => (showOpportunityDialog.value = true),
})
</script>

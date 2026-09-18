<template>
  <Dialog v-model="isOpen" :options="{ title: `New ${doctype}`, size: 'lg' }">
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

      <template v-else>
        <p v-if="!requiredFieldnames.length" class="text-p-sm text-app-text-muted">
          {{ doctype }} has no required fields — save to create it as-is, or open the full form to fill in more.
        </p>
        <DocDetailView v-else :doctype="doctype" :detail="detail" :fieldnames="requiredFieldnames" />
      </template>
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
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import { useDocDetail } from '@/composables/detail/useDocDetail'
import { notify } from '@/utils/common/notify'

// A lightweight "quick create" modal, opened from the list view's Add New
// button: just the doctype's required fields, with an escape hatch to the
// full detail form for everything else. Only mounted while open (see
// DocListView's v-if), so each open starts from a fresh useDocDetail('new')
// instance instead of carrying over a previous attempt's values.
const props = defineProps({
  modelValue: { type: Boolean, default: false },
  doctype: { type: String, required: true },
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

const requiredFieldnames = computed(() => detail.fields.value.filter((f) => f.reqd).map((f) => f.fieldname))

function openFullForm() {
  isOpen.value = false
  router.push({ name: 'DocDetail', params: { doctype: props.doctype, name: 'new' } })
}

async function onSave() {
  const ok = await detail.submit()
  if (!ok) return

  const newName = detail.meta.resource.data?.name
  notify.success(`${props.doctype} created.`)
  isOpen.value = false
  emit('created')
  if (newName) {
    router.push({ name: 'DocDetail', params: { doctype: props.doctype, name: newName } })
  }
}
</script>

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
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
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
  // Prefills the doctype's title field (e.g. from a Link field's search
  // text) so "Create New" from a combobox doesn't require retyping.
  initialValue: { type: String, default: '' },
  // Link fields want the new doc's name handed back so they can select it
  // inline, not a navigation away from the record they're editing.
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

const requiredFieldnames = computed(() => detail.fields.value.filter((f) => f.reqd).map((f) => f.fieldname))

watch(
  () => detail.meta.resource.data,
  (data) => {
    if (!data || !props.initialValue) return
    const titleField = data.title_field || 'name'
    if (!detail.values[titleField]) detail.values[titleField] = props.initialValue
  },
  { immediate: true },
)

// Desk only shows the Quick Entry dialog for a doctype with quick_entry=1
// on its DocType — everything else jumps straight to the full form. This
// dialog was opening unconditionally instead.
watch(
  () => detail.meta.resource.data,
  (data) => {
    if (data && !data.quick_entry) openFullForm()
  },
  { immediate: true },
)

function openFullForm() {
  isOpen.value = false
  // A plain path, not a named route: some doctypes (Lead, User) have their
  // own detail page routed ahead of the generic DocDetail one — see
  // router.js — and this lets vue-router pick whichever one matches instead
  // of this dialog having to know which doctypes are customized.
  router.push(`/${encodeURIComponent(props.doctype)}/new`)
}

async function onSave() {
  const ok = await detail.submit()
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

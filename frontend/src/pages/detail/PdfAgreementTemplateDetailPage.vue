<template>
  <DetailPageLayout :title="recordTitle" :tabs="tabs" v-model:active-tab="activeTab" :detail="detail" @back="goBack">
    <template #actions>
      <RecordActionBar
        show-save
        :save-dirty="isDirty"
        :save-loading="saving"
        :show-delete="!detail.isNew.value && detail.canDelete.value"
        :delete-loading="deleting"
        @save="onSave"
        @delete="showDeleteDialog = true"
      />
    </template>

    <template #tab-details>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <div class="flex flex-col gap-6">
          <div class="rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
            <DocDetailView :doctype="doctype" :detail="detail" />
          </div>

          <div class="flex flex-col gap-3">
            <h3 class="text-p-base font-medium text-app-text">Builder</h3>
            <PdfFieldBuilder
              :pdf-url="detail.values.upload_pdf_template"
              :disabled="!detail.canWrite.value"
              :dirty="isDirty"
              v-model="builderFields"
              @save="onSave"
            />
          </div>
        </div>
      </div>
    </template>

    <template #tab-notes>
      <ActivityTimeline
        :doctype="doctype"
        :name="name"
        :types="['note', 'update']"
        show-composer
        empty-text="Nothing here yet — add the first note below."
      />
    </template>

    <template #tab-activity>
      <ActivityTimeline
        :doctype="doctype"
        :name="name"
        :types="['task', 'event']"
        allow-create
        empty-text="No tasks or events linked to this record yet."
      />
    </template>
  </DetailPageLayout>

  <Dialog
    v-model="showDeleteDialog"
    :options="{
      title: `Delete this ${doctype}?`,
      message: `This permanently deletes this record. This can't be undone.`,
      icon: { name: 'trash-2', appearance: 'danger' },
    }"
  >
    <template #actions>
      <AppButton variant="danger" icon="trash-2" :loading="deleting" @click="onDelete">Delete</AppButton>
    </template>
  </Dialog>
</template>

<script setup>
// Pdf Agreement Template's own detail page. title/upload_pdf_template/
// is_active are plain fields, so they're rendered by the same
// DocDetailView every other doctype uses — no customization needed there.
// fields_json (the drag-and-drop field layout) is a hidden JSON field, so
// — same as Hierarchy's role_hierarchy_json — it's excluded from the
// generic get_doc_meta payload, fetched once via the generic
// frappe.client.get, edited locally through PdfFieldBuilder.vue, and
// merged into the generic save_doc_fields payload on save. No new backend
// endpoints: pdf_agreement_template.py's own validate() already handles
// moving a newly-uploaded private PDF to a public file automatically.
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import PdfFieldBuilder from '@/components/detail/esign/PdfFieldBuilder.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import { useDocDetail } from '@/composables/detail/useDocDetail'
import { useResource } from '@/composables/list/useResource'
import { useUnsavedChangesGuard } from '@/composables/common/useUnsavedChangesGuard'
import { notify } from '@/utils/common/notify'

const route = useRoute()
const router = useRouter()

const doctype = computed(() => 'Pdf Agreement Template')
const name = computed(() => route.params.name)

const detail = useDocDetail(doctype, name)

const recordTitle = computed(() => {
  if (detail.isNew.value) return 'New Pdf Agreement Template'
  return detail.values.title || name.value
})

const DEFAULT_TABS = [
  { key: 'details', label: 'Details' },
  { key: 'notes', label: 'Notes' },
  { key: 'activity', label: 'Activity' },
]
const tabs = computed(() => (detail.isNew.value ? DEFAULT_TABS.filter((t) => t.key === 'details') : DEFAULT_TABS))
const activeTab = ref('details')

// ── fields_json (hidden — not part of get_doc_meta) ────────────────────────
const builderFields = ref([])
const fieldsSnapshot = ref('[]')
const fieldsJson = computed(() => JSON.stringify(builderFields.value))

const existingResource = useResource({ url: 'frappe.client.get', notifyOnError: false })

watch(
  () => detail.meta.resource.data,
  async (data) => {
    if (!data) return
    if (detail.isNew.value) {
      builderFields.value = []
      fieldsSnapshot.value = '[]'
      return
    }
    const doc = await existingResource.resource.submit({ doctype: 'Pdf Agreement Template', name: name.value })
    if (!doc) return
    let parsed = []
    try {
      parsed = doc.fields_json ? JSON.parse(doc.fields_json) : []
    } catch {
      parsed = []
    }
    builderFields.value = parsed
    fieldsSnapshot.value = JSON.stringify(parsed)
  },
  { immediate: true },
)

const isDirty = computed(() => detail.isDirty.value || fieldsJson.value !== fieldsSnapshot.value)

// ── Save ────────────────────────────────────────────────────────────────
const saving = ref(false)

async function onSave() {
  const wasNew = detail.isNew.value
  saving.value = true
  try {
    const ok = await detail.submit({
      ...detail.values,
      fields_json: fieldsJson.value,
    })
    if (!ok) return false

    fieldsSnapshot.value = fieldsJson.value

    if (wasNew) {
      const newName = detail.meta.resource.data?.name
      bypassNext()
      router.replace(`/${encodeURIComponent(doctype.value)}/${encodeURIComponent(newName)}`)
    }
    return true
  } finally {
    saving.value = false
  }
}

const { bypassNext } = useUnsavedChangesGuard(isDirty, onSave)

function goBack() {
  router.push({ name: 'DocList', params: { doctype: doctype.value } })
}

const showDeleteDialog = ref(false)
const deleteResource = useResource({ url: 'verp_staffing.utils.list_view.delete_docs' })
const deleting = computed(() => deleteResource.isLoading)

async function onDelete() {
  const result = await deleteResource.resource.submit({ doctype: doctype.value, names: [name.value] })
  if (!result) return
  if (result.failed.length) {
    notify.error(result.failed[0].error)
    return
  }
  showDeleteDialog.value = false
  notify.success('Deleted.')
  bypassNext()
  router.push({ name: 'DocList', params: { doctype: doctype.value } })
}
</script>

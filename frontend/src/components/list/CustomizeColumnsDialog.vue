<template>
  <Dialog v-model="isOpen" :options="{ title: `Customize columns — ${doctype}`, size: 'xl' }">
    <template #body-content>
      <p class="mb-4 text-p-sm text-app-text-muted">
        Pick which columns show in {{ doctype }}'s list view and drag to set their order. This
        is a shared setting — it applies to every user and role, not just yours.
      </p>

      <div class="grid grid-cols-2 gap-4">
        <div class="flex min-w-0 flex-col gap-2">
          <h4 class="text-p-sm font-medium text-app-text-muted">Available columns</h4>
          <draggable
            v-model="available"
            :group="{ name: 'columns' }"
            item-key="fieldname"
            class="flex min-h-52 flex-col gap-1 rounded-md border border-dashed border-app-border p-2"
          >
            <template #item="{ element }">
              <div
                class="flex cursor-grab items-center gap-2 rounded-md border border-app-border bg-app-panel px-2 py-1.5 text-p-sm active:cursor-grabbing"
              >
                <FeatherIcon name="move" class="h-3.5 w-3.5 shrink-0 text-app-text-muted" />
                <span class="truncate">{{ element.label }}</span>
              </div>
            </template>
            <template #footer>
              <p v-if="!available.length" class="px-1 py-2 text-p-sm text-app-text-muted">
                All available columns are visible.
              </p>
            </template>
          </draggable>
        </div>

        <div class="flex min-w-0 flex-col gap-2">
          <h4 class="flex items-center justify-between text-p-sm font-medium text-app-text-muted">
            <span>Visible columns</span>
            <span>{{ selected.length }}</span>
          </h4>
          <draggable
            v-model="selected"
            :group="{ name: 'columns' }"
            item-key="fieldname"
            class="flex min-h-52 flex-col gap-1 rounded-md border border-app-border p-2"
          >
            <template #item="{ element }">
              <div
                class="flex cursor-grab items-center gap-2 rounded-md border border-app-border bg-app-panel px-2 py-1.5 text-p-sm active:cursor-grabbing"
              >
                <FeatherIcon name="move" class="h-3.5 w-3.5 shrink-0 text-app-text-muted" />
                <span class="min-w-0 flex-1 truncate">{{ element.label }}</span>
                <Button variant="ghost" icon="x" size="sm" @click="removeColumn(element)" />
              </div>
            </template>
            <template #footer>
              <p v-if="!selected.length" class="px-1 py-2 text-p-sm text-app-text-muted">
                Drag a column here to show it.
              </p>
            </template>
          </draggable>
        </div>
      </div>
    </template>

    <template #actions>
      <div class="flex w-full items-center justify-between">
        <Button
          variant="outline"
          theme="red"
          icon-left="rotate-ccw"
          :disabled="!columnsCustomized"
          :loading="saving.loading && isResetting"
          @click="onReset"
        >
          Reset to default
        </Button>
        <div class="flex gap-2">
          <Button variant="outline" icon-left="x" @click="isOpen = false">Cancel</Button>
          <Button
            variant="solid"
            icon-left="save"
            :disabled="!selected.length || !isDirty"
            :loading="saving.loading && !isResetting"
            @click="onSave"
          >
            Save
          </Button>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, Dialog, FeatherIcon } from 'frappe-ui'
import draggable from 'vuedraggable'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  doctype: { type: String, required: true },
  // Full selectable-field catalog, e.g. meta.fields.
  fields: { type: Array, default: () => [] },
  // Currently active columns, in order, e.g. meta.list_fields.
  listFields: { type: Array, default: () => [] },
  columnsCustomized: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const selected = ref([])
const available = ref([])
const isResetting = ref(false)
const initialOrder = ref([])

// Re-hydrated from the current meta every time the dialog opens, so it
// always starts from what's actually on screen rather than stale state
// left over from a previous open/close.
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    const selectedNames = new Set(props.listFields.map((f) => f.fieldname))
    selected.value = props.listFields.map((f) => ({ ...f }))
    available.value = props.fields
      .filter((f) => !selectedNames.has(f.fieldname))
      .map((f) => ({ ...f }))
    initialOrder.value = selected.value.map((f) => f.fieldname)
  },
)

// Dims Save until the column set/order actually differs from what's saved
// — dragging columns around back to their original order shouldn't leave
// Save looking actionable.
const isDirty = computed(() => {
  const current = selected.value.map((f) => f.fieldname)
  return current.length !== initialOrder.value.length || current.some((f, i) => f !== initialOrder.value[i])
})

function removeColumn(element) {
  selected.value = selected.value.filter((f) => f.fieldname !== element.fieldname)
  available.value = [...available.value, element]
}

const saving = useResource({
  url: 'verp_staffing.utils.list_view.set_list_view_columns',
  onSuccess(data) {
    notify.success(isResetting.value ? 'Columns reset to default.' : 'Columns updated.')
    isOpen.value = false
    emit('saved', data)
  },
})

function onSave() {
  isResetting.value = false
  saving.resource.submit({
    doctype: props.doctype,
    fields: selected.value.map((f) => f.fieldname),
  })
}

function onReset() {
  isResetting.value = true
  saving.resource.submit({ doctype: props.doctype, fields: [] })
}
</script>

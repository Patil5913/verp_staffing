<template>
  <div class="flex flex-col gap-5">
    <!-- Completeness + section jump chips -->
    <div class="sticky top-0 z-10 -mx-1 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-app-border bg-app-panel/95 px-4 py-3 shadow-sm backdrop-blur">
      <div class="flex items-center gap-3">
        <div class="h-2 w-32 overflow-hidden rounded-full bg-app-panel-2">
          <div class="h-full rounded-full bg-app-primary transition-all" :style="{ width: completeness + '%' }" />
        </div>
        <span class="text-p-sm font-medium text-app-text">{{ completeness }}% complete</span>
      </div>
      <nav class="flex min-w-0 flex-1 flex-wrap gap-1.5">
        <button
          v-for="group in groups"
          :key="group.key"
          type="button"
          class="rounded-full border border-app-border px-2.5 py-1 text-p-xs font-medium text-app-text-muted transition-colors hover:border-app-primary/50 hover:text-app-primary"
          @click="jump(group.key)"
        >
          {{ group.title }}
        </button>
      </nav>
    </div>

    <section
      v-for="group in groups"
      :id="`lead-section-${group.key}`"
      :key="group.key"
      class="flex scroll-mt-24 flex-col gap-4 rounded-xl border border-app-border bg-app-panel p-6 shadow-sm"
    >
      <h2 class="text-p-lg font-medium text-app-text">{{ group.title }}</h2>

      <div v-if="group.fields.length" class="grid grid-cols-1 items-start gap-x-6 gap-y-5 sm:grid-cols-2">
        <div v-for="field in group.fields" :key="field.fieldname" :class="isWide(field) ? 'col-span-full' : ''">
          <FieldControl
            :field="field"
            v-model="form.values[field.fieldname]"
            :disabled="locked || !form.canWrite.value || field.read_only"
            :show-errors="triedSave"
            :remove-file="removeFile"
          />
        </div>
      </div>

      <ChildTableField
        v-for="table in group.tables"
        :key="table.fieldname"
        :table="table"
        :rows="form.values[table.fieldname] || []"
        :disabled="locked || !form.canWrite.value || table.read_only"
        @update:rows="(rows) => (form.values[table.fieldname] = rows)"
      />
    </section>
  </div>
</template>

<script setup>
// The Lead's candidate profile (its linked "Lead Detail Form"), grouped into
// the same sections the doctype lays out — Personal Information, Educational
// Details, Address History, Consent, ... — instead of one long flat grid.
// State lives in the page's useLeadDetailForm (passed in as `form`), so an
// unsaved edit survives switching tabs; this component only renders it.
import { computed } from 'vue'
import { call } from 'frappe-ui'
import FieldControl from '@/components/detail/FieldControl.vue'
import { confirmLeave } from '@/utils/common/confirmDialog'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'
import ChildTableField from '@/components/detail/ChildTableField.vue'

const props = defineProps({
  form: { type: Object, required: true }, // useLeadDetailForm()
  locked: { type: Boolean, default: false },
  triedSave: { type: Boolean, default: false },
})

const isWide = (field) => ['Small Text', 'Long Text', 'Text Editor'].includes(field.fieldtype)

const groups = computed(() => {
  const order = []
  const byTitle = new Map()
  const ensure = (title) => {
    const t = title || 'General'
    if (!byTitle.has(t)) {
      const group = { key: t.toLowerCase().replace(/[^a-z0-9]+/g, '-'), title: t, fields: [], tables: [] }
      byTitle.set(t, group)
      order.push(group)
    }
    return byTitle.get(t)
  }
  for (const f of props.form.fields.value) ensure(f.section).fields.push(f)
  for (const t of props.form.tables.value) ensure(t.section).tables.push(t)
  return order.filter((g) => g.fields.length || g.tables.length)
})

const completeness = computed(() => props.form.completeness.value)

function jump(key) {
  document.getElementById(`lead-section-${key}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// lead.js's .fg-remove-file: removing an uploaded file deletes it right away.
async function removeFile(fieldname) {
  const ok = await confirmLeave({ title: 'Remove this file?', message: 'The file is deleted from the candidate profile.', leaveLabel: 'Remove', cancelLabel: 'Keep' })
  if (!ok) return false
  try {
    const res = await call('verp_staffing.crm.doctype.lead.lead.remove_attachment', { docname: props.form.docname.value, fieldname })
    return res?.status === 'success'
  } catch (e) {
    notify.error(normalizeError(e).message)
    return false
  }
}
</script>

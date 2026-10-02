<template>
  <div class="flex h-full flex-col">
    <StateBanner
      v-if="timeline.hasError"
      icon="alert-triangle"
      title="Couldn't load activity"
      :description="timeline.errorMessage"
      class="m-6"
    />

    <template v-else>
      <!-- Scrollable feed: notes, field changes, tasks and events, newest first -->
      <div class="min-h-0 flex-1 overflow-y-auto px-3 md:px-6 py-5">
        <div v-if="allowCreate" class="mx-auto mb-5 flex max-w-2xl justify-end gap-2">
          <AppButton variant="outline" size="sm" icon="check-square" @click="openTaskDialog">Task</AppButton>
          <AppButton variant="outline" size="sm" icon="calendar" @click="openEventDialog">Event</AppButton>
        </div>

        <div v-if="timeline.isLoading && !timeline.resource.data" class="flex justify-center py-16">
          <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
        </div>

        <div v-else class="mx-auto max-w-2xl">
          <div class="flex flex-col">
            <div
              v-for="(entry, index) in entries"
              :key="entry.key"
              class="relative flex gap-3"
              :class="index !== entries.length - 1 ? 'pb-5' : ''"
            >
              <div class="flex flex-col items-center">
                <div
                  class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
                  :class="ICON_STYLES[entry.type].bg"
                >
                  <FeatherIcon :name="ICON_STYLES[entry.type].icon" class="h-4 w-4" :class="ICON_STYLES[entry.type].fg" />
                </div>
                <div v-if="index !== entries.length - 1" class="mt-1 w-px flex-1 bg-app-border" />
              </div>

              <div class="min-w-0 flex-1 pb-0.5 pt-1">
                <!-- Note -->
                <div
                  v-if="entry.type === 'note'"
                  class="rounded-xl border border-app-border bg-app-panel px-4 py-3 shadow-sm"
                >
                  <div class="flex items-baseline justify-between gap-2">
                    <span class="truncate text-p-sm font-medium text-app-text">
                      {{ entry.owner }}
                      <AppBadge v-if="entry.from_doctype" theme="gray" class="ml-1.5 align-middle">from {{ entry.from_doctype }}</AppBadge>
                    </span>
                    <span class="flex shrink-0 items-center gap-1 text-p-xs text-app-text-muted">
                      {{ formatDate(entry.creation) }}
                      <template v-if="entry.can_edit && entry.id">
                        <AppButton variant="ghost" size="icon" icon="edit-2" title="Edit note" @click="openNoteEdit(entry)" />
                        <AppButton variant="ghost" size="icon" icon="trash-2" title="Delete note" @click="removeNote(entry)" />
                      </template>
                    </span>
                  </div>
                  <div class="note-html mt-1 text-p-sm text-app-text" v-html="clean(entry.html)" />
                </div>

                <!-- Field-change history -->
                <div v-else-if="entry.type === 'update'" class="pt-0.5 text-p-sm">
                  <p>
                    <span class="font-medium text-app-text">{{ entry.owner }}</span>
                    <span class="text-app-text-muted"> updated this </span>
                    <span class="text-app-text-muted">· {{ formatDate(entry.creation) }}</span>
                  </p>
                  <ul v-if="entry.changes.length" class="mt-1.5 flex flex-col gap-1">
                    <li v-for="change in entry.changes" :key="change.fieldname" class="text-p-xs text-app-text-muted">
                      <span class="font-medium text-app-text">{{ change.fieldname }}</span>
                      <span> changed from </span>
                      <span class="italic">{{ display(change.old) }}</span>
                      <span> to </span>
                      <span class="italic text-app-text">{{ display(change.new) }}</span>
                    </li>
                  </ul>
                  <p v-else-if="entry.row_changed" class="mt-1.5 text-p-xs text-app-text-muted">
                    Updated a row in a table field.
                  </p>
                </div>

                <!-- Task (CRM Task) -->
                <div
                  v-else-if="entry.type === 'task'"
                  class="rounded-xl border border-app-border bg-app-panel px-4 py-3 shadow-sm"
                >
                  <div class="flex items-start justify-between gap-2">
                    <AppCheckbox class="min-w-0 !items-start" :model-value="Boolean(entry.is_completed)" :disabled="!entry.can_edit || changing" @update:model-value="(v) => toggleTask(entry, v)">
                      <span :class="entry.is_completed ? 'line-through opacity-60' : ''">
                        <span class="font-medium">Task</span>
                        <span v-if="entry.description"> · {{ entry.description }}</span>
                      </span>
                    </AppCheckbox>
                    <span class="flex shrink-0 items-center gap-1">
                      <AppBadge :theme="entry.is_completed ? 'green' : 'orange'">
                        {{ entry.is_completed ? 'Completed' : 'Open' }}
                      </AppBadge>
                      <template v-if="entry.can_edit && !entry.is_completed">
                        <AppButton variant="ghost" size="icon" icon="edit-2" title="Edit task" @click="openTaskEdit(entry)" />
                      </template>
                      <AppButton v-if="entry.can_delete && !entry.is_completed" variant="ghost" size="icon" icon="trash-2" title="Delete task" @click="removeActivity('CRM Task', entry, 'task')" />
                    </span>
                  </div>
                  <p class="mt-1 text-p-xs text-app-text-muted">
                    <span v-if="entry.assigned_to">Assigned to {{ entry.assigned_to }} · </span>
                    <span v-if="entry.date">Due {{ formatDate(entry.date) }}</span>
                  </p>
                </div>

                <!-- Event (CRM Event) -->
                <div
                  v-else-if="entry.type === 'event'"
                  class="rounded-xl border border-app-border bg-app-panel px-4 py-3 shadow-sm"
                >
                  <div class="flex items-start justify-between gap-2">
                    <p class="min-w-0 truncate text-p-sm font-medium text-app-text">{{ entry.summary }}</p>
                    <span class="flex shrink-0 items-center gap-1">
                      <AppBadge theme="blue">{{ entry.category }}</AppBadge>
                      <AppButton v-if="entry.can_edit" variant="ghost" size="icon" icon="edit-2" title="Edit event" @click="openEventEdit(entry)" />
                      <AppButton v-if="entry.can_delete" variant="ghost" size="icon" icon="trash-2" title="Delete event" @click="removeActivity('CRM Event', entry, 'event')" />
                    </span>
                  </div>
                  <p v-if="entry.description" class="mt-1 whitespace-pre-wrap text-p-sm text-app-text">
                    {{ entry.description }}
                  </p>
                  <p class="mt-1 text-p-xs text-app-text-muted">
                    <span v-if="entry.assigned_to">Assigned to {{ entry.assigned_to }} · </span>
                    {{ formatDate(entry.date) }}
                  </p>
                </div>
              </div>
            </div>

            <div v-if="!entries.length" class="flex flex-col items-center gap-2 py-14 text-center">
              <FeatherIcon name="activity" class="h-6 w-6 text-app-text-muted" />
              <p class="text-p-sm text-app-text-muted">{{ emptyText }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Composer docked to the bottom of the tab, not the page -->
      <div v-if="showComposer" class="shrink-0 border-t border-app-border bg-app-panel-2 px-3 md:px-6 py-4">
        <div class="mx-auto flex max-w-2xl gap-3">
          <Avatar :label="currentUserLabel" size="md" class="mt-0.5 shrink-0" />
          <div
            class="flex-1 rounded-xl border border-app-border bg-app-panel transition-colors focus-within:border-app-primary"
          >
            <AppTextarea
              ref="textareaRef"
              v-model="draft"
              bare
              :rows="1"
              placeholder="Add a note…"
              class="px-3 pt-2.5"
              @input="autoGrow"
              @keydown.meta.enter="onAdd"
              @keydown.ctrl.enter="onAdd"
            />
            <div class="flex items-center justify-end gap-2 px-3 pb-2 pt-1">
              <span class="text-p-xs text-app-text-muted">⌘/Ctrl + Enter</span>
              <AppButton size="sm" icon="send" :disabled="!draft.trim()" :loading="adding" @click="onAdd">
                Add note
              </AppButton>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Edit note: the desk form's rich-text editor, so HTML notes stay intact -->
    <Dialog v-model="showNoteEdit" :options="{ title: 'Edit note', size: 'lg' }">
      <template #body-content>
        <TextEditor
          :content="noteEdit.html"
          editor-class="min-h-[140px] rounded-lg border border-app-border px-3 py-2 text-p-sm"
          @change="(html) => (noteEdit.html = html)"
        />
      </template>
      <template #actions>
        <AppButton icon="check" :loading="changing" @click="saveNote">Update</AppButton>
      </template>
    </Dialog>

    <!-- Edit task: only an admin can move the date, reassign or reword it; the
    assignee can tick it off (CRM Task.validate enforces the same) -->
    <Dialog v-model="showTaskEdit" :options="{ title: 'Edit task', size: 'md' }">
      <template #body-content>
        <div class="flex flex-col gap-4">
          <AppInput type="textarea" label="Description" v-model="taskEdit.description" :disabled="!isSystemManager()" />
          <AppInput type="datetime-local" label="Date & Time" v-model="taskEdit.date" :disabled="!isSystemManager()" />
          <AppLinkField label="Assigned To" doctype="User" :filters="{ user_type: 'System User' }" v-model="taskEdit.assignedTo" :disabled="!isSystemManager()" />
          <AppCheckbox v-model="taskEdit.isCompleted" label="Completed" />
        </div>
      </template>
      <template #actions>
        <AppButton icon="check" :loading="changing" @click="saveTask">Update</AppButton>
      </template>
    </Dialog>

    <Dialog v-model="showEventEdit" :options="{ title: 'Edit event', size: 'md' }">
      <template #body-content>
        <div class="flex flex-col gap-4">
          <AppCombobox label="Category" required v-model="eventEdit.category" :options="EVENT_CATEGORIES" />
          <AppInput type="datetime-local" label="Date & Time" required v-model="eventEdit.date" />
          <AppInput type="text" label="Summary" required v-model="eventEdit.summary" />
          <AppInput type="textarea" label="Description" v-model="eventEdit.description" />
          <AppLinkField label="Assigned To" doctype="User" :filters="{ user_type: 'System User' }" v-model="eventEdit.assignedTo" />
        </div>
      </template>
      <template #actions>
        <AppButton icon="check" :loading="changing" :disabled="!eventEdit.category || !eventEdit.summary.trim()" @click="saveEvent">Update</AppButton>
      </template>
    </Dialog>

    <!-- New Task: same fields/order as this app's desk "Add Task" - description,
    then date & time (defaulted to now), then assigned to -->
    <Dialog v-model="showTaskDialog" :options="{ title: 'New Task', size: 'md' }">
      <template #body-content>
        <div class="flex flex-col gap-4">
          <AppInput type="textarea" label="Description" v-model="taskForm.description" />
          <AppInput type="datetime-local" label="Date & Time" v-model="taskForm.date" />
          <AppLinkField label="Assigned To" doctype="User" :filters="{ user_type: 'System User' }" v-model="taskForm.assignedTo" />
        </div>
      </template>
      <template #actions>
        <AppButton icon="check-square" :loading="creatingTask" @click="onCreateTask">Create Task</AppButton>
      </template>
    </Dialog>

    <!-- New Event: same fields/order as this app's desk "Add Event" - category,
    then date & time (defaulted to now), then summary, description, assigned to.
    Required fields (category, date, summary) carry the same red asterisk. -->
    <Dialog v-model="showEventDialog" :options="{ title: 'New Event', size: 'md' }">
      <template #body-content>
        <div class="flex flex-col gap-4">
          <AppCombobox label="Category" required v-model="eventForm.category" :options="EVENT_CATEGORIES" />
          <AppInput type="datetime-local" label="Date & Time" required v-model="eventForm.date" />
          <AppInput type="text" label="Summary" required v-model="eventForm.summary" />
          <AppInput type="textarea" label="Description" v-model="eventForm.description" />
          <AppLinkField label="Assigned To" doctype="User" :filters="{ user_type: 'System User' }" v-model="eventForm.assignedTo" />
        </div>
      </template>
      <template #actions>
        <AppButton
          icon="calendar"
          :loading="creatingEvent"
          :disabled="!eventForm.category || !eventForm.date || !eventForm.summary.trim()"
          @click="onCreateEvent"
        >
          Create Event
        </AppButton>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import AppTextarea from '@/components/ui/AppTextarea.vue'
import { siteNowIso } from '@/utils/common/siteTime'
import AppBadge from '@/components/ui/AppBadge.vue'
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
import AppInput from '@/components/ui/AppInput.vue'
import { computed, nextTick, reactive, ref } from 'vue'
import DOMPurify from 'dompurify'
import { Avatar, Dialog, FeatherIcon, LoadingIndicator, TextEditor } from 'frappe-ui'
import AppCombobox from '@/components/ui/AppCombobox.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { useTimeline } from '@/composables/detail/useTimeline'
import { confirmLeave } from '@/utils/common/confirmDialog'
import { isSystemManager } from '@/utils/common/roles'

const props = defineProps({
  doctype: { type: String, required: true },
  name: { type: String, required: true },
  // Which entry types this instance renders - lets Notes (notes + edit
  // history, with the composer) and Activity (tasks + events, read-only,
  // but with "New Task"/"New Event" creation) reuse the same feed/timeline
  // UI instead of duplicating it.
  types: { type: Array, required: true },
  showComposer: { type: Boolean, default: false },
  allowCreate: { type: Boolean, default: false },
  emptyText: { type: String, default: 'Nothing here yet.' },
})

const currentUserLabel = window.user || ''

const {
  timeline,
  entries: allEntries,
  addNote,
  adding,
  createTask,
  creatingTask,
  createEvent,
  creatingEvent,
  updateNote,
  deleteNote,
  updateTask,
  updateEvent,
  deleteActivity,
  changing,
} = useTimeline(
  computed(() => props.doctype),
  computed(() => props.name),
)

const entries = computed(() => allEntries.value.filter((entry) => props.types.includes(entry.type)))

const ICON_STYLES = {
  note: { icon: 'message-square', bg: 'bg-app-primary-tint', fg: 'text-app-primary' },
  update: { icon: 'edit-2', bg: 'bg-app-panel-2', fg: 'text-app-text-muted' },
  task: { icon: 'check-square', bg: 'bg-amber-500/15', fg: 'text-amber-500' },
  event: { icon: 'calendar', bg: 'bg-emerald-500/15', fg: 'text-emerald-500' },
}

const EVENT_CATEGORIES = ['Event', 'Meeting', 'Call', 'Follow Up', 'Other']

// datetime-local needs "YYYY-MM-DDTHH:mm" in local time - this is how the
// dialogs default Date & Time to "now", the way CRM Task/CRM Event's own
// before_insert() does server-side when the field is left blank.
function nowForInput() {
  return siteNowIso().slice(0, 16).replace(' ', 'T')
}

const draft = ref('')
const textareaRef = ref(null)

function onAdd() {
  if (!draft.value.trim()) return
  addNote(draft.value)
  draft.value = ''
  nextTick(() => {
    if (textareaRef.value?.el) textareaRef.value.el.style.height = 'auto'
  })
}

function autoGrow(e) {
  const el = e.target
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}

function display(value) {
  if (value === null || value === undefined || value === '') return '-'
  return String(value)
}

function formatDate(value, dateOnly = false) {
  if (!value) return ''
  const date = new Date(value)
  return dateOnly ? date.toLocaleDateString() : date.toLocaleString()
}

const showTaskDialog = ref(false)
const taskForm = reactive({ description: '', date: '', assignedTo: '' })

function openTaskDialog() {
  taskForm.description = ''
  taskForm.date = nowForInput()
  taskForm.assignedTo = ''
  showTaskDialog.value = true
}

async function onCreateTask() {
  const result = await createTask({
    description: taskForm.description || undefined,
    date: taskForm.date || undefined,
    assigned_to: taskForm.assignedTo || undefined,
  })
  if (result) showTaskDialog.value = false
}

// ── existing entries: edit / complete / delete ──────────────────────────────
// Notes are HTML written in the desk's editor; strip anything unsafe first.
const clean = (html) => DOMPurify.sanitize(html || '')

const inputDate = (value) => (value ? String(value).replace(' ', 'T').slice(0, 16) : '')

async function confirmDelete(what) {
  return confirmLeave({ title: `Delete this ${what}?`, message: "This can't be undone.", leaveLabel: 'Delete', cancelLabel: 'Cancel' })
}

const showNoteEdit = ref(false)
const noteEdit = reactive({ id: '', html: '' })
function openNoteEdit(entry) {
  Object.assign(noteEdit, { id: entry.id, html: entry.html })
  showNoteEdit.value = true
}
async function saveNote() {
  if (!noteEdit.html?.replace(/<[^>]*>/g, '').trim()) return
  if (await updateNote(noteEdit.id, noteEdit.html)) showNoteEdit.value = false
}
async function removeNote(entry) {
  if (await confirmDelete('note')) deleteNote(entry.id)
}

const showTaskEdit = ref(false)
const taskEdit = reactive({ id: '', description: '', date: '', assignedTo: '', isCompleted: false })
function openTaskEdit(entry) {
  Object.assign(taskEdit, { id: entry.id, description: entry.description || '', date: inputDate(entry.date), assignedTo: entry.assigned_to || '', isCompleted: !!entry.is_completed })
  showTaskEdit.value = true
}
async function saveTask() {
  const values = { is_completed: taskEdit.isCompleted ? 1 : 0 }
  if (isSystemManager()) Object.assign(values, { description: taskEdit.description, date: taskEdit.date, assigned_to: taskEdit.assignedTo })
  if (await updateTask(taskEdit.id, values)) showTaskEdit.value = false
}
function toggleTask(entry, done) {
  updateTask(entry.id, { is_completed: done ? 1 : 0 })
}

const showEventEdit = ref(false)
const eventEdit = reactive({ id: '', category: '', date: '', summary: '', description: '', assignedTo: '' })
function openEventEdit(entry) {
  Object.assign(eventEdit, { id: entry.id, category: entry.category || '', date: inputDate(entry.date), summary: entry.summary || '', description: entry.description || '', assignedTo: entry.assigned_to || '' })
  showEventEdit.value = true
}
async function saveEvent() {
  const done = await updateEvent(eventEdit.id, {
    category: eventEdit.category,
    date: eventEdit.date,
    summary: eventEdit.summary.trim(),
    description: eventEdit.description,
    assigned_to: eventEdit.assignedTo,
  })
  if (done) showEventEdit.value = false
}

async function removeActivity(activityDoctype, entry, what) {
  if (await confirmDelete(what)) deleteActivity(activityDoctype, entry.id)
}

const showEventDialog = ref(false)
const eventForm = reactive({ category: '', date: '', summary: '', description: '', assignedTo: '' })

function openEventDialog() {
  eventForm.category = ''
  eventForm.date = nowForInput()
  eventForm.summary = ''
  eventForm.description = ''
  eventForm.assignedTo = ''
  showEventDialog.value = true
}

async function onCreateEvent() {
  if (!eventForm.category || !eventForm.date || !eventForm.summary.trim()) return
  const result = await createEvent({
    category: eventForm.category,
    date: eventForm.date,
    summary: eventForm.summary.trim(),
    description: eventForm.description || undefined,
    assigned_to: eventForm.assignedTo || undefined,
  })
  if (result) showEventDialog.value = false
}
</script>

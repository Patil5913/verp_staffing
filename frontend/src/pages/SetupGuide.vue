<template>
  <div class="mx-auto flex max-w-3xl flex-col gap-4 px-6 py-8">
    <StateBanner
      v-if="progress.hasError"
      icon="alert-triangle"
      title="Couldn't load setup progress"
      :description="progress.errorMessage"
    />
    <div v-else-if="progress.isLoading && !progress.resource.data" class="flex justify-center py-16">
      <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
    </div>

    <template v-else-if="data">
      <!-- Completed state -->
      <div
        v-if="data.is_completed"
        class="flex flex-col items-center gap-3 rounded-2xl border border-app-border bg-app-panel px-8 py-12 text-center"
      >
        <span class="lucide-party-popper size-10 text-app-primary" />
        <h1 class="text-xl font-semibold text-app-text">Setup Complete</h1>
        <p class="max-w-sm text-p-base text-app-text-muted">
          Your organization is fully configured and ready for daily operations.
        </p>
        <div class="mt-2 flex gap-2">
          <Button variant="solid" @click="router.push('/')">Go to Dashboard</Button>
          <Button variant="outline" :loading="hide.loading" @click="hide.resource.submit()">
            Hide Setup Workspace
          </Button>
        </div>
      </div>

      <!-- In-progress state -->
      <template v-else>
        <div class="rounded-2xl border border-app-border bg-app-panel px-8 py-8">
          <div class="mb-5 flex items-start justify-between gap-4">
            <div>
              <div class="text-p-sm font-semibold text-app-primary">Staffing ERP Setup</div>
              <h1 class="text-2xl font-semibold text-app-text">Setup Progress</h1>
              <p class="mt-1 text-p-sm text-app-text-muted">
                {{ data.completed_steps }} of {{ data.total_steps }} steps completed
              </p>
            </div>
            <div class="shrink-0 rounded-full border border-app-border bg-app-panel-2 px-3 py-1.5 text-p-sm font-semibold text-app-primary">
              {{ data.progress_percentage }}% Complete
            </div>
          </div>

          <div class="mb-6 h-2.5 w-full overflow-hidden rounded-full bg-app-panel-2">
            <div
              class="h-full rounded-full bg-app-primary transition-all duration-700"
              :style="{ width: data.progress_percentage + '%' }"
            />
          </div>

          <div class="mb-6 flex flex-col gap-1">
            <span class="text-p-sm text-app-text-muted">Current Step</span>
            <strong class="text-p-base font-semibold text-app-text">{{ data.current_step_label }}</strong>
          </div>

          <div class="flex flex-wrap gap-2">
            <Button variant="solid" @click="continueSetup">Continue Setup →</Button>
            <Button variant="outline" @click="progress.resource.reload()">Refresh</Button>
          </div>
        </div>

        <div class="rounded-2xl border border-app-border bg-app-panel px-8 py-6">
          <div class="mb-1 text-lg font-semibold text-app-text">Setup Journey</div>
          <div class="mb-4 text-p-sm text-app-text-muted">Complete each step to finish onboarding</div>

          <div class="flex flex-col">
            <div
              v-for="step in STEPS"
              :key="step.key"
              class="flex items-center gap-4 py-3"
              :class="{ 'rounded-xl border-l-4 border-app-primary bg-app-panel-2 px-3 -mx-3': step.key === data.current_step }"
            >
              <div
                class="flex size-9 shrink-0 items-center justify-center rounded-full text-base"
                :class="stepIconClass(step.key)"
              >
                <span v-if="data.steps[step.key]" class="lucide-check size-4" />
                <span v-else>{{ step.icon }}</span>
              </div>
              <div class="min-w-0 flex-1">
                <div class="text-p-base font-medium text-app-text">{{ step.label }}</div>
                <div class="text-p-sm text-app-text-muted">{{ step.desc }}</div>
              </div>
              <Badge :theme="stepBadgeTheme(step.key)" :label="stepBadgeLabel(step.key)" />
            </div>
          </div>
        </div>

        <div class="flex justify-end">
          <Button variant="ghost" :loading="hide.loading" @click="hide.resource.submit()">
            Hide Setup Workspace
          </Button>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, Button, LoadingIndicator } from 'frappe-ui'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'
import StateBanner from '@/components/common/StateBanner.vue'

const router = useRouter()

const STEPS = [
  { key: 'department', label: 'Department Structure', desc: "Define your organization's department hierarchy and reporting units.", icon: '🏢' },
  { key: 'hierarchy', label: 'Reporting Hierarchy', desc: 'Map out who reports to whom across your staffing network.', icon: '🔗' },
  { key: 'employee', label: 'Employee Setup', desc: 'Import or create employee records and assign them to departments.', icon: '👤' },
  { key: 'erp_configuration', label: 'ERP Configuration', desc: 'Configure core ERP settings for payroll, attendance, and compliance.', icon: '⚙️' },
  { key: 'pdf_agreement_template', label: 'Agreement Templates', desc: 'Upload offer letter and employment agreement PDF templates.', icon: '📄' },
]

// Next-action routes from the backend are classic desk create-new-doc URLs
// (e.g. "/app/employee/new") — this pass only ports list views, not a
// generic create form, so "Continue Setup" lands on the corresponding list
// instead of a blank new-record form.
const NEXT_ACTION_LIST_ROUTE = {
  employee: '/list/Employee',
  erp_configuration: '/settings/ERP%20Configuration',
  pdf_agreement_template: '/list/Pdf%20Agreement%20Template',
}

const progress = useResource({
  url: 'verp_staffing.utils.onboarding_setup_helper.get_setup_progress',
  auto: true,
})
const data = computed(() => progress.resource.data)

const hide = useResource({
  url: 'verp_staffing.utils.onboarding_setup_helper.hide_setup_workspace',
  onSuccess() {
    notify.success('Setup Workspace hidden successfully.')
  },
})

function stepIconClass(key) {
  if (data.value.steps[key]) return 'bg-green-100 text-green-700'
  if (key === data.value.current_step) return 'bg-app-primary text-white'
  return 'bg-app-panel-2 text-app-text-muted'
}

function stepBadgeTheme(key) {
  if (data.value.steps[key]) return 'green'
  if (key === data.value.current_step) return 'blue'
  return 'gray'
}

function stepBadgeLabel(key) {
  if (data.value.steps[key]) return 'Done'
  if (key === data.value.current_step) return 'In progress'
  return 'Pending'
}

function continueSetup() {
  const route = NEXT_ACTION_LIST_ROUTE[data.value.current_step]
  if (route) router.push(route)
}
</script>

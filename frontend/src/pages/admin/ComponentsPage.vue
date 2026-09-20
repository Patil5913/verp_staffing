<template>
  <div class="mx-auto flex max-w-6xl gap-8 px-3 md:px-6 py-8">
    <nav class="sticky top-6 hidden h-fit w-48 shrink-0 flex-col gap-0.5 lg:flex">
      <input v-model="q" placeholder="Filter…" class="mb-2 h-8 rounded-md border border-app-border bg-app-panel px-2 text-p-sm text-app-text outline-none focus:border-app-primary" />
      <a
        v-for="t in filteredToc"
        :key="t.id"
        :href="`#${t.id}`"
        class="rounded-md px-2 py-1 text-p-sm text-app-text-muted hover:bg-app-panel-2 hover:text-app-text"
        @click.prevent="scrollTo(t.id)"
      >{{ t.title }}</a>
    </nav>
    <div class="flex min-w-0 flex-1 flex-col gap-8">
    <header>
      <h1 class="text-p-xl font-semibold text-app-text">Components</h1>
      <p class="text-p-sm text-app-text-muted">Every reusable building block of this app, live. Shared primitives are in <code>components/ui</code> and <code>components/common</code>.</p>
    </header>

    <ComponentSection id="buttons" title="Buttons" source="components/common/AppButton.vue">
      <div class="flex flex-wrap items-center gap-3">
        <AppButton>Primary</AppButton>
        <AppButton variant="outline">Outline</AppButton>
        <AppButton variant="ghost">Ghost</AppButton>
        <AppButton variant="danger">Danger</AppButton>
        <AppButton size="sm" icon="plus">Small + icon</AppButton>
        <AppButton size="icon" icon="trash-2" variant="outline" />
        <AppButton loading>Loading</AppButton>
        <AppButton disabled>Disabled</AppButton>
      </div>
    </ComponentSection>

    <ComponentSection id="text-inputs" title="Text inputs" source="components/ui/AppInput.vue · AppTextarea.vue">
      <div class="grid gap-4 sm:grid-cols-2">
        <AppInput v-model="text" label="Name" placeholder="Enter a name" required />
        <AppInput v-model="text" label="With hint" hint="Helper text goes here" />
        <AppInput v-model="empty" label="With error" error="This field is required" />
        <AppInput model-value="Read only" label="Disabled" disabled />
        <AppInput v-model="empty" label="Date" type="date" />
        <AppTextarea v-model="long" label="Description" placeholder="Longer text" />
      </div>
    </ComponentSection>

    <ComponentSection id="date-picker" title="Date picker" source="components/ui/AppDatePicker.vue">
      <div class="grid gap-4 sm:grid-cols-3">
        <AppDatePicker v-model="date" label="Date" />
        <AppDatePicker v-model="dateTime" mode="datetime" label="Date & time" />
        <AppDatePicker v-model="dateRange" mode="range" label="Date range" />
      </div>
    </ComponentSection>

    <ComponentSection id="search-input" title="Search input" source="components/ui/AppSearchInput.vue">
      <div class="flex max-w-md flex-col gap-3">
        <AppSearchInput v-model="searchText" placeholder="Search…" />
        <AppSearchInput v-model="searchText" compact placeholder="Compact" />
      </div>
    </ComponentSection>

    <ComponentSection id="checkbox" title="Checkbox" source="components/ui/AppCheckbox.vue">
      <div class="flex gap-6">
        <AppCheckbox v-model="checked" label="Enabled" />
        <AppCheckbox :model-value="false" label="Unchecked" />
        <AppCheckbox :model-value="false" indeterminate label="Some selected" />
        <AppCheckbox :model-value="true" label="Disabled" disabled />
      </div>
    </ComponentSection>

    <ComponentSection id="combobox-fixed-options" title="Combobox (fixed options)" source="components/common/AppCombobox.vue">
      <div class="grid gap-4 sm:grid-cols-2">
        <AppCombobox v-model="choice" label="Status" :options="['Open', 'Replied', 'Closed']" />
        <AppCombobox v-model="choice" label="Compact" :options="['Open', 'Replied', 'Closed']" compact />
      </div>
    </ComponentSection>

    <ComponentSection id="link-field-server-search" title="Link field (server search)" source="components/common/AppLinkField.vue">
      <div class="max-w-sm"><AppLinkField v-model="link" doctype="User" label="User" hide-add-new /></div>
    </ComponentSection>

    <ComponentSection id="badges" title="Badges" source="components/common/DocStatusBadge.vue">
      <div class="flex flex-wrap gap-2">
        <DocStatusBadge :docstatus="0" />
        <DocStatusBadge :docstatus="1" />
        <DocStatusBadge :docstatus="2" />
        <DocStatusBadge status="Open" />
        <DocStatusBadge status="Paid" />
        <DocStatusBadge status="Overdue" />
      </div>
    </ComponentSection>

    <ComponentSection id="tags" title="Tags" source="components/ui/AppBadge.vue">
      <div class="flex flex-wrap gap-2">
        <AppBadge label="Gray" />
        <AppBadge theme="blue" label="Blue" />
        <AppBadge theme="green" label="Green" />
        <AppBadge theme="orange" label="Orange" />
        <AppBadge theme="red" label="Red" size="md" />
      </div>
    </ComponentSection>

    <ComponentSection id="tabs" title="Tabs" source="components/ui/AppTabs.vue">
      <AppTabs v-model="tab" :tabs="['Details', 'Activity', 'Connections']" />
      <p class="pt-3 text-p-sm text-app-text-muted">Selected: {{ tab }}</p>
    </ComponentSection>

    <ComponentSection id="view-switcher" title="View switcher" source="components/common/ViewSwitcher.vue">
      <ViewSwitcher doctype="Account" current="list" />
    </ComponentSection>

    <ComponentSection id="table" title="Table" source="components/ui/AppTable.vue">
      <AppTable :columns="tableColumns" :rows="tableRows">
        <template #cell-status="{ value }"><DocStatusBadge :status="value" /></template>
      </AppTable>
    </ComponentSection>

    <ComponentSection id="child-table-inline-editable" title="Child table (inline editable)" source="components/ui/AppChildTable.vue">
      <AppChildTable v-model="items" :columns="childColumns" />
    </ComponentSection>

    <ComponentSection id="section-card" title="Section card" source="components/common/SectionCard.vue">
      <SectionCard title="Card title" subtitle="Optional subtitle">
        <template #actions><AppButton size="sm" variant="outline">Action</AppButton></template>
        <p class="text-p-sm text-app-text-muted">Panel content.</p>
      </SectionCard>
    </ComponentSection>

    <ComponentSection id="banners" title="Banners" source="components/common/NoticeBanner.vue · StateBanner.vue">
      <div class="flex flex-col gap-3">
        <NoticeBanner tone="info" message="Informational notice." />
        <NoticeBanner tone="warning" message="Warning before a permanent action." />
        <NoticeBanner tone="danger" message="Something went wrong." />
        <StateBanner icon="inbox" title="Nothing here yet" description="Empty-state placeholder." />
      </div>
    </ComponentSection>

    <ComponentSection id="loading-placeholders" title="Loading placeholders" source="components/ui/AppSkeleton.vue">
      <div class="grid gap-4 sm:grid-cols-3">
        <AppSkeleton :lines="4" />
        <AppSkeleton variant="avatar" />
        <AppSkeleton variant="block" />
      </div>
    </ComponentSection>

    <ComponentSection id="overlays" title="Overlays" source="frappe-ui Dialog · Dropdown · Avatar">
      <div class="flex flex-wrap items-center gap-4">
        <AppButton variant="outline" @click="dialogOpen = true">Open dialog</AppButton>
        <Dropdown :options="menuOptions">
          <template #default="{ open }">
            <AppButton variant="outline" :icon="open ? 'chevron-up' : 'chevron-down'">Dropdown</AppButton>
          </template>
        </Dropdown>
        <Avatar label="Parth Rugle" size="lg" />
        <Avatar label="Verp Staffing" size="md" />
      </div>
      <Dialog v-model="dialogOpen" :options="{ title: 'Example dialog', size: 'md' }">
        <template #body-content>
          <p class="text-p-sm text-app-text-muted">Dialog content goes here.</p>
        </template>
        <template #actions>
          <AppButton @click="dialogOpen = false">Done</AppButton>
        </template>
      </Dialog>
    </ComponentSection>

    <ComponentSection id="pagination" title="Pagination" source="components/list/Pagination.vue">
      <Pagination v-model:page="page" :page-count="5" />
    </ComponentSection>

    <ComponentSection id="theme-toggle" title="Theme toggle" source="components/common/ThemeToggle.vue">
      <ThemeToggle />
    </ComponentSection>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Avatar, Dialog, Dropdown } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import NoticeBanner from '@/components/common/NoticeBanner.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import ThemeToggle from '@/components/common/ThemeToggle.vue'
import ViewSwitcher from '@/components/common/ViewSwitcher.vue'
import Pagination from '@/components/list/Pagination.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppTextarea from '@/components/ui/AppTextarea.vue'
import AppSearchInput from '@/components/ui/AppSearchInput.vue'
import AppBadge from '@/components/ui/AppBadge.vue'
import AppDatePicker from '@/components/ui/AppDatePicker.vue'
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
import AppTabs from '@/components/ui/AppTabs.vue'
import AppTable from '@/components/ui/AppTable.vue'
import AppChildTable from '@/components/ui/AppChildTable.vue'
import AppSkeleton from '@/components/ui/AppSkeleton.vue'
import ComponentSection from '@/components/ui/ComponentSection.vue'

const toc = [
  { id: 'buttons', title: 'Buttons' },
  { id: 'text-inputs', title: 'Text inputs' },
  { id: 'date-picker', title: 'Date picker' },
  { id: 'search-input', title: 'Search input' },
  { id: 'checkbox', title: 'Checkbox' },
  { id: 'combobox-fixed-options', title: 'Combobox (fixed options)' },
  { id: 'link-field-server-search', title: 'Link field (server search)' },
  { id: 'badges', title: 'Badges' },
  { id: 'tags', title: 'Tags' },
  { id: 'tabs', title: 'Tabs' },
  { id: 'view-switcher', title: 'View switcher' },
  { id: 'table', title: 'Table' },
  { id: 'child-table-inline-editable', title: 'Child table (inline editable)' },
  { id: 'section-card', title: 'Section card' },
  { id: 'banners', title: 'Banners' },
  { id: 'loading-placeholders', title: 'Loading placeholders' },
  { id: 'overlays', title: 'Overlays' },
  { id: 'pagination', title: 'Pagination' },
  { id: 'theme-toggle', title: 'Theme toggle' },
]
const q = ref('')
const filteredToc = computed(() => toc.filter((t) => t.title.toLowerCase().includes(q.value.toLowerCase())))
const scrollTo = (id) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })

const dialogOpen = ref(false)
const menuOptions = [
  { label: 'Edit', icon: 'edit', onClick: () => {} },
  { label: 'Duplicate', icon: 'copy', onClick: () => {} },
  { label: 'Delete', icon: 'trash-2', onClick: () => {} },
]
const searchText = ref('')
const date = ref('')
const dateTime = ref('')
const dateRange = ref('')
const text = ref('')
const empty = ref('')
const long = ref('')
const checked = ref(true)
const choice = ref('Open')
const link = ref('')
const tab = ref('Details')
const page = ref(1)

const tableColumns = [
  { key: 'name', label: 'Name' },
  { key: 'status', label: 'Status' },
  { key: 'amount', label: 'Amount', align: 'right' },
]
const tableRows = [
  { name: 'INV-0001', status: 'Paid', amount: '1,200.00' },
  { name: 'INV-0002', status: 'Overdue', amount: '480.00' },
  { name: 'INV-0003', status: 'Open', amount: '95.50' },
]

const childColumns = [
  { key: 'item', label: 'Item' },
  { key: 'qty', label: 'Qty', type: 'number' },
  { key: 'rate', label: 'Rate', type: 'number' },
]
const items = ref([
  { item: 'Consulting hours', qty: 10, rate: 75 },
  { item: 'Onboarding fee', qty: 1, rate: 250 },
])
</script>

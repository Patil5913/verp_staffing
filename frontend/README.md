# Verp Placements - Frontend

A Vue 3 single-page app (SPA) built with [frappe-ui](https://github.com/frappe/frappe-ui), Tailwind CSS and Vite. It is served by the Frappe backend at **`/verp`** and talks to it through whitelisted API methods and the standard `frappe.client` / resource endpoints.

- `npm run dev` - Vite dev server
- `npm run build` (`vite build`) - production build, written to `../verp_staffing/public/frontend`
- `npm run preview` - preview the production build

Run `vite build` after any frontend change.

---

## 1. Big picture

```
index.html ─► src/main.js ─► App.vue ─► layout (AppShell | BlankLayout) ─► <router-view>
                  │                                                              │
                  └─► router.js ──(lazy-loads)──► pages/**                       │
                                                    │                            │
                              components/**  ◄──────┤  composables/**  ──► utils/**
                                                    └─► configs/**  (per-doctype config)
```

Dependencies flow **one way, downwards**:

| Layer | May depend on |
|---|---|
| `pages/` | `components/`, `composables/`, `utils/`, `configs/` |
| `configs/` | `components/` (as slot/panel components), `utils/` |
| `components/` | other `components/` (mostly `ui/` and `common/`), `composables/`, `utils/` |
| `composables/` | other `composables/`, `utils/` |
| `utils/` | other `utils/` only (no Vue components) |

Imports use the `@` alias for `src/` (`@/components/ui/AppButton.vue`). Imports between files in the same folder use `./`.

### Key architectural ideas

1. **One generic engine, many doctypes.** Lists (`DocListView`), detail pages (`ConfigDetailPage` / `DocDetailPage`), trees, kanban and reports are doctype-agnostic. Doctype-specific behaviour is injected through **`configs/`** (extra panels, actions, hidden fields, tabs) rather than by writing a new page per doctype. Only doctypes with truly custom layouts get their own page in `pages/detail/`.
2. **Server-driven UI.** The sidebar, dashboards, report filters, permissions and route access all come from the server (`useSidebar`, `useDashboard`, `useReport`, `routeAccess`). The frontend only decides how to present them.
3. **All server calls go through `useResource`**, a thin wrapper over frappe-ui's `createResource` that normalises errors (`utils/common/errors.js`) and toasts (`utils/common/notify.js`).
4. **Components are auto-registered.** `unplugin-vue-components` (via `frappe-ui/vite`) scans `src/components/**`, so components are used in templates by name without import. Component file names must therefore be **unique across all folders**. `components.d.ts` and `auto-imports.d.ts` are generated and git-ignored.
5. **Theming** uses CSS variables (`--app-*`) in `src/index.css`, switched by `data-theme` on `<html>` (light / dark / system). Tailwind exposes them as `app-bg`, `app-panel`, `app-border`, `app-text`, `app-primary`, ….

---

## 2. Folder layout

```
frontend/
├── index.html               HTML shell; sets data-theme before first paint
├── vite.config.js           Vite + frappe-ui plugin, `@` alias, dev-site name, /verp base route
├── tailwind.config.js       frappe-ui preset, app colour tokens, icon safelist
├── postcss.config.js        Tailwind + autoprefixer
├── package.json             deps: vue, vue-router, frappe-ui, vuedraggable
├── public/                  static files copied as-is
└── src/
    ├── main.js              app bootstrap
    ├── App.vue              picks layout by route
    ├── router.js            routes, auth + access guards
    ├── index.css            theme variables + frappe-ui styles
    ├── layouts/             page chrome
    ├── pages/               route-level screens
    ├── components/          reusable UI, grouped by domain
    ├── composables/         stateful logic (Vue reactivity + server calls)
    ├── configs/             per-doctype / per-report configuration
    └── utils/               pure helpers
```

---

## 3. Root files

| File | What it does | Depends on |
|---|---|---|
| `index.html` | HTML entry. Inline script reads `localStorage['verp-theme']` and sets `data-theme` on `<html>` before first paint (avoids a theme flash). Loads `/src/main.js`. | `composables/common/useTheme.js` (keeps the same key in sync) |
| `vite.config.js` | Vite config: `frappe-ui/vite` plugin (route `/verp`, lucide icons, component auto-import), Vue plugin, `@` → `src`, defines `__DEV_SITE_NAME__` from the bench's `common_site_config.json` (Socket.IO namespace in dev), works around frappe-ui prebundling issues. | `frappe-ui`, `@vitejs/plugin-vue` |
| `tailwind.config.js` | Uses the frappe-ui preset, defines `app-*` colour/typography tokens, and **safelists** icon classes built dynamically at runtime. | `utils/layout/sidebarIcons.js`, `utils/dashboard/icons.js` |
| `postcss.config.js` | Tailwind + autoprefixer. | - |
| `src/main.js` | Creates the Vue app, installs router and `FrappeUI`, sets frappe-ui's `resourceFetcher`, intercepts clicks on classic-desk links (`/app/...`) found in server messages and routes them to the SPA equivalent, mounts **after** `router.isReady()`. | `App.vue`, `router.js`, `utils/common/deskRoute.js` |
| `src/App.vue` | Renders `<BlankLayout>` for public routes (Login) and `<AppShell>` for everything else; mounts the global `UnsavedChangesDialog`. | `layouts/*`, `components/common/UnsavedChangesDialog.vue` |
| `src/router.js` | All routes (lazy-loaded pages), `/verp` history base, config-driven doctype routes, `beforeEach` guard: login check → server-side route access check → `Forbidden`. Last route is `NotFound`. | every page in `pages/`, `configs/detail/{marketing,customerCare,accounts,items,esign,emailQueue}`, `utils/common/routeAccess.js` |
| `src/index.css` | Imports frappe-ui styles; defines `--app-*` CSS variables for light and `[data-theme='dark']`. | `frappe-ui/style.css` |

---

## 4. `src/layouts/`

| File | What it does | Depends on |
|---|---|---|
| `AppShell.vue` | Logged-in chrome: sidebar header + sidebar on the left, navbar on top, page content in the middle. Loads the sidebar tree. | `layout/SidebarHeader`, `layout/AppNavbar`, `layout/AppSidebar`, `useSidebar` |
| `BlankLayout.vue` | Bare `<slot>` for public pages (Login). | - |

---

## 5. `src/pages/` - route-level screens

Each page is lazy-loaded from `router.js`. Pages should be thin: they compose components and composables.

### `pages/auth/`
| File | What it does | Depends on |
|---|---|---|
| `Login.vue` | Login form; honours the `redirect-to` query. | `AppInput`, `AppButton`, `notify` |
| `Home.vue` | Simple landing/redirect page. | `AppButton`, `notify` |
| `Forbidden.vue` | 403 screen shown by the router's access guard. | `AppButton`, `StateBanner` |
| `NotFound.vue` | 404 catch-all. | `AppButton`, `StateBanner` |

### `pages/dashboard/`
| File | What it does | Depends on |
|---|---|---|
| `DashboardPage.vue` | Analytics home; a tab per business area, each with KPIs, alerts, charts and tables. | `components/dashboard/*`, `useDashboard`, `utils/dashboard/format`, `StateBanner` |

### `pages/lists/` - collection views of a doctype
| File | What it does | Depends on |
|---|---|---|
| `DocListPage.vue` | Route wrapper: passes the `:doctype` param to `DocListView`. | `list/DocListView` |
| `KanbanPage.vue` | Kanban view of a doctype (Interview). | `list/KanbanBoard`, `ViewSwitcher`, `SubNavbar`, `useResource`, `configs/detail/listOptions`, `formatValue` |
| `TreePage.vue` | Generic tree view for tree doctypes (Company, Item Category…). | `tree/DocTreeView`, `SubNavbar`, `ViewSwitcher` |
| `AccountTreePage.vue` | Company-scoped Chart of Accounts with add/edit. | `tree/DocTreeView`, `SubNavbar`, `AppLinkField`, `useResource` |
| `InterviewCalendarPage.vue` | Month/week calendar of interview rounds. | `SubNavbar`, `ViewSwitcher`, `useResource` |

### `pages/detail/` - single-record screens
Most use `DetailPageLayout` + `DocDetailView` + `RecordActionBar` + `ActivityTimeline`, driven by `useDetailPageController`.

| File | What it does | Notable extra dependencies |
|---|---|---|
| `DocDetailPage.vue` | **Default** detail view for any doctype without its own page (route `/:doctype/:name`). | - |
| `ConfigDetailPage.vue` | **Config-driven** detail page. Reads a config from `configs/detail/*` (panels, actions, tabs, hidden fields) passed in through route meta. Used by many doctypes. | `ChildTableField`, `DocStatusBadge` |
| `LeadDetailPage.vue` | Lead: profile completeness, Lead Detail Form, create-opportunity dialog. | `lead/*`, `useLeadDetailForm`, `fieldFormats` |
| `CustomerDetailPage.vue` | Customer with history and field-update actions. | `FieldUpdateActions`, `useResource` |
| `OpportunityDetailPage.vue` | Opportunity tabs and actions. | `ChildTableField`, `roles` |
| `ResumeDetailPage.vue` | Resume (details / attachments / notes / activity). | `FieldUpdateActions` |
| `RucDetailPage.vue` | Resume Update Call sessions. | `FieldUpdateActions` |
| `JdcDetailPage.vue` | JDC interview session. | `FieldUpdateActions` |
| `CoverLetterDetailPage.vue` | Cover letter with proof of work. | `FieldUpdateActions` |
| `TrainingDetailPage.vue`, `InterviewSupportDetailPage.vue`, `TechnicalOtherServicesDetailPage.vue` | "Service record" pages - same shape: resume panel + forward candidate flow. | `ServiceResumePanel`, `ForwardCandidateButton`, `AppLinkField` |
| `OutsourceDetailPage.vue` | Outsource record; small curated field grid. | - |
| `EmployeeDetailPage.vue` | Employee: profile / assignments / LinkedIn / target tabs. | `ChildTableField`, `roles` |
| `DepartmentDetailPage.vue` | Department (generic tabs). | - |
| `RoleDetailPage.vue` | Role; single curated grid. | - |
| `UserDetailPage.vue` | User: profile / roles / email / general / security. | `user/UserRolesTab`, `user/UserChangePassword` |
| `EmailAccountDetailPage.vue`, `EmailDomainDetailPage.vue` | Email account / domain (generic tabs, role-aware). | `roles` |
| `HierarchyDetailPage.vue` | Role hierarchy editor with live diagram. | `hierarchy/HierarchyDiagram`, `useDocDetail`, `useUnsavedChangesGuard` |
| `PdfAgreementTemplateDetailPage.vue` | Template with the PDF field-placement builder. | `esign/PdfFieldBuilder`, `useDocDetail` |
| `ERPConfigurationDetailPage.vue` | ERP Configuration (Single doctype): email grid, field selector, website settings, sample data. | `erp/*`, `useSystemSettingsPanel` |

### `pages/reports/`
| File | What it does | Depends on |
|---|---|---|
| `ReportsHub.vue` | Lists every report the user may open, grouped by area. | `SubNavbar`, `AppSearchInput`, `useResource` |
| `ReportPage.vue` | Route wrapper; keyed by report name so filters reset when switching reports. | `report/ReportView` |

### `pages/mail/`
| File | What it does | Depends on |
|---|---|---|
| `EmailInbox.vue` | Inbox screen: folders, list, reader, compose; refreshes over Socket.IO. | `components/mail/*`, `useMailbox`, `utils/common/realtime`, `utils/mail/format` |

### `pages/notifications/`
| File | What it does | Depends on |
|---|---|---|
| `NotificationsPage.vue` | Full Notification Log ("See all Activity" from the bell). | `useNotifications`, `AppTabs`, `AppSkeleton` |

### `pages/admin/`
| File | What it does | Depends on |
|---|---|---|
| `PermissionManager.vue` | Role permission matrix editor. | `AppCheckbox`, `AppLinkField`, `useResource` |
| `PendingPERequests.vue` | Payment Verification queue (pending Payment Entry requests). | `SubNavbar`, `DocStatusBadge`, `useResource` |
| `SetupGuide.vue` | First-run setup checklist. | `AppBadge`, `useResource` |
| `SettingsFormPage.vue` | Generic form for a Single/settings doctype. | `AppInput`, `useResource` |
| `ComponentsPage.vue` | `/components` gallery of the shared UI components (dev reference). | all `ui/` and `common/` components, `ui/ComponentSection` |

---

## 6. `src/components/`

Grouped by **role**: `ui` = primitives, `common` = small app-wide building blocks, everything else = feature areas.

### `components/ui/` - design-system primitives (no business logic)
| File | What it does | Depends on |
|---|---|---|
| `AppButton.vue` | The app's button (pill; variants, sizes, loading, icons). | frappe-ui |
| `AppInput.vue` | Single control for text/number/date/select/etc. | `AppCombobox` |
| `AppTextarea.vue` | Multi-line input. | - |
| `AppCheckbox.vue` | Checkbox with check/dash states. | - |
| `AppCombobox.vue` | Themed select/combobox. | frappe-ui |
| `AppDatePicker.vue` | Date picker with month/year switcher. | frappe-ui |
| `AppSearchInput.vue` | Toolbar search box. | - |
| `AppBadge.vue` | Coloured status/tag pill. | - |
| `AppTabs.vue` | Tab strip (`{label,value}` or strings). | - |
| `AppTable.vue` | Read-only table with `cell-<key>` slots. | - |
| `AppChildTable.vue` | Inline-editable child table. | `AppButton` |
| `AppSkeleton.vue` | Loading placeholders. | - |
| `ScrollArea.vue` | Thin themed scrollbar wrapper. | - |
| `ComponentSection.vue` | One entry in the `/components` gallery. | - |

### `components/common/` - shared, slightly higher-level blocks
| File | What it does | Depends on |
|---|---|---|
| `AppLinkField.vue` | Link-field picker (search a doctype, quick-create). | `useResource`, `list/QuickCreateDialog` |
| `DocStatusBadge.vue` | Status pill beside a record title / in panels. | `AppBadge`, `utils/list/statusTheme` |
| `RecordActionBar.vue` | Action row of a detail page (record actions before Save/Delete). | `AppButton` |
| `SectionCard.vue` | Rounded panel wrapping every detail-page block. | - |
| `NoticeBanner.vue` | Inline notice inside a record (locked, warning…). | - |
| `StateBanner.vue` | Empty / error / forbidden placeholder (icon, title, description). | - |
| `SubNavbar.vue` | Thin bar under the navbar: title, search/filters, actions. | - |
| `ViewSwitcher.vue` | List / Tree / Kanban / Calendar toggle. | `configs/detail/listOptions`, vue-router |
| `ThemeToggle.vue` | System/light/dark switch. | `useTheme` |
| `UnsavedChangesDialog.vue` | Global "discard changes?" dialog. | `AppButton`, `utils/common/confirmDialog` |

### `components/layout/` - app chrome
| File | What it does | Depends on |
|---|---|---|
| `AppSidebar.vue` | Server-driven sidebar tree (flat links, groups, children). | `useSidebar`, `sidebarIcons`, `ScrollArea`, `SidebarLink` |
| `SidebarLink.vue` | One link; SPA routes use vue-router, others go to desk. | - |
| `SidebarHeader.vue` | Logo / app switcher at the top of the sidebar. | `useSidebar`, `router` |
| `AppNavbar.vue` | Top bar with notifications and the command palette. | `overlays/NotificationBell`, `overlays/CommandPalette` |
| `ProfileMenu.vue` | User menu: profile, theme, shortcuts, logout. | `useTheme`, `overlays/KeyboardShortcutsDialog`, `notify` |

### `components/overlays/`
| File | What it does | Depends on |
|---|---|---|
| `CommandPalette.vue` | Ctrl/⌘-K quick navigation over sidebar entries. | `useSidebar`, `sidebarIcons`, `router` |
| `NotificationBell.vue` | Bell dropdown with unread notifications. | `useNotifications`, `ScrollArea`, dompurify |
| `KeyboardShortcutsDialog.vue` | Lists shortcuts. | `useSidebar` |

### `components/list/` - list view
| File | What it does | Depends on |
|---|---|---|
| `DocListView.vue` | The generic doctype list: filters, sort, bulk select, pagination, column customisation, quick create. | `useDocList`, `useResource`, `ViewSwitcher`, `Pagination`, `formatValue`, `statusTheme`, `listOptions` |
| `Pagination.vue` | Prev/next + page info. | `AppButton` |
| `QuickCreateDialog.vue` | Modal to create a record from a list / link field. | `DocDetailView`, `useDocDetail` |
| `CustomizeColumnsDialog.vue` | Drag-and-drop column chooser. | `vuedraggable`, `useResource` |
| `KanbanBoard.vue` | Doctype-agnostic kanban columns/cards. | - |
| `EmailQueueStrip.vue` | Email Queue state counters shown above its list. | `AppButton`, `notify` |

### `components/detail/` - record view
**Core** (top level):
| File | What it does | Depends on |
|---|---|---|
| `DetailPageLayout.vue` | Back + title, tabs, actions. | `AppButton` |
| `DocDetailView.vue` | Renders a doctype's field grid from meta. | `StateBanner` |
| `FieldControl.vue` | Renders one field by fieldtype (data, link, select, check…). | `App*` inputs, `AppLinkField`, `fieldFormats` |
| `ChildTableField.vue` | Editable child table in a form. | `AppButton` |
| `AssignToField.vue` | "Assign To" employee picker used by service records. | `AppLinkField` |
| `SummaryStrip.vue` | Row of key figures at the top of a record. | `formatValue` |
| `ActivityTimeline.vue` | Notes, field changes, tasks and events feed. | `useTimeline`, `App*` inputs, `roles`, dompurify |

**`actions/`** - buttons for a record's action bar
| File | What it does | Depends on |
|---|---|---|
| `DocAction.vue` | Generic server-action button (optional prompt). | `AppInput`, `notify`, `errors` |
| `LinkAction.vue` | Navigation button (e.g. "View Chart of Accounts"). | `AppButton` |
| `CreateSalesOrderAction.vue` | Opens a new Sales Order for the customer. | `AppButton` |
| `ResolutionActions.vue` | Resolve / Refund with a reason (Customer Care). | `useResource` |
| `ForwardAction.vue` | Adapter placing the Forward Candidate flow into config actions. | - |
| `ForwardCandidateButton.vue` | The shared "Forward Candidate" dialog flow for service records. | `useResource`, `AppCombobox` |

**`customer/`**
| File | What it does | Depends on |
|---|---|---|
| `CustomerContextPanel.vue` | Customer's Lead Detail Form data. | `useCustomerContext` |
| `CustomerHistoryPanel.vue` | Customer trail across departments. | `useResource` |
| `CustomerSalesOrdersPanel.vue` | Sales orders + payment schedules. | `useResource` |
| `AddressContactPanel.vue` | Linked addresses and contacts, add/edit. | `AppLinkField`, `notify` |

**`lead/`**
| File | What it does | Depends on |
|---|---|---|
| `LeadProfilePanel.vue` | Profile completeness and section chips, editing Lead Detail Form. | `FieldControl`, `ChildTableField` |
| `LeadOpportunityDialog.vue` | "Create Opportunity" dialog. | `AppLinkField` |
| `ServiceResumePanel.vue` | Latest resume on file for a customer. | `useResource` |

**`user/`**
| File | What it does | Depends on |
|---|---|---|
| `UserRolesTab.vue` | Role checkbox matrix. | `useUserRoles` |
| `UserChangePassword.vue` | Change-password form. | `useResource` |

**`esign/`**
| File | What it does | Depends on |
|---|---|---|
| `ESignBuilder.vue` | Recipients and field tools for an E-Sign document. | `usePdfPages` |
| `PdfFieldBuilder.vue` | Toolbox to place fields on PDF pages. | `usePdfPages`, `FieldControl` |
| `ESignSendAction.vue` | Validates and sends for signature. | `notify`, `errors` |
| `ESignTracking.vue` | Read-only signing progress. | `DocStatusBadge` |

**`hierarchy/`** - `HierarchyDiagram.vue`: renders the role hierarchy diagram (uses `utils/detail/hierarchyDiagram.js`).

**`accounts/`** - Sales Order / Journal / Payment panels ported from desk scripts
| File | What it does |
|---|---|
| `AgreementPanel.vue` | Sales Order agreements module. |
| `PaymentTermsPanel.vue` | Payment schedule with "Mark as Paid" / "Re-request". |
| `LinkedInvoicesPanel.vue` | Invoices raised from a Sales Order. |
| `SendDetailsFormAction.vue` | "Send Details Form" action. |
| `JournalQuickEntryAction.vue` | Journal Entry quick entry. |
| `OutstandingInvoicesPanel.vue` | "Get Outstanding Invoices" for write-offs. |
| `PaymentEntryAssist.vue` | Client-side help while filling a Payment Entry. |

All depend on `SectionCard`, `AppButton`, `DocStatusBadge` / inputs as needed, `useResource`, `formatValue`, `notify`, `errors`.

**`marketing/`**
| File | What it does | Depends on |
|---|---|---|
| `MarketingTargetPanel.vue` | Target block (superior-only editing). | `DocDetailView`, `useIsSuperior` |
| `JobApplicationGrid.vue` | Per-day job application counts. | `useIsSuperior` |
| `InterviewRoundsField.vue` | Interview rounds table with desk-form rules. | `FieldControl`, `useIsSuperior`, `roles` |
| `MarketingInterviewsPanel.vue` | Interviews linked to a Marketing record. | `useResource` |
| `CreateInterviewButton.vue` | "Create Interview" dialog. | `AppInput`, vue-router |

**`emailQueue/`**: `EmailQueueActions.vue` (send now / retry), `EmailQueueError.vue`, `EmailQueueMessage.vue` (rendered body via `MailBody`).

**`erp/`**: `EmailConfiguratorGrid.vue` (email usage grid), `FieldSelectorWidget.vue` (item picker), `WebsiteSystemSettingsPanel.vue`, `SampleDataPanel.vue` (remove sample data).

**`fieldUpdate/`**: `FieldUpdateActions.vue` (request/approve field-change buttons), `FieldUpdateDialog.vue` ("Update Detail" dialog), `FieldUpdateReviewDialog.vue` (approver's "Accept Updates").

### `components/mail/`
| File | What it does | Depends on |
|---|---|---|
| `MailSidebar.vue` | Folders / account switch. | `AppCombobox` |
| `MailList.vue` | Search, filters and message list. | `AppSearchInput`, `utils/mail/format` |
| `MailReader.vue` | Message view with reply/forward actions. | `useSendMail`, `MailBody` |
| `MailBody.vue` | Sanitised body in a sandboxed iframe. | dompurify |
| `MailComposeDialog.vue` | New / reply / reply-all / forward. | `useSendMail`, `RecipientInput` |
| `RecipientInput.vue` | Email "chips" input. | `AppInput`, `utils/mail/format` |

### `components/report/`
| File | What it does | Depends on |
|---|---|---|
| `ReportView.vue` | One report: filters, summary, chart, table. | `useReport`, `configs/reports.js`, the other report components |
| `ReportFilterBar.vue` | Server-defined filter panel. | `FieldControl` |
| `ReportTable.vue` | Sortable/searchable/grouped result grid. | `formatReport` |
| `ReportBarChart.vue` | Horizontal bar chart. | - |

### `components/dashboard/`
`DashboardSubNav.vue` (tabs + period/company filters), `DashboardKpi.vue` (headline number + change), `DashboardChart.vue` (server-typed chart card), `DashboardTable.vue`, `DashboardAlerts.vue`. They depend on `utils/dashboard/format.js` and `icons.js`.

### `components/tree/`
`DocTreeView.vue` - doctype-agnostic tree rendered as an indented table (used by `TreePage`, `AccountTreePage`).

---

## 7. `src/composables/` - stateful logic

| Folder | File | What it does | Depends on |
|---|---|---|---|
| `common/` | `useTheme.js` | Shared theme state (system/light/dark), persisted in `localStorage`. | `notify` |
| | `useUnsavedChangesGuard.js` | Prompts before leaving a dirty form (route + tab close). | `confirmDialog`, vue-router |
| `layout/` | `useSidebar.js` | Loads/caches the server sidebar config, shortcuts, active item. | `router`, `notify` |
| | `useNotifications.js` | Notification Log + unread count, updated in realtime. | `realtime`, `deskRoute`, `notify` |
| `list/` | `useResource.js` | **Base for all server calls** (wraps `createResource` with error/toast handling). | `errors`, `notify` |
| | `useApiState.js` | Shared loading / permission-denied / empty state. | `errors` |
| | `useDocList.js` | Orchestrates a doctype list: fields, filters, sort, paging, column prefs. | `configs/detail/listOptions` |
| `detail/` | `useDocDetail.js` | Single-record load, field meta, dirty tracking, save. | `useResource`, `fieldFormats` |
| | `useDetailPageController.js` | Shared shell logic for detail pages (save, delete, tabs, guard). | `useDocDetail`, `useUnsavedChangesGuard` |
| | `useTimeline.js` | Notes/tasks/events CRUD for the activity feed. | `useResource` |
| | `useCustomerContext.js` | Data for customer context panels. | `useResource` |
| | `useLeadDetailForm.js` | Lead's linked Lead Detail Form record. | `useResource` |
| | `useIsSuperior.js` | Whether the user is above an assignee in a department. | `useResource` |
| | `useUserRoles.js` | Role list/toggle for a User. | `useResource` |
| | `useSystemSettingsPanel.js` | The 15 managed System Settings fields. | `useResource` |
| | `usePdfPages.js` | Renders PDF pages to images (pdf.js). | - |
| `report/` | `useReport.js` | A report's lifecycle: filters, defaults, run, format. | `useResource`, `formatReport` |
| `dashboard/` | `useDashboard.js` | A dashboard tab: allowed tabs, period, data, refresh. | `useResource`, `utils/dashboard/format` |
| `mail/` | `useMailbox.js` | Inbox state and calls (folders, messages, flags, delete). | `errors`, `notify` |
| | `useSendMail.js` | One call for compose/reply/reply-all/forward. | `errors`, `notify` |

---

## 8. `src/configs/` - per-doctype configuration

| File | What it does | Depends on |
|---|---|---|
| `detail/marketing.js` | Detail configs for Marketing / Interview / Other Services (panels, actions, target block). | `components/detail/marketing/*`, `customer/*`, `actions/*` |
| `detail/customerCare.js` | CR and Onboardings: derived status, resolution actions. | `customer/*`, `actions/*`, `AssignToField` |
| `detail/accounts.js` | Accounts master (Sales Order, Journal, Payment Entry, …). | `components/detail/accounts/*`, `customer/AddressContactPanel`, `actions/*` |
| `detail/items.js` | Item / Item Category / UOM configs. | - |
| `detail/esign.js` | E-Sign configs (frozen once sent). | `esign/*`, `NoticeBanner` |
| `detail/emailQueue.js` | Email Queue config. | `emailQueue/*` |
| `detail/listOptions.js` | Per-doctype **list-view** behaviour (available views, kanban field, header strip). | `list/EmailQueueStrip` |
| `reports.js` | How each report is presented (its filters and data come from the server). | - |

To add a doctype with extra panels or actions: create a config here, register it in `router.js`, and `ConfigDetailPage` renders it. Only add a dedicated page in `pages/detail/` when the layout genuinely differs.

---

## 9. `src/utils/` - pure helpers

| Folder | File | What it does |
|---|---|---|
| `common/` | `errors.js` | Normalises errors from frappe-ui `call`/resources into readable messages and permission state. |
| | `notify.js` | Toast wrapper. |
| | `confirmDialog.js` | App-wide promise-based "are you sure" dialog. |
| | `roles.js` | Current user's roles from server boot data. |
| | `routeAccess.js` | Asks the server whether the user may open a route (used by the router guard). |
| | `deskRoute.js` | Converts classic-desk `/app/...` paths to SPA routes. |
| | `realtime.js` | Shared Socket.IO connection. |
| `layout/` | `sidebarIcons.js` | Maps sidebar config icon ids to lucide icons (also feeds the Tailwind safelist). |
| `list/` | `formatValue.js` | Per-fieldtype value formatting for lists and panels. |
| | `statusTheme.js` | Best-effort badge colour from a status value. |
| `detail/` | `fieldFormats.js` | Field-name heuristics and validators (phone, email, …). |
| | `hierarchyDiagram.js` | Pure port of the desk hierarchy diagram renderer. |
| `dashboard/` | `format.js` | Number/percent/currency formatting for dashboard tiles. |
| | `icons.js` | Icon vocabulary for dashboard cards (also feeds the Tailwind safelist). |
| `report/` | `formatReport.js` | Turns raw Script Report results into columns/rows for display. Uses `list/formatValue`. |
| `mail/` | `format.js` | Address parsing, dates and snippets for mail screens. |

---

## 10. Conventions

- **Where does new code go?** A reusable primitive → `components/ui`. A small cross-feature block → `components/common`. Feature-specific → the matching feature folder. Logic with reactive state or server calls → `composables/<feature>`. Pure functions → `utils/<feature>`. Doctype-specific tweaks → `configs/`.
- **Server calls** always go through `useResource` (never raw `fetch`).
- **Notifications** use `notify`, **confirmations** use `confirmDialog`, so feedback looks the same everywhere.
- **Styling**: Tailwind with the `app-*` tokens; avoid hard-coded colours so dark mode keeps working.
- **Dynamic icon classes** (`'lucide-' + name`) must be listed in `sidebarIcons.js` / `dashboard/icons.js` so Tailwind's safelist includes them.
- Keep component file names unique (auto-registration is by name).

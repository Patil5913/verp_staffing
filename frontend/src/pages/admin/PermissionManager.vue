<template>
	<div class="flex h-full flex-col">
		<!-- Sub navbar: same shape as a doctype list view (title left, actions
    right) so this reads as part of the app rather than a bolted-on tool. -->
		<div
			class="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-app-border bg-app-panel px-3 py-2 md:h-11 md:px-6 md:py-0"
		>
			<h1 class="min-w-0 shrink-0 truncate text-p-lg font-medium text-app-text">
				Role Permissions Manager
			</h1>
			<div class="flex items-center gap-2">
				<AppButton
					variant="outline"
					icon="plus"
					:disabled="!doctype"
					@click="openAddDialog"
				>
					Add Role Permission
				</AppButton>
				<AppButton
					variant="danger"
					:disabled="!doctype"
					:loading="resetting.loading"
					@click="onReset"
				>
					Reset to Defaults
				</AppButton>
			</div>
		</div>

		<div class="min-h-0 flex-1 overflow-y-auto px-3 md:px-6 py-5">
			<div class="flex flex-col gap-5">
				<!-- Both filters, and either works on its own: pick just a DocType
        to see every role's rules for it, just a Role to see everything that
        role can touch, or both to narrow to one pairing. -->
				<div class="flex flex-wrap gap-4">
					<div class="w-96 max-w-full">
						<AppLinkField
							doctype="DocType"
							label="DocType"
							v-model="doctype"
							placeholder="Search for a DocType…"
							hide-add-new
							:page-length="0"
						/>
					</div>
					<div class="w-96 max-w-full">
						<AppLinkField
							doctype="Role"
							label="Role"
							v-model="role"
							placeholder="Search for a Role…"
							hide-add-new
							:page-length="0"
						/>
					</div>
				</div>

				<StateBanner
					v-if="!doctype && !role"
					icon="shield"
					title="Pick a DocType or a Role"
					description="Select either (or both) above to see and edit what a role can do."
				/>
				<StateBanner
					v-else-if="perms.hasError"
					icon="alert-triangle"
					title="Couldn't load permissions"
					:description="perms.errorMessage"
				/>
				<div
					v-else-if="perms.isLoading && !perms.resource.data"
					class="flex justify-center py-16"
				>
					<LoadingIndicator class="h-6 w-6 text-app-text-muted" />
				</div>

				<div v-else-if="perms.resource.data" class="flex flex-col gap-2">
					<PermissionRuleCard
						v-for="row in perms.resource.data"
						:key="`${row.parent}-${row.role}-${row.permlevel}-${row.if_owner}`"
						:row="row"
						can-write
						@toggle="toggle"
					>
						<template #title>
							<span v-if="!doctype">{{ row.parent }} · </span>{{ row.role }}
						</template>
						<template #actions>
							<AppButton
								variant="ghost"
								size="icon"
								icon="trash-2"
								class="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
								@click="onRemove(row)"
							/>
						</template>
					</PermissionRuleCard>

					<div
						v-if="!perms.resource.data.length"
						class="rounded-lg border border-dashed border-app-border py-10 text-center text-p-sm text-app-text-muted"
					>
						No matching permissions yet - use "Add Role Permission" above.
					</div>
				</div>
			</div>
		</div>

		<!-- Add dialog: pick the role + level to grant this DocType to. -->
		<Dialog
			v-model="addOpen"
			:options="{ title: `Add Role Permission - ${doctype}`, size: 'sm' }"
		>
			<template #body-content>
				<div class="flex flex-col gap-4">
					<AppLinkField
						doctype="Role"
						label="Role"
						v-model="newRole"
						placeholder="Search for a role…"
					/>
					<div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
						<label v-for="pt in PTYPES" :key="pt" class="flex items-center gap-2">
							<AppCheckbox v-model="newPerms[pt]" />
							<span class="text-p-sm capitalize text-app-text">{{ pt }}</span>
						</label>
					</div>
				</div>
			</template>
			<template #actions>
				<AppButton
					variant="primary"
					:disabled="!newRole"
					:loading="addingBusy"
					@click="onAddLevel"
					>Add</AppButton
				>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import AppCheckbox from "@/components/ui/AppCheckbox.vue";
import PermissionRuleCard from "@/components/detail/role/PermissionRuleCard.vue";
// Permission Manager: DocType and Role filters both work standalone (pick
// just one) or together - the backend already supports every combination
// (get_permissions falls back to "every role" when role is blank, and to
// "every doctype that role touches" when doctype is blank), so the frontend
// just needs to fetch whenever at least one is set instead of demanding
// both. Edits stage in a dialog and only commit on Save, rather than firing
// a server call on every checkbox click.
import { ref, watch } from "vue";
import { useRoute } from "vue-router";
import { Dialog, LoadingIndicator } from "frappe-ui";
import AppButton from "@/components/ui/AppButton.vue";
import AppLinkField from "@/components/common/AppLinkField.vue";
import { useResource } from "@/composables/list/useResource";
import { notify } from "@/utils/common/notify";
import StateBanner from "@/components/common/StateBanner.vue";

const PTYPES = [
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"report",
	"export",
	"import",
	"share",
	"print",
	"email",
	"select",
];

const route = useRoute();
// Landing here from a Role's own detail page ("Manage Permissions") passes
// ?role=<name> so that role is already selected instead of making the user
// re-pick it.
const doctype = ref("");
const role = ref(typeof route.query.role === "string" ? route.query.role : "");

const perms = useResource({
	url: "frappe.core.page.permission_manager.permission_manager.get_permissions",
	makeParams: () => ({ doctype: doctype.value, role: role.value }),
});

function reload() {
	if (doctype.value || role.value)
		perms.resource.submit({ doctype: doctype.value, role: role.value });
}
watch([doctype, role], reload, { immediate: true });

const updating = useResource({
	url: "frappe.core.page.permission_manager.permission_manager.update",
	notifyOnError: false,
});

async function toggle(row, ptype) {
	const value = row[ptype] ? 0 : 1;
	try {
		await updating.resource.submit({
			doctype: row.parent,
			role: row.role,
			permlevel: row.permlevel,
			ptype,
			value,
			if_owner: row.if_owner ? 1 : 0,
		});
		row[ptype] = value;
	} catch {
		notify.error("Couldn't save permission - please try again.");
	}
}

// ── Add ────────────────────────────────────────────────────────────────
const addOpen = ref(false);
const newRole = ref("");
const newPerms = ref({});

function openAddDialog() {
	newRole.value = role.value || "";
	newPerms.value = {};
	addOpen.value = true;
}

const adding = useResource({
	url: "frappe.core.page.permission_manager.permission_manager.add",
	notifyOnError: false,
});
const addingBusy = ref(false);
async function onAddLevel() {
	addingBusy.value = true;
	try {
		await adding.resource.submit({ parent: doctype.value, role: newRole.value, permlevel: 0 });
		for (const ptype of PTYPES.filter((pt) => newPerms.value[pt])) {
			await updating.resource.submit({
				doctype: doctype.value,
				role: newRole.value,
				permlevel: 0,
				ptype,
				value: 1,
				if_owner: 0,
			});
		}
		addOpen.value = false;
		reload();
	} catch {
		notify.error("Couldn't add permission - please try again.");
	} finally {
		addingBusy.value = false;
	}
}

// ── Remove ────────────────────────────────────────────────────────────
const removing = useResource({
	url: "frappe.core.page.permission_manager.permission_manager.remove",
	onSuccess: reload,
});
function onRemove(row) {
	removing.resource.submit({
		doctype: row.parent,
		role: row.role,
		permlevel: row.permlevel,
		if_owner: row.if_owner ? 1 : 0,
	});
}

// ── Reset ─────────────────────────────────────────────────────────────
const resetting = useResource({
	url: "frappe.core.page.permission_manager.permission_manager.reset",
	onSuccess() {
		notify.success(`Permissions for ${doctype.value} reset to defaults.`);
		reload();
	},
});
function onReset() {
	resetting.resource.submit({ doctype: doctype.value });
}
</script>

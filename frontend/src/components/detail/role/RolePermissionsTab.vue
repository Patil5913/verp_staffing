<template>
	<div class="flex flex-col gap-4">
		<StateBanner
			v-if="perms.hasError"
			icon="alert-triangle"
			title="Couldn't load permissions"
			:description="perms.errorMessage"
		/>
		<div v-else-if="perms.isLoading && !perms.resource.data" class="flex justify-center py-16">
			<LoadingIndicator class="h-6 w-6 text-app-text-muted" />
		</div>

		<div v-else class="rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
			<div class="mb-4">
				<h2 class="text-p-lg font-medium text-app-text">Permissions</h2>
				<p class="text-p-sm text-app-text-muted">
					What this role can do, grouped by module. Click a permission to toggle it.
				</p>
			</div>

			<div class="flex flex-col gap-4">
				<div
					v-for="(section, si) in sections"
					:key="section.label"
					class="flex flex-col gap-2 rounded-lg p-3"
					:style="sectionStyle(si)"
				>
					<button
						type="button"
						class="flex items-center gap-2 text-left"
						@click="toggleSection(section.label)"
					>
						<FeatherIcon
							:name="isOpen(section.label) ? 'chevron-down' : 'chevron-right'"
							class="h-4 w-4 text-app-text-muted"
						/>
						<span
							class="text-p-xs font-semibold uppercase tracking-wide text-app-text"
							>{{ section.label }}</span
						>
						<AppBadge>{{ section.rows.length }} DocTypes</AppBadge>
					</button>
					<div v-show="isOpen(section.label)" class="flex flex-col gap-2">
						<PermissionRuleCard
							v-for="row in section.rows"
							:key="`${row.parent}-${row.permlevel}-${row.if_owner}`"
							:row="row"
							:can-write="canWrite"
							@toggle="toggle"
						/>
					</div>
				</div>
			</div>
			<p v-if="!sections.length" class="py-8 text-center text-p-sm text-app-text-muted">
				{{ search ? 'No matching DocTypes.' : 'No permissions set for this role yet.' }}
			</p>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { LoadingIndicator, FeatherIcon } from "frappe-ui";
import PermissionRuleCard from "@/components/detail/role/PermissionRuleCard.vue";
import AppBadge from "@/components/ui/AppBadge.vue";
import StateBanner from "@/components/common/StateBanner.vue";
import { useResource } from "@/composables/list/useResource";
import { notify } from "@/utils/common/notify";

const props = defineProps({
	role: { type: String, required: true },
	canWrite: { type: Boolean, default: false },
});

const SECTION_RGB = [
	"37, 99, 235",
	"5, 150, 105",
	"217, 119, 6",
	"124, 58, 237",
	"225, 29, 72",
	"8, 145, 178",
];
const sectionStyle = (i) => {
	const rgb = SECTION_RGB[i % SECTION_RGB.length];
	return {
		backgroundColor: `rgba(${rgb}, 0.12)`,
		border: `1px solid rgba(${rgb}, 0.4)`,
		borderLeft: `5px solid rgb(${rgb})`,
	};
};

const perms = useResource({
	url: "verp_staffing.utils.role_view.get_role_permissions",
	makeParams: () => ({ role: props.role }),
	auto: true,
});

const sections = computed(() => {
	const groups = {};
	const q = search.value.trim().toLowerCase();
	for (const row of perms.resource.data || [])
		if (!q || row.parent.toLowerCase().includes(q) || row.module.toLowerCase().includes(q))
			(groups[row.module] ||= []).push(row);
	return Object.keys(groups)
		.sort()
		.map((label) => ({ label, rows: groups[label] }));
});

const search = ref("");
const collapsed = ref(new Set());
const isOpen = (label) => !collapsed.value.has(label);
function toggleSection(label) {
	const next = new Set(collapsed.value);
	if (next.has(label)) next.delete(label);
	else next.add(label);
	collapsed.value = next;
}

const PTYPES = ["read", "write", "create", "delete", "submit", "cancel", "amend", "report", "export", "import", "share", "print", "email", "select"];
async function setAll(section, value) {
	for (const row of section.rows)
		for (const pt of PTYPES) if (!!row[pt] !== !!value) await toggle(row, pt);
}

const updating = useResource({
	url: "frappe.core.page.permission_manager.permission_manager.update",
	notifyOnError: false,
});
async function toggle(row, ptype) {
	if (!props.canWrite) return;
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
</script>

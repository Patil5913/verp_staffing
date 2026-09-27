<template>
	<div v-if="field.fieldtype === 'Link' && !isLinkToFile" class="flex flex-col gap-1.5">
		<AppLinkField
			:key="linkFiltersKey"
			:label="field.label"
			:required="Boolean(field.reqd)"
			:doctype="field.options"
			:query="linkQuery?.query"
			:filters="linkQuery?.filters"
			:model-value="modelValue || ''"
			:disabled="disabled"
			@update:model-value="(v) => emit('update:modelValue', v)"
		/>
		<p v-if="error" class="text-p-xs text-red-600">{{ error }}</p>
	</div>

	<div v-else-if="field.fieldtype === 'Dynamic Link'" class="flex flex-col gap-1.5">
		<AppLinkField
			v-if="dynamicDoctype"
			:label="field.label"
			:required="Boolean(field.reqd)"
			:doctype="dynamicDoctype"
			:query="linkQuery?.query"
			:filters="linkQuery?.filters"
			:model-value="modelValue || ''"
			:disabled="disabled"
			@update:model-value="(v) => emit('update:modelValue', v)"
		/>
		<template v-else>
			<label v-if="field.label" class="text-p-sm font-medium text-app-text-muted">{{
				field.label
			}}</label>
			<p class="text-p-sm text-app-text-muted">Pick the linked record's type first.</p>
		</template>
		<p v-if="error" class="text-p-xs text-red-600">{{ error }}</p>
	</div>

	<div v-else-if="isLinkToFile" class="flex flex-col gap-1.5">
		<label v-if="field.label" class="text-p-sm font-medium text-app-text-muted">
			{{ field.label }}<span v-if="field.reqd" class="text-red-600"> *</span>
		</label>
		<div class="flex items-center gap-3">
			<LoadingIndicator
				v-if="modelValue && linkedFile.loading"
				class="h-4 w-4 text-app-text-muted"
			/>
			<a
				v-else-if="modelValue && linkedFile.url"
				:href="linkedFile.url"
				target="_blank"
				rel="noopener"
				class="min-w-0 truncate text-p-sm text-app-primary hover:underline"
			>
				{{ linkedFile.name || modelValue }}
			</a>
			<!-- A value with no readable file record (e.g. the portal can't look one up) is still a file. -->
			<span v-else-if="modelValue" class="text-p-sm text-app-text">{{ linkedFile.name || "File uploaded" }}</span>
			<span v-else class="text-p-sm text-app-text-muted">No file attached</span>

			<FileUploader v-if="!disabled" @success="onLinkToFileUploaded">
				<template #default="{ uploading, progress, openFileSelector }">
					<AppButton
						variant="outline"
						size="sm"
						:loading="uploading"
						@click="openFileSelector"
					>
						{{
							uploading
								? `Uploading ${progress}%`
								: modelValue
									? "Replace"
									: "Upload"
						}}
					</AppButton>
				</template>
			</FileUploader>
			<AppButton
				v-if="!disabled && modelValue"
				variant="ghost"
				size="icon"
				icon="x"
				@click="emit('update:modelValue', '')"
			/>
		</div>
		<p v-if="error" class="text-p-xs text-red-600">{{ error }}</p>
	</div>

	<div v-else-if="controlType === 'checkbox'" class="pt-6">
		<AppCheckbox
			:label="field.label"
			:model-value="Boolean(modelValue)"
			:disabled="disabled"
			@update:model-value="(v) => emit('update:modelValue', v)"
		/>
	</div>

	<div v-else-if="controlType === 'attach'" class="flex flex-col gap-1.5">
		<label v-if="field.label" class="text-p-sm font-medium text-app-text-muted">
			{{ field.label }}<span v-if="field.reqd" class="text-red-600"> *</span>
		</label>
		<div class="flex items-center gap-3">
			<img
				v-if="field.fieldtype === 'Attach Image' && modelValue"
				:src="modelValue"
				class="h-10 w-10 shrink-0 rounded-md border border-app-border object-cover"
			/>
			<a
				v-else-if="modelValue"
				:href="modelValue"
				target="_blank"
				rel="noopener"
				class="min-w-0 truncate text-p-sm text-app-primary hover:underline"
			>
				{{ attachFileName }}
			</a>
			<span v-else class="text-p-sm text-app-text-muted">No file attached</span>

			<FileUploader
				v-if="!disabled"
				:file-types="field.accept"
				@success="
					(f) => {
						emit('update:modelValue', f.file_url);
						emit('file-meta', f);
					}
				"
			>
				<template #default="{ uploading, progress, openFileSelector }">
					<AppButton
						variant="outline"
						size="sm"
						:loading="uploading"
						@click="openFileSelector"
					>
						{{
							uploading
								? `Uploading ${progress}%`
								: modelValue
									? "Replace"
									: "Upload"
						}}
					</AppButton>
				</template>
			</FileUploader>
			<AppButton
				v-if="!disabled && modelValue"
				variant="ghost"
				size="icon"
				icon="x"
				@click="clearFile"
			/>
		</div>
	</div>

	<div v-else class="flex flex-col gap-1.5">
		<label v-if="field.label" class="text-p-sm font-medium text-app-text-muted">
			{{ field.label }}<span v-if="field.reqd" class="text-red-600"> *</span>
		</label>

		<!-- reusable.js's field-name-driven rendering: a read-only email opens
		a mail composer (mailto: here - no in-app composer in this SPA), a
		read-only LinkedIn-style URL field is just a link. Only once disabled -
		still a plain editable input otherwise. -->
		<a
			v-if="disabled && isEmailField(field.fieldname) && displayValue"
			:href="`mailto:${displayValue}`"
			class="text-p-sm font-medium text-app-primary hover:underline"
		>{{ displayValue }}</a>
		<a
			v-else-if="disabled && isLinkedinField(field.fieldname) && displayValue"
			:href="String(displayValue).startsWith('http') ? displayValue : `https://${displayValue}`"
			target="_blank"
			rel="noopener"
			class="text-p-sm font-medium text-app-primary hover:underline"
		>{{ displayValue }}</a>
		<TruncatedText
			v-else-if="controlType === 'textarea' && disabled"
			:text="displayValue || ''"
			:max-height="maxDisplayHeight"
			class="text-p-sm text-app-text"
		/>
		<AppTextarea
			v-else-if="controlType === 'textarea'"
			:model-value="displayValue ?? ''"
			:disabled="disabled"
			:placeholder="placeholder"
			@update:model-value="onInput"
		/>
		<AppCombobox
			v-else-if="controlType === 'select'"
			:model-value="String(displayValue ?? '')"
			:options="selectOptions"
			:disabled="disabled"
			:placeholder="placeholder || 'Select an option'"
			@update:model-value="onInput"
		/>
		<AppTimeInput
			v-else-if="controlType === 'time'"
			:model-value="displayValue ?? ''"
			:disabled="disabled"
			@update:model-value="onInput"
		/>
		<AppAvailabilityPicker
			v-else-if="isAvailability"
			:model-value="displayValue ?? ''"
			:disabled="disabled"
			@update:model-value="onInput"
		/>
		<AppInput
			v-else
			:type="controlType"
			:model-value="displayValue ?? ''"
			:disabled="disabled"
			:placeholder="placeholder"
			:prefix="currencyInfo.symbol"
			:prefix-title="currencyInfo.code"
			@update:model-value="onInput"
		/>
		<p v-if="field.description" class="-mt-1 text-p-xs text-app-text-muted">
			{{ field.description }}
		</p>

		<p v-if="error" class="text-p-xs text-red-600">{{ error }}</p>
	</div>
</template>

<script setup>
import AppCheckbox from "@/components/ui/AppCheckbox.vue";
import { computed, inject, reactive, watch } from "vue";
import { FileUploader, LoadingIndicator, call } from "frappe-ui";
import AppButton from "@/components/ui/AppButton.vue";
import AppCombobox from "@/components/ui/AppCombobox.vue";
import AppLinkField from "@/components/common/AppLinkField.vue";
import AppInput from "@/components/ui/AppInput.vue";
import { currencyCodeFor, currencySymbol } from "@/utils/detail/currency";
import AppTimeInput from "@/components/ui/AppTimeInput.vue";
import AppAvailabilityPicker from "@/components/ui/AppAvailabilityPicker.vue";
import TruncatedText from "@/components/ui/TruncatedText.vue";
import AppTextarea from "@/components/ui/AppTextarea.vue";
import {
	isEmailField,
	isLinkedinField,
	isMonthYearField,
	isPhoneField,
	isAvailabilityField,
	toMonthYear,
	fromMonthYear,
	validateFieldValue,
} from "@/utils/detail/fieldFormats";

// A Currency field shows its currency symbol - resolved from the field's `options`
// against the row / document it sits in (see utils/detail/currency.js). A parent
// provides the documents to look in; a grid cell passes its own row via `currencyDocs`.
const parentCurrencyDocs = inject("fieldCurrencyDocs", null);

const props = defineProps({
	currencyDocs: { type: Array, default: null },
	// { file_url, file_name } for a Link-to-File value the caller already has (the customer
	// portal can't look a File up itself) - skips the lookup below.
	fileInfo: { type: Object, default: null },
	field: { type: Object, required: true },
	modelValue: { default: null },
	disabled: { type: Boolean, default: false },
	showErrors: { type: Boolean, default: false },
	// { query?, filters? } for a Link field - a whitelisted standard query and/or
	// filters, like the desk's frm.set_query(fieldname, ...).
	linkQuery: { type: Object, default: null },
	// Optional async (fieldname) => boolean for a file the server should delete
	// straight away (Lead Detail Form, as on the desk) instead of just clearing
	// the field until the next Save. Resolve false to keep the file.
	removeFile: { type: Function, default: null },
	// For a Dynamic Link field (`field.options` names another field on the
	// same doc whose value is the *target doctype*): that resolved doctype
	// name, since this component only sees its own field/value, not the rest
	// of the doc. The caller (DocDetailView) resolves it.
	dynamicDoctype: { type: String, default: "" },
	// Read-only long-text fields (Small Text/Long Text/Text Editor) clamp to
	// this height and offer "View more" instead of showing the full text -
	// configurable per caller rather than a fixed line count baked in here,
	// since how much room is available varies by where the field is shown.
	maxDisplayHeight: { type: String, default: "4.5em" },
});
const emit = defineEmits(["update:modelValue", "file-meta"]);

const TYPE_MAP = {
	Data: "text",
	"Small Text": "textarea",
	"Long Text": "textarea",
	"Text Editor": "textarea",
	Code: "textarea",
	JSON: "textarea",
	Int: "number",
	Float: "number",
	Currency: "number",
	Percent: "number",
	Duration: "number",
	Rating: "number",
	Check: "checkbox",
	Select: "select",
	Date: "date",
	Datetime: "datetime-local",
	Time: "time",
	Attach: "attach",
	"Attach Image": "attach",
	Password: "password",
};

async function clearFile() {
	if (props.removeFile && !(await props.removeFile(props.field.fieldname))) return;
	emit("update:modelValue", "");
}

// These fieldname heuristics (personal_phone_number, start_date, ...) come
// from Lead Detail Form's own Data-typed fields, which store a phone/MM-YYYY
// string rather than a real Frappe Date. Scoping them to fieldtype Data
// keeps them from also catching an unrelated same-named field elsewhere
// that's genuinely typed - e.g. Employee.start_date is a real Date field,
// and was being forced into a "MM-YYYY" text box (wrong placeholder, wrong
// display formatting, date picker never opening) instead of its date picker.
const isDataField = computed(() => props.field.fieldtype === "Data");
const isMonthYear = computed(() => isDataField.value && isMonthYearField(props.field.fieldname));
const isPhone = computed(() => isDataField.value && isPhoneField(props.field.fieldname));
const isAvailability = computed(() => isDataField.value && isAvailabilityField(props.field.fieldname));

const currencyInfo = computed(() => {
	if (props.field.fieldtype !== "Currency") return { symbol: "", code: "" };
	const docs = props.currencyDocs ?? parentCurrencyDocs?.() ?? [];
	const code = currencyCodeFor(props.field, docs);
	return { symbol: currencySymbol(code), code };
});

const controlType = computed(() => {
	if (isDataField.value && isEmailField(props.field.fieldname)) return "email";
	if (isPhone.value || isMonthYear.value) return "text";
	return TYPE_MAP[props.field.fieldtype] || "text";
});

const placeholder = computed(() => {
	if (isMonthYear.value) return "MM-YYYY";
	if (isPhone.value) return "Exp: +1xxxxxxxxxx";
	return undefined;
});

const displayValue = computed(() => {
	if (isMonthYear.value) return toMonthYear(props.modelValue);
	return props.modelValue;
});

function onInput(value) {
	if (isMonthYear.value) {
		emit("update:modelValue", fromMonthYear(value));
		return;
	}
	emit("update:modelValue", value);
}

const attachFileName = computed(() => (props.modelValue || "").split("/").pop());

// A Link-to-File field (Lead Detail Form's Visa Copy/Driving Licence/EAD
// Card/Old Resume, ...) is Desk's convention for "an upload, referenced by
// the File doc's name rather than a plain Attach field's raw URL" - the
// generic Link branch above would otherwise render it as a doctype
// search/picker, which is meaningless for a File record nobody browses by
// name. Renders the same upload/replace/clear UI as Attach, just storing
// the File doc's `name` as the field value instead of its `file_url`.
const isLinkToFile = computed(
	() => props.field.fieldtype === "Link" && props.field.options === "File",
);

// Forces AppLinkField to fully remount whenever the filter/query it should
// search under changes - e.g. Employee Assignment Details' Designation
// column depends on the row's own Department (get_department_hierarchy_
// roles_query), and Assigned To depends on Designation in turn (see
// EmployeeDetailPage.vue's assignmentLinkQueries). A prop update alone
// re-fetches AppLinkField's *option list*, but a Combobox that's already
// open (or was interacted with under the old filter) can otherwise keep
// showing stale results/selection state from before the filter changed -
// a full remount is the reliable way to guarantee none of that survives.
const linkFiltersKey = computed(
	() => JSON.stringify(props.linkQuery?.filters || {}) + (props.linkQuery?.query || ""),
);

let justUploaded = null; // declared before the immediate watch below reads it
const linkedFile = reactive({ url: "", name: "", loading: false });
watch(
	() => (isLinkToFile.value ? props.modelValue : null),
	async (fileName) => {
		// The file just uploaded here: its details are already in hand, no lookup needed.
		if (fileName && justUploaded?.name === fileName) return;
		linkedFile.url = "";
		linkedFile.name = "";
		if (!fileName) return;
		if (props.fileInfo?.file_url && props.fileInfo.name === fileName) {
			linkedFile.url = props.fileInfo.file_url;
			linkedFile.name = props.fileInfo.file_name || "";
			return;
		}
		linkedFile.loading = true;
		try {
			const file = await call("frappe.client.get_value", {
				doctype: "File",
				filters: fileName,
				fieldname: ["file_url", "file_name"],
			}).catch(() => null);
			linkedFile.url = file?.file_url || "";
			linkedFile.name = file?.file_name || "";
		} finally {
			linkedFile.loading = false;
		}
	},
	{ immediate: true },
);
function onLinkToFileUploaded(f) {
	justUploaded = f;
	linkedFile.url = f.file_url;
	linkedFile.name = f.file_name || f.file_url?.split("/").pop() || "";
	emit("update:modelValue", f.name);
}

const selectOptions = computed(() => {
	if (props.field.fieldtype !== "Select") return [];
	const raw = (props.field.options || "").split("\n");
	const options = raw.filter(Boolean).map((v) => ({ label: v, value: v }));
	// A leading blank line is Frappe's "may be left empty" - offer that choice,
	// so a filter or optional Select can be cleared again once picked.
	return raw[0] === "" && raw.length > 1 ? [{ label: "-", value: "" }, ...options] : options;
});

const error = computed(() => {
	if (!props.showErrors) return "";
	return validateFieldValue(props.field, props.modelValue);
});

defineExpose({ error });
</script>

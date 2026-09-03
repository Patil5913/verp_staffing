frappe.listview_settings["Onboardings"] = {
	onload(listview) {
		listview.page.btn_primary.hide();
		const interval = setInterval(() => {
			const btn = document.querySelector(".btn-new-doc");
			if (btn) {
				btn.style.display = "none";
				clearInterval(interval);
			}
		}, 300);
	},
	get_indicator(doc) {
		const colors = {
			Active: "orange",
			Completed: "green",
			Returned: "blue",
		};
		return [__(doc.status), colors[doc.status] || "grey", "status,=," + doc.status];
	},
};

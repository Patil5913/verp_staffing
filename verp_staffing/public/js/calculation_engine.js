// Initialize global namespace
window.verp_staffing = window.verp_staffing || {};
verp_staffing.calculation_engine = verp_staffing.calculation_engine || {};

/**
 * Main Calculation Engine
 * This function handles:
 * - Item calculations
 * - Tax calculations (all types)
 * - Discount distribution
 * - Currency conversion
 * - Rounding
 *
 * This is reusable across:
 * Sales Invoice, Purchase Invoice, Orders
 */

verp_staffing.calculation_engine.calculate_invoice = function (frm) {
	if (!frm.doc.items || frm.doc.items.length === 0) return;

	this.calculate_items(frm);
	this.apply_discount(frm);
	this.calculate_taxes(frm);
	this.calculate_base(frm);
	this.calculate_rounding(frm);

	frm.refresh_field("items");
	frm.refresh_field("taxes");
};

/**
 * Step 1: Calculate item amounts and totals
 */
verp_staffing.calculation_engine.calculate_items = function (frm) {
	let net_total = 0;
	let total_qty = 0;

	frm.doc.items.forEach((row) => {
		row.amount = flt(row.qty) * flt(row.rate);
		net_total += row.amount;
		total_qty += flt(row.qty);
	});

	frm.set_value("total", net_total);
	frm.set_value("net_total", net_total);
	frm.set_value("total_qty", total_qty);
};

/**
 * Step 2: Calculate taxes based on charge type
 */
verp_staffing.calculation_engine.calculate_taxes = function (frm) {
	let net_total = flt(frm.doc.net_total);
	let cumulative_total = net_total;
	(frm.doc.taxes || []).forEach((tax, i) => {
		let tax_amount = 0;

		// CASE 1: Actual
		if (tax.charge_type === "Actual") {
			tax_amount = flt(tax.tax_amount || 0);
		}

		// CASE 2: On Net Total
		else if (tax.charge_type === "On Net Total") {
			tax_amount = (net_total * flt(tax.rate)) / 100;
		}

		// CASE 3: On Previous Row Amount
		else if (tax.charge_type === "On Previous Row Amount") {
			let prev = frm.doc.taxes[i - 1];
			if (!prev) {
				frappe.throw("Previous row not found for tax calculation");
			}
			tax_amount = (flt(prev.tax_amount) * flt(tax.rate)) / 100;
		}

		// CASE 4: On Previous Row Total
		else if (tax.charge_type === "On Previous Row Total") {
			let prev = frm.doc.taxes[i - 1];
			if (!prev) {
				frappe.throw("Previous row not found for tax calculation");
			}
			tax_amount = (flt(prev.total) * flt(tax.rate)) / 100;
		}

		// CASE 5: On Item Quantity
		else if (tax.charge_type === "On Item Quantity") {
			let total_qty = 0;
			frm.doc.items.forEach((item) => {
				total_qty += flt(item.qty);
			});
			tax_amount = total_qty * flt(tax.rate);
		}

		tax.tax_amount = tax_amount;

		cumulative_total += tax_amount;
		tax.total = cumulative_total;
	});

	frm.set_value("total_taxes_and_charges", cumulative_total - net_total);
	frm.set_value("grand_total", cumulative_total);
};

/**
 * Step 3: Apply discount proportionally
 */
verp_staffing.calculation_engine.apply_discount = function (frm) {
	let discount = flt(frm.doc.discount_amount || 0);
	let total = flt(frm.doc.total);

	// No discount → reset everything
	if (!discount) {
		frm.set_value("net_total", total);

		(frm.doc.items || []).forEach((item) => {
			item.net_amount = item.amount;
		});

		return;
	}
	if (discount > total) {
		frappe.throw("Discount cannot exceed total");
	}

	let ratio = discount / total;

	let new_net_total = 0;

	(frm.doc.items || []).forEach((item) => {
		let reduction = flt(item.amount) * ratio;
		item.net_amount = flt(item.amount - reduction);
		new_net_total += item.net_amount;
	});

	frm.set_value("net_total", new_net_total);
	frm.refresh_field("items");
};

/**
 * Step 4: Convert to base currency
 */
verp_staffing.calculation_engine.calculate_base = function (frm) {
	let rate = flt(frm.doc.conversion_rate || 1);

	frm.set_value("base_total", flt(frm.doc.total) * rate);
	frm.set_value("base_net_total", flt(frm.doc.net_total) * rate);
	frm.set_value("base_grand_total", flt(frm.doc.grand_total) * rate);
	frm.set_value(
		"base_total_taxes_and_charges",
		flt(frm.doc.total_taxes_and_charges) * flt(frm.doc.conversion_rate || 1),
	);
	frm.set_value("base_rounding_adjustment", flt(frm.doc.rounding_adjustment) * rate);
	frm.set_value("base_rounded_total", flt(frm.doc.rounded_total) * rate);
	if (frm.doc.discount_amount) {
		frm.set_value("base_discount_amount", flt(frm.doc.discount_amount) * rate);
	}
};

/**
 * Step 5: Handle rounding
 */
verp_staffing.calculation_engine.calculate_rounding = function (frm) {
	let rate = flt(frm.doc.conversion_rate || 1);

	if (frm.doc.disable_rounded_total) {
		frm.set_value("rounded_total", frm.doc.grand_total);
		frm.set_value("rounding_adjustment", 0);
		frm.set_value("base_rounded_total", frm.doc.base_grand_total);
		frm.set_value("outstanding_amount", frm.doc.grand_total);

		return;
	}

	let rounded = Math.round(flt(frm.doc.grand_total));
	let adjustment = rounded - frm.doc.grand_total;

	frm.set_value("rounded_total", rounded);
	frm.set_value("rounding_adjustment", adjustment);
	frm.set_value("base_rounded_total", rounded * rate);
	frm.set_value("outstanding_amount", rounded);
};

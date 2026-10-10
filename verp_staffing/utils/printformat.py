import frappe
from frappe.utils import escape_html

from verp_staffing.utils.email_template import get_email_branding

SALES_INVOICE_PRINT_FORMAT = "Verp Sales Invoice"


# --------------------------------------------------------------------------
# Generic, reusable upsert for any Jinja print format
# --------------------------------------------------------------------------
def upsert_print_format(name, doc_type, html, make_default=False):
    """Create or update a custom Jinja Print Format. Returns True if changed."""
    if frappe.db.exists("Print Format", name):
        doc = frappe.get_doc("Print Format", name)
        if (
            doc.html == html
            and doc.doc_type == doc_type
            and doc.custom_format
            and not doc.disabled
        ):
            changed = False
        else:
            doc.doc_type = doc_type
            doc.html = html
            doc.custom_format = 1
            doc.print_format_type = "Jinja"
            doc.standard = "No"
            doc.disabled = 0
            doc.save(ignore_permissions=True)
            changed = True
    else:
        frappe.get_doc(
            {
                "doctype": "Print Format",
                "name": name,
                "doc_type": doc_type,
                "html": html,
                "custom_format": 1,
                "print_format_type": "Jinja",
                "standard": "No",
                "disabled": 0,
            }
        ).insert(ignore_permissions=True)
        changed = True

    if make_default:
        frappe.make_property_setter(
            {
                "doctype": doc_type,
                "doctype_or_field": "DocType",
                "property": "default_print_format",
                "value": name,
                "property_type": "Data",
            }
        )
    return changed


# --------------------------------------------------------------------------
# Bank accounts (max 3) for the footer block
# --------------------------------------------------------------------------
# Placeholder bank details until the company's real ones are entered - the
# template just shows where they go.
DUMMY_BANK_DETAILS = """
    <div style="margin-top:20px;">
      <div style="font-size:12px;font-weight:700;color:#111;margin-bottom:6px;">Bank Details</div>
      <table cellpadding="0" cellspacing="0" style="font-size:11px;color:#444;">
        <tr><td style="padding:2px 12px 2px 0;color:#666;">Bank Name</td><td>Dummy Bank Ltd.</td></tr>
        <tr><td style="padding:2px 12px 2px 0;color:#666;">Account Number</td><td>1234 5678 9012</td></tr>
        <tr><td style="padding:2px 12px 2px 0;color:#666;">IFSC Code</td><td>DUMM0001234</td></tr>
      </table>
    </div>"""


SALES_INVOICE_TEMPLATE = """
{% macro money(v) %}{{ frappe.utils.fmt_money(v or 0, currency=doc.currency) }}{% endmacro %}

<style>
  /* Print engines drop background colours unless told to keep them. */
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
</style>
<div style="font-family:Arial,sans-serif;font-size:12px;color:#333;line-height:1.5;">

  <!-- HEADER -->
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td width="55%" valign="top">
        __LOGO_BLOCK__
        <div style="font-size:16px;font-weight:700;color:#111;margin-top:6px;">__COMPANY_NAME__</div>
      </td>
      <td width="45%" valign="top" align="right">
        <div style="font-size:26px;font-weight:800;color:#111;letter-spacing:1px;">
          {{ _("INVOICE") }}
        </div>
        <table cellpadding="0" cellspacing="0" align="right" style="margin-top:8px;font-size:12px;">
          <tr><td style="padding:2px 10px;color:#666;">{{ _("Invoice No.") }}</td>
              <td style="padding:2px 0;font-weight:700;">{{ doc.name }}</td></tr>
          <tr><td style="padding:2px 10px;color:#666;">{{ _("Date") }}</td>
              <td style="padding:2px 0;">{{ frappe.utils.formatdate(doc.posting_date) }}</td></tr>
          {% if doc.due_date %}
          <tr><td style="padding:2px 10px;color:#666;">{{ _("Due Date") }}</td>
              <td style="padding:2px 0;">{{ frappe.utils.formatdate(doc.due_date) }}</td></tr>
          {% endif %}
        </table>
      </td>
    </tr>
  </table>

  <hr style="border:none;border-top:2px solid #111;margin:16px 0;">

  <!-- BILL TO -->
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td valign="top" width="60%">
        <div style="font-size:11px;color:#666;text-transform:uppercase;">{{ _("Bill To") }}</div>
        <div style="font-size:14px;font-weight:700;color:#111;">{{ doc.customer }}</div>
      </td>
    </tr>
  </table>

  <!-- ITEMS -->
  <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:18px;border-collapse:collapse;">
    <thead>
      <tr>
        <th align="left"  style="background:#111;color:#fff;padding:8px 10px;width:6%;">#</th>
        <th align="left"  style="background:#111;color:#fff;padding:8px 10px;">{{ _("Description") }}</th>
        <th align="right" style="background:#111;color:#fff;padding:8px 10px;width:10%;">{{ _("Qty") }}</th>
        <th align="right" style="background:#111;color:#fff;padding:8px 10px;width:16%;">{{ _("Rate") }}</th>
        <th align="right" style="background:#111;color:#fff;padding:8px 10px;width:18%;">{{ _("Amount") }}</th>
      </tr>
    </thead>
    <tbody>
      {% for item in doc.items %}
      <tr>
        <td style="padding:8px 10px;border-bottom:1px solid #e5e7eb;" valign="top">{{ loop.index }}</td>
        <td style="padding:8px 10px;border-bottom:1px solid #e5e7eb;" valign="top">
          <div style="font-weight:600;">{{ item.item }}</div>
        </td>
        <td align="right" style="padding:8px 10px;border-bottom:1px solid #e5e7eb;" valign="top">
          {{ item.get_formatted("qty") }} {{ item.uom or "" }}
        </td>
        <td align="right" style="padding:8px 10px;border-bottom:1px solid #e5e7eb;" valign="top">{{ money(item.rate) }}</td>
        <td align="right" style="padding:8px 10px;border-bottom:1px solid #e5e7eb;" valign="top">{{ money(item.amount) }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <!-- TOTALS -->
  <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px;">
    <tr>
      <td width="55%" valign="top">
        {% if doc.in_words %}
        <div style="font-size:11px;color:#666;">{{ _("Amount in words") }}</div>
        <div style="font-weight:600;">{{ doc.in_words }}</div>
        {% endif %}
      </td>
      <td width="45%" valign="top">
        <table width="100%" cellpadding="0" cellspacing="0" style="font-size:12px;">
          <tr><td style="padding:4px 10px;">{{ _("Subtotal") }}</td>
              <td align="right" style="padding:4px 10px;">{{ money(doc.net_total) }}</td></tr>
          {% if doc.discount_amount %}
          <tr><td style="padding:4px 10px;">{{ _("Discount") }}</td>
              <td align="right" style="padding:4px 10px;">- {{ money(doc.discount_amount) }}</td></tr>
          {% endif %}
          {% for tax in doc.taxes %}
          {% if tax.tax_amount %}
          <tr><td style="padding:4px 10px;">{{ tax.account_head }}</td>
              <td align="right" style="padding:4px 10px;">{{ money(tax.tax_amount) }}</td></tr>
          {% endif %}
          {% endfor %}
          <tr>
            <td style="background:#111;color:#fff;font-weight:700;padding:8px 10px;">{{ _("Grand Total") }}</td>
            <td align="right" style="background:#111;color:#fff;font-weight:700;padding:8px 10px;">{{ money(doc.rounded_total or doc.grand_total) }}</td>
          </tr>
          {% if doc.outstanding_amount is not none and doc.outstanding_amount != (doc.rounded_total or doc.grand_total) %}
          <tr style="font-weight:700;">
            <td style="padding:4px 10px;">{{ _("Balance Due") }}</td>
            <td align="right" style="padding:4px 10px;">{{ money(doc.outstanding_amount) }}</td>
          </tr>
          {% endif %}
        </table>
      </td>
    </tr>
  </table>

  <!-- BANK DETAILS -->
  __BANK_DETAILS__

  <!-- TERMS -->

  <!-- FOOTER -->
  <div style="margin-top:30px;text-align:center;border-top:1px solid #e5e7eb;padding-top:14px;">
    <div style="font-size:11px;color:#6b7280;margin-bottom:10px;">{{ _("Thank you for your business.") }}</div>
    __SOCIAL_LINKS__
  </div>
</div>
"""


def remove_other_sales_invoice_print_formats():
    """Only Verp Sales Invoice should exist for Sales Invoice. Frappe's own
    (standard) formats can't be deleted, so they are disabled instead - and
    any custom ones are deleted outright."""
    others = frappe.get_all(
        "Print Format",
        filters={
            "doc_type": "Sales Invoice",  # never another doctype's formats
            "name": ["!=", SALES_INVOICE_PRINT_FORMAT],
        },
        fields=["name", "standard"],
    )
    for pf in others:
        frappe.delete_doc("Print Format", pf.name, ignore_permissions=True, force=True)


def seed_sales_invoice_print_format(make_default=False, raise_on_error=False):
    """
    Build and sync the 'Verp Sales Invoice' print format with current branding
    and bank accounts. Safe to call repeatedly (migrate, after_install,
    on_update of the config doctype).
    """
    try:
        branding = get_email_branding()

        logo_url = branding["logo_url"]
        company_name = escape_html(branding["company_name"] or "")

        logo_block = (
            f'<img src="{escape_html(logo_url)}" alt="{company_name}" '
            f'style="max-height:56px;max-width:180px;display:block;">'
            if logo_url
            else ""
        )

        html = (
            SALES_INVOICE_TEMPLATE.replace("__LOGO_BLOCK__", logo_block)
            .replace("__COMPANY_NAME__", company_name)
            .replace("__SOCIAL_LINKS__", branding["social_links_html"])
            .replace("__BANK_DETAILS__", DUMMY_BANK_DETAILS)
        )

        changed = upsert_print_format(
            SALES_INVOICE_PRINT_FORMAT,
            "Sales Invoice",
            html,
            make_default=True,
        )
        remove_other_sales_invoice_print_formats()
        return changed
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Sales Invoice Print Format Seed")
        if raise_on_error:
            raise

import frappe
import json
import re

SERVICE_DOCTYPE_MAP = {
    "ruc": "RUC",
    "resume": "Resume",
    "jdc": "JDC",
    "training": "Training",
    "cover letter": "Cover Letter",
    "marketing": "Marketing",
    "cr": "CR",
    "onboarding": "Onboarding",
}


ROLES = [
    "Lead Master Manager",
    "Lead Manager",
    "Lead Team Lead",
    "Lead Person",
    "Sales Team Lead",
    "Sales Person",
    "Sales Manager",
    "Sales Master Manager",
    "Marketing Master Manager",
    "Marketing Manager",
    "Marketing Team Lead",
    "Senior Recruiter",
    "Marketing Mentor",
    "Recruiter",
    "Senior Resume Person",
    "Resume Person",
    "Technical Coordinator",
    "Technical Manager",
    "Technical Master Manager",
    "HR Manager",
    "HR",
    "OnBoarding Person",
    "CR",
    "Account Person",
    "_show_setup",
    "_show_accounting",
    "_show_sidebar_master",
    "_show_role_permission_manager",
    "Technical Person",
]

PERM_FIELDS = [
    "select",
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
]

ROLE_PERMISSIONS = {
    "Inbox User": {
        "Communication": ["read", "create", "email"],
        "Email Account": ["read"],
    },
    "_show_sidebar_master": {
        "Sidebar Master": ["select", "read", "write", "create"],
        "Comment": ["select", "read", "create", "write", "delete"],
        "File": ["select", "read", "create", "write"],
    },
    "HR": {
        "User": ["select", "read", "write", "create"],
        "Role": ["select", "read", "write", "create"],
    },
    "HR Manager": {
        "User": ["select", "read", "write", "create"],
        "Role": ["select", "read", "write", "create"],
    },
}


DEPARTMENTS_ROLES = {
    "Lead": ["Lead Master Manager", "Lead Manager", "Lead Team Lead", "Lead Person"],
    "Sales": [
        "Sales Master Manager",
        "Sales Manager",
        "Sales Team Lead",
        "Sales Person",
    ],
    "Marketing": [
        "Marketing Master Manager",
        "Marketing Manager",
        "Marketing Team Lead",
        "Senior Recruiter",
        "Marketing Mentor",
        "Recruiter",
    ],
    "Resume": ["Senior Resume Person", "Resume Person"],
    "Technical": [
        "Technical Coordinator",
        "Technical Manager",
        "Technical Person",
        "Technical Master Manager",
    ],
    "HR": ["HR Manager", "HR"],
    "CR": ["CR"],
    "Onboarding": ["OnBoarding Person"],
    "Accounting": ["Account Person"],
}

HIERARCHY_DATA = [
    {
        "department": "Lead",
        "role_hierarchy_json": [
            {"parent_role": "Lead Master Manager", "child_roles": ["Lead Manager"]},
            {"parent_role": "Lead Manager", "child_roles": ["Lead Team Lead"]},
            {"parent_role": "Lead Team Lead", "child_roles": ["Lead Person"]},
        ],
        "auto_assign_config": {"role": "Lead Person"},
    },
    {
        "department": "Sales",
        "role_hierarchy_json": [
            {"parent_role": "Sales Master Manager", "child_roles": ["Sales Manager"]},
            {"parent_role": "Sales Manager", "child_roles": ["Sales Team Lead"]},
            {"parent_role": "Sales Team Lead", "child_roles": ["Sales Person"]},
        ],
        "auto_assign_config": {"role": "Sales Manager"},
    },
    {
        "department": "Marketing",
        "role_hierarchy_json": [
            {
                "parent_role": "Marketing Master Manager",
                "child_roles": ["Marketing Manager"],
            },
            {
                "parent_role": "Marketing Manager",
                "child_roles": ["Marketing Team Lead"],
            },
            {"parent_role": "Marketing Team Lead", "child_roles": ["Senior Recruiter"]},
            {"parent_role": "Senior Recruiter", "child_roles": ["Marketing Mentor"]},
            {"parent_role": "Marketing Mentor", "child_roles": ["Recruiter"]},
        ],
        "auto_assign_config": {"role": "Marketing Manager"},
    },
    {
        "department": "Resume",
        "role_hierarchy_json": [
            {"parent_role": "Senior Resume Person", "child_roles": ["Resume Person"]},
        ],
        "auto_assign_config": {"role": "Senior Resume Person"},
    },
    {
        "department": "Technical",
        "role_hierarchy_json": [
            {
                "parent_role": "Technical Master Manager",
                "child_roles": ["Technical Manager"],
            },
            {
                "parent_role": "Technical Manager",
                "child_roles": ["Technical Coordinator"],
            },
            {
                "parent_role": "Technical Coordinator",
                "child_roles": ["Technical Person"],
            },
        ],
        "auto_assign_config": {"role": "Technical Coordinator"},
    },
    {
        "department": "HR",
        "role_hierarchy_json": [
            {"parent_role": "HR Manager", "child_roles": ["HR"]},
        ],
        "auto_assign_config": {"role": "HR Manager"},
    },
    {
        "department": "CR",
        "role_hierarchy_json": [
            {"parent_role": "CR", "child_roles": []},
        ],
        "auto_assign_config": {"role": "CR"},
    },
    {
        "department": "Onboarding",
        "role_hierarchy_json": [
            {"parent_role": "OnBoarding Person", "child_roles": []},
        ],
        "auto_assign_config": {"role": "OnBoarding Person"},
    },
    {
        "department": "Accounting",
        "role_hierarchy_json": [
            {"parent_role": "Account Person", "child_roles": []},
        ],
        "auto_assign_config": {"role": "Account Person"},
    },
]

FORM_TOURS = {
    "Lead": {
        "title": "Lead",
        "steps": [
            {
                "title": "Lead Name",
                "fieldname": "name1",
                "description": "Enter the full name of the lead.",
                "position": "Top",
                "label": "Full Name",
                "fieldtype": "Data",
            }
        ],
    },
    "Opportunity": {
        "title": "Opportunity",
        "steps": [
            {
                "title": "Opportunity From Lead",
                "fieldname": "opportunity_from_lead",
                "description": "Choose an existing lead and convert it into an opportunity.",
                "position": "Top",
                "label": "Opportunity From Lead",
                "fieldtype": "Link",
            },
            {
                "title": "Select the customer who referred this opportunity",
                "fieldname": "referral_customer",
                "description": "Choose the customer who referred this opportunity.",
                "position": "Top",
                "label": "Referral Customer",
                "fieldtype": "Link",
            },
        ],
    },
    "Resume": {
        "title": "Resume",
        "steps": [
            {
                "title": "Select Customer",
                "fieldname": "customer",
                "description": "Select the customer for whom you want to create a resume.",
                "position": "Top",
                "label": "Customer",
                "fieldtype": "Link",
            },
            {
                "title": "Select Employee",
                "fieldname": "assign_to",
                "description": "Select the employee to whom you want to assign this resume.",
                "position": "Top",
                "label": "Assign To",
                "fieldtype": "Link",
            },
            {
                "title": "Select Status",
                "fieldname": "status",
                "description": "Select the status of this resume process.",
                "position": "Top",
                "label": "Status",
                "fieldtype": "Select",
            },
            {
                "title": "Upload Resume",
                "fieldname": "resume",
                "description": "Upload the resume you created for this customer.",
                "position": "Top",
                "label": "Upload Resume",
                "fieldtype": "Attach",
            },
        ],
    },
    "Marketing": {
        "title": "Marketing",
        "steps": [
            {
                "title": "Select Customer",
                "fieldname": "customer",
                "description": "Select the customer for whom you want to do marketing.",
                "position": "Right Center",
                "label": "Customer",
                "fieldtype": "Link",
            },
            {
                "title": "Select Employee",
                "fieldname": "assign_to",
                "description": "Select an employee for marketing activities for this customer.",
                "position": "Right Center",
                "label": "Assign To",
                "fieldtype": "Link",
            },
        ],
    },
    "RUC": {
        "title": "RUC",
        "steps": [
            {
                "title": "Select Customer",
                "fieldname": "customer",
                "description": "Select the customer for whom you want to conduct a resume understanding session.",
                "position": "Top",
                "label": "Customer",
                "fieldtype": "Link",
            },
            {
                "title": "Select Employee",
                "fieldname": "assign_to",
                "description": "Select the employee to whom you want to assign this resume understanding session.",
                "position": "Top",
                "label": "Assign To",
                "fieldtype": "Link",
            },
            {
                "title": "Select Status",
                "fieldname": "status",
                "description": "Select the status of this resume understanding session.",
                "position": "Top",
                "label": "Assiged To",
                "fieldtype": "Select",
            },
            {
                "title": "Select Outsource Person",
                "fieldname": "outsource",
                "description": "Select an outsourced person if no employee is available for this session.",
                "position": "Top",
                "label": "Outsource Person",
                "fieldtype": "Link",
            },
            {
                "title": "Fill Session details",
                "fieldname": "session_details",
                "description": "Fill the session details if it's completed.",
                "position": "Top",
                "label": "Session Details",
                "fieldtype": "Table",
            },
        ],
    },
    "Sales Order": {
        "title": "Sales Order",
        "steps": [
            {
                "title": "Select Customer",
                "fieldname": "customer",
                "description": "Choose the customer for whom this sales order is being created.",
                "position": "Top",
                "label": "Customer",
                "fieldtype": "Link",
            },
            {
                "title": "Select Company",
                "fieldname": "company",
                "description": "Select the company responsible for processing and managing this sales order.",
                "position": "Right Center",
                "label": "Company",
                "fieldtype": "Link",
            },
            {
                "title": "Select Currency",
                "fieldname": "currency",
                "description": "Choose the currency in which the sales order will be issued.",
                "position": "Right Center",
                "label": "Currency",
                "fieldtype": "Link",
            },
            {
                "title": "Set Exchange Rate",
                "fieldname": "conversion_rate",
                "description": "Enter the exchange rate between the selected currency and the company's base currency.",
                "position": "Right Center",
                "label": "Exchange Rate",
                "fieldtype": "Float",
            },
            {
                "title": "Add Items",
                "fieldname": "items",
                "description": "<b>How to add items:</b><br>1. Click <b>Add Row</b> to add a new item.<br>2. Select the item to be sold.<br>3. Enter the quantity.<br>4. Update the rate.<br>5. Review the calculated amount for each row.<br>6. Repeat for all items included in this sales order.",
                "position": "Top",
                "label": "Items",
                "fieldtype": "Table",
            },
            {
                "title": "Configure Taxes and Charges",
                "fieldname": "taxes",
                "description": "<b>How to add taxes and charges:</b><br>1. Click <b>Add Row</b> to create a tax entry.<br>2. Select the tax type.<br>3. Choose the appropriate account.<br>4. Enter either the tax rate (%) or tax amount.<br>5. Review the calculated tax values before proceeding.",
                "position": "Top",
                "label": "Taxes and Charges",
                "fieldtype": "Table",
            },
            {
                "title": "Apply Additional Discount",
                "fieldname": "additional_discount_percentage",
                "description": "Enter the discount percentage to be applied to the sales order total.",
                "position": "Top",
                "label": "Additional Discount Percentage",
                "fieldtype": "Float",
            },
            {
                "title": "Select Discount Account",
                "fieldname": "additional_discount_account",
                "description": "Choose the accounting ledger where the additional discount amount will be recorded.",
                "position": "Top",
                "label": "Discount Account",
                "fieldtype": "Link",
            },
            {
                "title": "Agreement and Terms",
                "fieldname": "agreement_html",
                "description": "1. Review the sales order details and applicable terms.<br>2. Verify pricing, taxes, and discounts before submission.<br>3. Ensure all customer information is correct.<br>4. Save the sales order to continue processing.",
                "position": "Bottom",
                "label": "Session Details",
                "fieldtype": "HTML",
            },
            {
                "title": "Configure Payment Terms",
                "fieldname": "payment_terms",
                "description": "<b>How to define payment terms:</b><br>1. Click <b>Add Row</b> to create a payment schedule.<br>2. Select the payment condition or term type.<br>3. Enter the number of days based on the selected condition.<br>4. Specify the start date.<br>5. Verify the calculated due date.<br>6. Enter the payment amount or percentage.<br>7. Review the payment status and schedule before saving.",
                "position": "Top",
                "label": "Payment Terms",
                "fieldtype": "Table",
            },
        ],
    },
    "Sales Invoice": {
        "title": "Sales Invoice",
        "steps": [
            {
                "title": "Select Customer",
                "fieldname": "customer",
                "description": "Choose the customer for whom this sales invoice is being created.",
                "position": "Top",
                "label": "Customer",
                "fieldtype": "Link",
            },
            {
                "title": "Select Company",
                "fieldname": "company",
                "description": "Select the company responsible for processing and managing this sales invoice.",
                "position": "Right Center",
                "label": "Company",
                "fieldtype": "Link",
            },
            {
                "title": "Select Sales Order",
                "fieldname": "sales_order",
                "description": "Select an existing sales order to create this sales invoice against.",
                "position": "Right Center",
                "label": "Sales Order",
                "fieldtype": "Link",
            },
            {
                "title": "Set Payment Due Date",
                "fieldname": "due_date",
                "description": "Specify the date by which payment is expected from the customer for this transaction.",
                "position": "Right Center",
                "label": "Payment Due Date",
                "fieldtype": "Date",
            },
            {
                "title": "Select Currency",
                "fieldname": "currency",
                "description": "Choose the currency in which the sales order will be issued.",
                "position": "Right Center",
                "label": "Currency",
                "fieldtype": "Link",
            },
            {
                "title": "Set Exchange Rate",
                "fieldname": "conversion_rate",
                "description": "Enter the exchange rate between the selected currency and the company's base currency.",
                "position": "Right Center",
                "label": "Exchange Rate",
                "fieldtype": "Float",
            },
            {
                "title": "Add Items",
                "fieldname": "items",
                "description": "<b>How to add items:</b><br>1. Click <b>Add Row</b> to add a new item.<br>2. Select the item to be sold.<br>3. Enter the quantity.<br>4. Update the rate.<br>5. Review the calculated amount for each row.<br>6. Repeat for all items included in this sales order.",
                "position": "Top",
                "label": "Items",
                "fieldtype": "Table",
            },
            {
                "title": "Configure Taxes and Charges",
                "fieldname": "taxes",
                "description": "<b>How to add taxes and charges:</b><br>1. Click <b>Add Row</b> to create a tax entry.<br>2. Select the tax type.<br>3. Choose the appropriate account.<br>4. Enter either the tax rate (%) or tax amount.<br>5. Review the calculated tax values before proceeding.",
                "position": "Top",
                "label": "Taxes and Charges",
                "fieldtype": "Table",
            },
            {
                "title": "Apply Additional Discount",
                "fieldname": "additional_discount_percentage",
                "description": "Enter the discount percentage to be applied to the sales order total.",
                "position": "Top",
                "label": "Additional Discount Percentage",
                "fieldtype": "Float",
            },
            {
                "title": "Select Discount Account",
                "fieldname": "additional_discount_account",
                "description": "Choose the accounting ledger where the additional discount amount will be recorded.",
                "position": "Top",
                "label": "Discount Account",
                "fieldtype": "Link",
            },
        ],
    },
    "Purchase Order": {
        "title": "Purchase Order",
        "steps": [
            {
                "title": "Select Supplier",
                "fieldname": "supplier",
                "description": "Choose the supplier from whom this purchase order is being created.",
                "position": "Top",
                "label": "Supplier",
                "fieldtype": "Link",
            },
            {
                "title": "Select Company",
                "fieldname": "company",
                "description": "Select the company responsible for processing and managing this purchase order.",
                "position": "Right Center",
                "label": "Company",
                "fieldtype": "Link",
            },
            {
                "title": "Select Currency",
                "fieldname": "currency",
                "description": "Choose the currency in which the purchase order will be issued.",
                "position": "Right Center",
                "label": "Currency",
                "fieldtype": "Link",
            },
            {
                "title": "Set Exchange Rate",
                "fieldname": "conversion_rate",
                "description": "Enter the exchange rate between the selected currency and the company's base currency.",
                "position": "Right Center",
                "label": "Exchange Rate",
                "fieldtype": "Float",
            },
            {
                "title": "Add Items",
                "fieldname": "items",
                "description": "<b>How to add items:</b><br>1. Click <b>Add Row</b> to add a new item.<br>2. Select the item to be sold.<br>3. Enter the quantity.<br>4. Update the rate.<br>5. Review the calculated amount for each row.<br>6. Repeat for all items included in this sales order.",
                "position": "Top",
                "label": "Items",
                "fieldtype": "Table",
            },
            {
                "title": "Configure Taxes and Charges",
                "fieldname": "taxes",
                "description": "<b>How to add taxes and charges:</b><br>1. Click <b>Add Row</b> to create a tax entry.<br>2. Select the tax type.<br>3. Choose the appropriate account.<br>4. Enter either the tax rate (%) or tax amount.<br>5. Review the calculated tax values before proceeding.",
                "position": "Top",
                "label": "Taxes and Charges",
                "fieldtype": "Table",
            },
            {
                "title": "Apply Additional Discount",
                "fieldname": "additional_discount_percentage",
                "description": "Enter the discount percentage to be applied to the purchase order total.",
                "position": "Top",
                "label": "Additional Discount Percentage",
                "fieldtype": "Float",
            },
            {
                "title": "Select Discount Account",
                "fieldname": "additional_discount_account",
                "description": "Choose the accounting ledger where the additional discount amount will be recorded.",
                "position": "Top",
                "label": "Discount Account",
                "fieldtype": "Link",
            },
        ],
    },
    "Purchase Invoice": {
        "title": "Purchase Invoice",
        "steps": [
            {
                "title": "Select Supplier",
                "fieldname": "supplier",
                "description": "Choose the supplier from whom this purchase invoice is being created.",
                "position": "Top",
                "label": "Supplier",
                "fieldtype": "Link",
            },
            {
                "title": "Select Company",
                "fieldname": "company",
                "description": "Select the company responsible for processing and managing this purchase invoice.",
                "position": "Right Center",
                "label": "Company",
                "fieldtype": "Link",
            },
            {
                "title": "Select Purchase Order",
                "fieldname": "purchase_order",
                "description": "Select an existing purchase order to create this purchase invoice against.",
                "position": "Right Center",
                "label": "Purchase Order",
                "fieldtype": "Link",
            },
            {
                "title": "Set Payment Due Date",
                "fieldname": "due_date",
                "description": "Specify the date by which payment is expected from the customer for this transaction.",
                "position": "Right Center",
                "label": "Payment Due Date",
                "fieldtype": "Date",
            },
            {
                "title": "Select Currency",
                "fieldname": "currency",
                "description": "Choose the currency in which the purchase order will be issued.",
                "position": "Right Center",
                "label": "Currency",
                "fieldtype": "Link",
            },
            {
                "title": "Set Exchange Rate",
                "fieldname": "conversion_rate",
                "description": "Enter the exchange rate between the selected currency and the company's base currency.",
                "position": "Right Center",
                "label": "Exchange Rate",
                "fieldtype": "Float",
            },
            {
                "title": "Add Items",
                "fieldname": "items",
                "description": "<b>How to add items:</b><br>1. Click <b>Add Row</b> to add a new item.<br>2. Select the item to be sold.<br>3. Enter the quantity.<br>4. Update the rate.<br>5. Review the calculated amount for each row.<br>6. Repeat for all items included in this sales order.",
                "position": "Top",
                "label": "Items",
                "fieldtype": "Table",
            },
            {
                "title": "Configure Taxes and Charges",
                "fieldname": "taxes",
                "description": "<b>How to add taxes and charges:</b><br>1. Click <b>Add Row</b> to create a tax entry.<br>2. Select the tax type.<br>3. Choose the appropriate account.<br>4. Enter either the tax rate (%) or tax amount.<br>5. Review the calculated tax values before proceeding.",
                "position": "Top",
                "label": "Taxes and Charges",
                "fieldtype": "Table",
            },
            {
                "title": "Apply Additional Discount",
                "fieldname": "additional_discount_percentage",
                "description": "Enter the discount percentage to be applied to the purchase order total.",
                "position": "Top",
                "label": "Additional Discount Percentage",
                "fieldtype": "Float",
            },
            {
                "title": "Select Discount Account",
                "fieldname": "additional_discount_account",
                "description": "Choose the accounting ledger where the additional discount amount will be recorded.",
                "position": "Top",
                "label": "Discount Account",
                "fieldtype": "Link",
            },
        ],
    },
    "Journal Entry": {
        "title": "Journal Entry",
        "steps": [
            {
                "title": "Select Entry Type",
                "fieldname": "voucher_type",
                "description": "Choose the type of Journal Entry you want to create. The selected entry type determines how the transaction will be recorded in the accounting system.",
                "position": "Top",
                "label": "Entry Type",
                "fieldtype": "Select",
            },
            {
                "title": "Select Company",
                "fieldname": "company",
                "description": "Select the company for which this Journal Entry is being created. All accounting transactions will be recorded under the selected company.",
                "position": "Right Center",
                "label": "Company",
                "fieldtype": "Link",
            },
            {
                "title": "Set Posting Date",
                "fieldname": "posting_date",
                "description": "Specify the posting date for this Journal Entry. This date determines the accounting period in which the transaction will be recorded.",
                "position": "Right Center",
                "label": "Payment Due Date",
                "fieldtype": "Date",
            },
            {
                "title": "Add Accounting Entries",
                "fieldname": "accounts",
                "description": """
                <div>
                    <b>How to add accounting entries:</b>
                    <ol style="margin-top: 8px; padding-left: 20px;">
                        <li>Click <b>Add Row</b> to create a new accounting line.</li>
                        <li>Select the <b>Account</b> to be debited or credited.</li>
                        <li>If applicable, choose the <b>Party Type</b> and <b>Party</b>.</li>
                        <li>Enter the <b>Debit</b> or <b>Credit</b> amount.</li>
                        <li>Ensure that the total Debit amount equals the total Credit amount before saving.</li>
                    </ol>
                    <p style="margin-top: 8px;">
                        <b>Note:</b> A Journal Entry can only be submitted when it is balanced.
                    </p>
                </div>
            """,
                "position": "Top",
                "label": "Accounting Entries",
                "fieldtype": "Table",
            },
        ],
    },
    "Payment Entry": {
        "title": "Payment Entry",
        "steps": [
            {
                "title": "Select Payment Type",
                "fieldname": "payment_type",
                "description": "Choose the type of payment type. Select Receive for incoming payments, Pay for outgoing payments, or Internal Transfer to move funds between company accounts.",
                "position": "Top",
                "label": "Payment Type",
                "fieldtype": "Select",
            },
            {
                "title": "Set Posting Date",
                "fieldname": "posting_date",
                "description": "Specify the posting date for this Payment Entry. This date determines the accounting period in which the transaction will be recorded.",
                "position": "Right Center",
                "label": "Posting Date",
                "fieldtype": "Date",
            },
            {
                "title": "Select Company",
                "fieldname": "company",
                "description": "Select the company for which this Payment Entry is being created. All accounting transactions associated with this payment will be recorded under the selected company.",
                "position": "Right Center",
                "label": "Company",
                "fieldtype": "Link",
            },
            {
                "title": "Select Party Type",
                "fieldname": "party_type",
                "description": "Choose the category of party involved in this transaction, such as Customer, Supplier, or other supported party types.",
                "position": "Top",
                "label": "Party Type",
                "fieldtype": "Link",
            },
            {
                "title": "Select Source Account",
                "fieldname": "paid_from",
                "description": "Select the account from which the payment amount will be deducted. This is typically a bank or cash account for outgoing payments or transfers.",
                "position": "Top",
                "label": "Account Paid From",
                "fieldtype": "Dynamic Link",
            },
            {
                "title": "Select Destination Account",
                "fieldname": "paid_to",
                "description": "Select the account that will receive the payment amount. This is typically a bank, cash, or party-related account depending on the payment type.",
                "position": "Top",
                "label": "Account Paid To",
                "fieldtype": "Link",
            },
            {
                "title": "Select Party",
                "fieldname": "party",
                "description": "Based on the selected Party Type, choose the specific Customer, Supplier, Employee, or other party involved in this transaction.",
                "position": "Top",
                "label": "Party",
                "fieldtype": "Dynamic Link",
            },
            {
                "title": "Select Currency",
                "fieldname": "currency",
                "description": "Choose the currency in which the payment is being made or received.",
                "position": "Right Center",
                "label": "Currency",
                "fieldtype": "Link",
            },
            {
                "title": "Set Exchange Rate",
                "fieldname": "conversion_rate",
                "description": "Enter or verify the exchange rate used to convert the selected currency into the company's base currency for accounting purposes.",
                "position": "Right Center",
                "label": "Exchange Rate",
                "fieldtype": "Float",
            },
            {
                "title": "Configure Taxes and Charges",
                "fieldname": "taxes",
                "description": "<b>How to add taxes and charges:</b><br>1. Click <b>Add Row</b> to create a tax entry.<br>2. Select the tax type.<br>3. Choose the appropriate account.<br>4. Enter either the tax rate (%) or tax amount.<br>5. Review the calculated tax values before proceeding.",
                "position": "Top",
                "label": "Taxes and Charges",
                "fieldtype": "Table",
            },
        ],
    },
    "Employee": {
        "title": "Employee",
        "steps": [
            {
                "title": "Select User",
                "fieldname": "user",
                "description": "Select the user for whom you want to create a employee.",
                "position": "Right Center",
                "label": "Session Details",
                "fieldtype": "HTML",
            },
            {
                "title": "Enter Department Details",
                "fieldname": "employee_assignment_details_table",
                "description": "Click <b>Add Row</b>, then Enter the department, designation, and reporting employee for the employee being created",
                "position": "Bottom",
                "label": "Employee Assignment Details Table",
                "fieldtype": "HTML",
            },
        ],
    },
    "Interview": {
        "title": "Interview",
        "steps": [
            {
                "title": "Select Customer",
                "fieldname": "marketing_link",
                "description": "Select the customer for whom you want to create an interview.",
                "position": "Right Center",
                "label": "Marketing",
                "fieldtype": "Link",
            },
            {
                "title": "Company Name ",
                "fieldname": "company",
                "description": "Select the company name for the interview.",
                "position": "Right Center",
                "label": "Company",
                "fieldtype": "Data",
            },
            {
                "title": "Interview Role",
                "fieldname": "role",
                "description": "Enter the role for which the interview is scheduled.",
                "position": "Right Center",
                "label": "Role",
                "fieldtype": "Data",
            },
        ],
    },
    "Pdf Agreement Template": {
        "title": "PDF Agreement Template",
        "steps": [
            {
                "title": "Template Name",
                "fieldname": "title",
                "description": "Enter unique template name.",
                "position": "Right Center",
                "label": "Template Name",
                "fieldtype": "Data",
            },
            {
                "title": "Upload Template",
                "fieldname": "upload_pdf_template",
                "description": "Upload the <b>Agreement</b> template PDF.",
                "position": "Right Center",
                "label": "Upload PDF Template",
                "fieldtype": "Attach",
            },
            {
                "title": "Is Template Active",
                "fieldname": "is_active",
                "description": "Select the checkbox to <b>activate</b> the current template.",
                "position": "Right Center",
                "label": "Is Active",
                "fieldtype": "Check",
            },
            {
                "title": "Build Template",
                "fieldname": "builder_html",
                "description": "1. Click the button which you wantr to add in template from the right side of section having name <strong>Fields</strong><br/>2. click on the template pdf where want to place the selected field<br/>3. enter the field name in that dialog<br/>4. manage teh size of created field<br/>5. repeat step untill all fields got add<br/>6. At last click <strong>Save Template</strong> Button under <strong>Fields<strong> section to save the created template",
                "position": "Top",
                "label": "Build Template",
                "fieldtype": "HTML",
            },
        ],
    },
    "Customer": {
        "title": "Customer",
        "steps": [
            {
                "title": "Enter Customer Name",
                "fieldname": "name1",
                "description": "Provide the official name of the customer. This will be used across all transactions and records.",
                "position": "Right Center",
                "label": "Customer Name",
                "fieldtype": "Data",
            },
            {
                "title": "Select Customer Source",
                "fieldname": "customer_from",
                "description": "Choose where this customer originated from. Select <b>Lead</b> or <b>Opportunity</b>.",
                "position": "Right Center",
                "label": "Customer From",
                "fieldtype": "Link",
            },
            {
                "title": "Link the Source Record",
                "fieldname": "party_name",
                "description": "Based on the selected source, choose the relevant record. Only matching <b>Leads</b> or <b>Opportunities</b> will be shown.",
                "position": "Right Center",
                "label": "Party",
                "fieldtype": "Dynamic Link",
            },
        ],
    },
    "Company": {
        "title": "Company",
        "steps": [
            {
                "title": "Enter Company Name",
                "fieldname": "company_name",
                "description": "Provide the official name of the company. This name will be used across all transactions and records.",
                "position": "Right Center",
                "label": "Company",
                "fieldtype": "Data",
            },
            {
                "title": "Enter Company Abbreviation",
                "fieldname": "abbr",
                "description": "Provide a short abbreviation or code for the company. This helps identify the company in records and reports.",
                "position": "Right Center",
                "label": "Abbr",
                "fieldtype": "Data",
            },
            {
                "title": "Select Default Currency",
                "fieldname": "default_currency",
                "description": "Choose the default currency that will be used for transactions associated with this company.",
                "position": "Right Center",
                "label": "Default Currency",
                "fieldtype": "Link",
            },
            {
                "title": "Select Company Country",
                "fieldname": "country",
                "description": "Select the country in which the company operates or is registered.",
                "position": "Right Center",
                "label": "Country",
                "fieldtype": "Link",
            },
            {
                "title": "Mark as Group Company",
                "fieldname": "is_group",
                "description": "Enable this option if the company acts as a parent or group company containing multiple subsidiary companies.",
                "position": "Right Center",
                "label": "Is Group",
                "fieldtype": "Check",
            },
            {
                "title": "Select Parent Company",
                "fieldname": "parent_company",
                "description": "If this company belongs to a group, select its parent company from the list.",
                "position": "Top",
                "label": "Parent Company",
                "fieldtype": "Link",
            },
        ],
    },
    "Fiscal Year": {
        "title": "Fiscal Year",
        "steps": [
            {
                "title": "Enter Fiscal Year Name",
                "fieldname": "year",
                "description": "Enter the fiscal year name, for example, 2025 or 2025-26.",
                "position": "Right Center",
                "label": "Year Name",
                "fieldtype": "Data",
            },
            {
                "title": "Select Start Date",
                "fieldname": "year_start_date",
                "description": "Choose the date on which the fiscal year begins.",
                "position": "Right Center",
                "label": "Year Start Date",
                "fieldtype": "Date",
            },
            {
                "title": "Select End Date",
                "fieldname": "year_end_date",
                "description": "Choose the date on which the fiscal year ends.",
                "position": "Right Center",
                "label": "Year End Date",
                "fieldtype": "Date",
            },
            {
                "title": "Select Included Companies",
                "fieldname": "included_companies",
                "description": "Choose the companies that will be associated with this fiscal year.",
                "position": "Right Center",
                "label": "Included Companies",
                "fieldtype": "Table MultiSelect",
            },
            {
                "title": "Mark Fiscal Year as Inactive",
                "fieldname": "disabled",
                "description": "Enable this option to deactivate the fiscal year and prevent it from being used in future transactions.",
                "position": "Right Center",
                "label": "Disabled",
                "fieldtype": "Check",
            },
        ],
    },
    "Accounts Settings": {
        "title": "Accounts Settings",
        "steps": [
            {
                "title": "Select Default Company",
                "fieldname": "default_company",
                "description": "Choose the default company that will be automatically used in accounting transactions such as orders, invoices, and vouchers.",
                "position": "Right Center",
                "label": "Default Company",
                "fieldtype": "Link",
            },
            {
                "title": "Show Account Balances",
                "fieldname": "show_balance_in_coa",
                "description": "Enable this option to display account balances in the Chart of Accounts.",
                "position": "Right Center",
                "label": "Show Balances in Chart Of Accounts",
                "fieldtype": "Check",
            },
            {
                "title": "Enable Automatic Invoice Emailing",
                "fieldname": "auto_send_sales_invoice_after_submission",
                "description": "Enable this option to automatically send Sales Invoices to customers after they are submitted.",
                "position": "Right Center",
                "label": "Auto Send Sales Invoice After Submission",
                "fieldtype": "Check",
            },
            {
                "title": "Set Invoice Reminder Days",
                "fieldname": "invoice_reminder_days",
                "description": "Specify the number of days before the due date when invoice payment reminders should be sent.",
                "position": "Right Center",
                "label": "Invoice Reminder Days",
                "fieldtype": "Int",
            },
        ],
    },
    "Bank Account": {
        "title": "Bank Account",
        "steps": [
            {
                "title": "Enter Account Name",
                "fieldname": "account_name",
                "description": "Provide a unique and descriptive name for the bank account.",
                "position": "Right Center",
                "label": "Account Name",
                "fieldtype": "Data",
            },
            {
                "title": "Select Bank",
                "fieldname": "bank",
                "description": "Choose the bank associated with this account.",
                "position": "Right Center",
                "label": "Bank",
                "fieldtype": "Link",
            },
            {
                "title": "Select Account Type",
                "fieldname": "account_type",
                "description": "Choose the type of bank account, such as Savings, Current, or Cash.",
                "position": "Right Center",
                "label": "Account Type",
                "fieldtype": "Link",
            },
            {
                "title": "Select Account Subtype",
                "fieldname": "account_subtype",
                "description": "Choose the appropriate subtype for the selected account type, if applicable.",
                "position": "Right Center",
                "label": "Account Subtype",
                "fieldtype": "Link",
            },
            {
                "title": "Mark as Company Account",
                "fieldname": "is_company_account",
                "description": "Enable this option if the account belongs to the company. This is required for bank reconciliation.",
                "position": "Right Center",
                "label": "Is Company Account",
                "fieldtype": "Check",
            },
            {
                "title": "Select Company",
                "fieldname": "company",
                "description": "Choose the company that owns or manages this bank account.",
                "position": "Right Center",
                "label": "Company",
                "fieldtype": "Link",
            },
            {
                "title": "Select Party Type",
                "fieldname": "party_type",
                "description": "Choose the type of party that owns this bank account, such as Customer or Shareholder.",
                "position": "Top",
                "label": "Party Type",
                "fieldtype": "Link",
            },
            {
                "title": "Select Party",
                "fieldname": "party",
                "description": "Based on the selected Party Type, choose the corresponding party from the available records.",
                "position": "Top",
                "label": "Party",
                "fieldtype": "Dynamic Link",
            },
        ],
    },
}


def after_install():
    seed_master_sidebar_config()
    seed_services_and_departments()
    setup_navbar_settings()
    seed_website_setting()
    create_interview_statuses()
    seed_sales_stages()
    seed_type_of_interview()
    create_all_roles()
    seed_employee_departments()
    assign_permissions_to_roles(ROLE_PERMISSIONS)
    seed_hierarchy()
    remove_default_workspaces()
    # seed_bulk_users_with_password()
    # seed_employees_with_hierarchy(HIERARCHY_DATA)
    seed_form_tours()
    seed_party_types()


def seed_master_sidebar_config():
    """
    Create default sidebar configuration for Master user
    if it doesn't already exist.
    """

    SIDEBAR_CONFIG = [
        {
            "key": "setup",
            "label": "Setup Guide",
            "icon": "icon-getting-started",
            "parent_type": "type_3",
            "shortcut": "",
            "roles": ["_show_setup"],
            "route": "/app/setup",
            "link_type": "page",
        },
        {
            "key": "users",
            "label": "Users",
            "icon": "icon-setting-gear",
            "parent_type": "type_2",
            "shortcut": "",
            "roles": [],
            "children": [
                {
                    "key": "user",
                    "name": "User",
                    "type": "doctype",
                    "route": "/app/user",
                    "doctype": "User",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "employee",
                    "name": "Employee",
                    "type": "doctype",
                    "route": "/app/employee",
                    "doctype": "Employee",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "outsource",
                    "name": "Outsource",
                    "type": "doctype",
                    "route": "/app/outsource",
                    "doctype": "Outsource",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "role",
                    "name": "Role",
                    "type": "doctype",
                    "route": "/app/role",
                    "doctype": "Role",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "role-permissions-manager",
                    "name": "Role Permissions Manager",
                    "type": "page",
                    "route": "/app/permission-manager",
                    "icon": "icon-assign",
                    "shortcut": "",
                    "roles": ["System Manager", "_show_role_permission_manager"],
                },
            ],
        },
        {
            "key": "staffing-master",
            "label": "Staffing Master",
            "icon": "icon-setting-gear",
            "parent_type": "type_2",
            "shortcut": "",
            "roles": [],
            "children": [
                {
                    "key": "email-domain",
                    "name": "Email Domain",
                    "type": "doctype",
                    "route": "/app/email-domain",
                    "doctype": "Email Domain",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "email-account",
                    "name": "Email Account",
                    "type": "doctype",
                    "route": "/app/email-account",
                    "doctype": "Email Account",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "department",
                    "name": "Department",
                    "type": "doctype",
                    "route": "/app/department",
                    "doctype": "Department",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "hierarchy",
                    "name": "Hierarchy",
                    "type": "doctype",
                    "route": "/app/hierarchy",
                    "doctype": "Hierarchy",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "erp-configuration",
                    "name": "ERP Configuration",
                    "type": "doctype",
                    "route": "/app/erp-configuration/ERP%20Configuration",
                    "doctype": "ERP Configuration",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "pdf-agreement-template",
                    "name": "Pdf Agreement Template",
                    "type": "doctype",
                    "route": "/app/pdf-agreement-template",
                    "doctype": "Pdf Agreement Template",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
            ],
        },
        {
            "key": "email-inbox",
            "label": "Email Inbox",
            "icon": "icon-mail",
            "parent_type": "type_3",
            "shortcut": "",
            "roles": [],
            "route": "/app/email-inbox",
            "link_type": "page",
        },
        {
            "key": "lead",
            "label": "Lead",
            "icon": "icon-setting-gear",
            "parent_type": "type_3",
            "shortcut": "",
            "roles": [],
            "route": "/app/lead",
            "link_type": "doctype",
            "doctype": "Lead",
        },
        {
            "key": "sales",
            "label": "Sales",
            "icon": "icon-setting-gear",
            "parent_type": "type_2",
            "shortcut": "",
            "roles": [],
            "children": [
                {
                    "key": "opportunity",
                    "name": "Opportunity",
                    "type": "doctype",
                    "route": "/app/opportunity",
                    "doctype": "Opportunity",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "customer",
                    "name": "Customer",
                    "type": "doctype",
                    "route": "/app/customer",
                    "doctype": "Customer",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
            ],
        },
        {
            "key": "technical",
            "label": "Technical",
            "icon": "icon-setting-gear",
            "parent_type": "type_2",
            "shortcut": "",
            "roles": [],
            "children": [
                {
                    "key": "resume",
                    "name": "Resume",
                    "type": "doctype",
                    "route": "/app/resume",
                    "doctype": "Resume",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "ruc",
                    "name": "RUC",
                    "type": "doctype",
                    "route": "/app/ruc",
                    "doctype": "RUC",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "jdc",
                    "name": "JDC",
                    "type": "doctype",
                    "route": "/app/jdc",
                    "doctype": "JDC",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "cover-letter",
                    "name": "Cover Letter",
                    "type": "doctype",
                    "route": "/app/cover-letter",
                    "doctype": "Cover Letter",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "training",
                    "name": "Training",
                    "type": "doctype",
                    "route": "/app/training",
                    "doctype": "Training",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "technical-other-services",
                    "name": "Technical Other Services",
                    "type": "doctype",
                    "route": "/app/technical-other-services",
                    "doctype": "Technical Other Services",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
            ],
        },
        {
            "key": "marketings",
            "label": "Marketings",
            "icon": "icon-setting-gear",
            "parent_type": "type_2",
            "shortcut": "",
            "roles": [],
            "children": [
                {
                    "key": "marketing",
                    "name": "Marketing",
                    "type": "doctype",
                    "route": "/app/marketing",
                    "doctype": "Marketing",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "interview",
                    "name": "Interview",
                    "type": "doctype",
                    "route": "/app/interview",
                    "doctype": "Interview",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "marketing-other-services",
                    "name": "Marketing Other Services",
                    "type": "doctype",
                    "route": "/app/marketing-other-services",
                    "doctype": "Marketing Other Services",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
            ],
        },
        {
            "key": "cr",
            "label": "CR",
            "icon": "icon-setting-gear",
            "parent_type": "type_3",
            "shortcut": "",
            "roles": [],
            "route": "/app/cr",
            "link_type": "doctype",
            "doctype": "CR",
        },
        {
            "key": "onboardings",
            "label": "Onboardings",
            "icon": "icon-setting-gear",
            "parent_type": "type_3",
            "shortcut": "",
            "roles": [],
            "route": "/app/onboardings",
            "link_type": "doctype",
            "doctype": "Onboardings",
        },
        {
            "key": "accounts-master",
            "label": "Accounts Master",
            "icon": "icon-setting-gear",
            "parent_type": "type_2",
            "shortcut": "",
            "roles": [],
            "children": [
                {
                    "key": "company",
                    "name": "Company",
                    "type": "doctype",
                    "route": "/app/company",
                    "doctype": "Company",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "fiscal-year",
                    "name": "Fiscal Year",
                    "type": "doctype",
                    "route": "/app/fiscal-year",
                    "doctype": "Fiscal Year",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "accounts-settings",
                    "name": "Accounts Settings",
                    "type": "doctype",
                    "route": "/app/accounts-settings/Accounts%20Settings",
                    "doctype": "Accounts Settings",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
            ],
        },
        {
            "key": "pending-pe-requests",
            "label": "Pending PE Requests",
            "icon": "icon-accounting",
            "parent_type": "type_3",
            "shortcut": "",
            "roles": ["System Manager", "_show_accounting"],
            "route": "/app/pending-pe-requests",
            "link_type": "page",
        },
        {
            "key": "coa",
            "label": "Chart of Accounts",
            "icon": "icon-accounting",
            "parent_type": "type_3",
            "shortcut": "",
            "roles": ["System Manager", "_show_accounting"],
            "route": "/app/account/view/tree",
            "link_type": "page",
        },
        {
            "key": "accounting",
            "label": "Accounting",
            "icon": "icon-setting-gear",
            "parent_type": "type_2",
            "shortcut": "",
            "roles": [],
            "children": [
                {
                    "key": "account",
                    "name": "Account",
                    "type": "doctype",
                    "route": "/app/account",
                    "doctype": "Account",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "bank",
                    "name": "Bank",
                    "type": "doctype",
                    "route": "/app/bank",
                    "doctype": "Bank",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "bank-account",
                    "name": "Bank Account",
                    "type": "doctype",
                    "route": "/app/bank-account",
                    "doctype": "Bank Account",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "journal-entry",
                    "name": "Journal Entry",
                    "type": "doctype",
                    "route": "/app/journal-entry",
                    "doctype": "Journal Entry",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "payment-entry",
                    "name": "Payment Entry",
                    "type": "doctype",
                    "route": "/app/payment-entry",
                    "doctype": "Payment Entry",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "purchase-invoice",
                    "name": "Purchase Invoice",
                    "type": "doctype",
                    "route": "/app/purchase-invoice",
                    "doctype": "Purchase Invoice",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "sales-invoice",
                    "name": "Sales Invoice",
                    "type": "doctype",
                    "route": "/app/sales-invoice",
                    "doctype": "Sales Invoice",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "sales-order",
                    "name": "Sales Order",
                    "type": "doctype",
                    "route": "/app/sales-order",
                    "doctype": "Sales Order",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "subscription",
                    "name": "Subscription",
                    "type": "doctype",
                    "route": "/app/subscription",
                    "doctype": "Subscription",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "subscription-plan",
                    "name": "Subscription Plan",
                    "type": "doctype",
                    "route": "/app/subscription-plan",
                    "doctype": "Subscription Plan",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "purchase-order",
                    "name": "Purchase Order",
                    "type": "doctype",
                    "route": "/app/purchase-order",
                    "doctype": "Purchase Order",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "supplier",
                    "name": "Supplier",
                    "type": "doctype",
                    "route": "/app/supplier",
                    "doctype": "Supplier",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
            ],
        },
        {
            "key": "e-sign",
            "label": "E Sign",
            "icon": "icon-setting-gear",
            "parent_type": "type_3",
            "shortcut": "",
            "roles": [],
            "route": "/app/e-sign",
            "link_type": "doctype",
            "doctype": "E Sign",
        },
        {
            "key": "items",
            "label": "Items",
            "icon": "icon-setting-gear",
            "parent_type": "type_2",
            "shortcut": "",
            "roles": [],
            "children": [
                {
                    "key": "item",
                    "name": "Item",
                    "type": "doctype",
                    "route": "/app/item",
                    "doctype": "Item",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "item-category",
                    "name": "Item Category",
                    "type": "doctype",
                    "route": "/app/item-category",
                    "doctype": "Item Category",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
                {
                    "key": "uom",
                    "name": "UOM",
                    "type": "doctype",
                    "route": "/app/uom",
                    "doctype": "UOM",
                    "icon": "icon-setting-gear",
                    "shortcut": "",
                    "roles": [],
                },
            ],
        },
    ]

    if frappe.db.exists("Sidebar Master", {"sidebar_owner": "Master"}):
        return

    doc = frappe.get_doc(
        {
            "doctype": "Sidebar Master",
            "sidebar_owner": "Master",
            "config_json": json.dumps(SIDEBAR_CONFIG),
        }
    )

    doc.insert(ignore_permissions=True)


import requests
from frappe.utils.file_manager import save_file


def setup_navbar_settings():

    navbar = frappe.get_single("Navbar Settings")
    updated = False

    for row in navbar.settings_dropdown:
        if row.item_label == "Session Defaults":
            row.hidden = 1
            updated = True

    for row in navbar.help_dropdown:
        if row.item_label == "Frappe Support":
            row.hidden = 1
            updated = True

    url = "https://drive.usercontent.google.com/uc?id=1WAOgwqIH21AZJ88HmM-6fCc9nRv3ExYj&export=download"

    existing = frappe.db.get_value(
        "File",
        {"attached_to_doctype": "Navbar Settings"},
        ["name", "file_url"],
        as_dict=True,
    )
    file_url = ""
    if existing:
        file_url = existing.file_url
    else:
        response = requests.get(url, timeout=20)
        content_type = response.headers.get("Content-Type", "")

        if not content_type.startswith("image/"):
            frappe.throw(
                f"Downloaded file is not an image. Content-Type: {content_type}"
            )

        file_doc = save_file(
            fname="app_logo.png",
            content=response.content,
            dt="Navbar Settings",
            dn="Navbar Settings",
            is_private=0,
        )
        file_url = file_doc.file_url

    navbar.app_logo = file_url
    updated = True

    if updated:
        navbar.save(ignore_permissions=True)


def seed_website_setting():
    website = frappe.get_single("Website Settings")
    updated = False

    # ---------- LOGIN PAGE ----------
    if website.app_name != "Vrugle":
        website.app_name = "Vrugle"
        updated = True

    if website.disable_signup != 1:
        website.disable_signup = 1
        updated = True

    # App logo (reuse if exists, else download)
    url = "https://drive.usercontent.google.com/uc?id=1WAOgwqIH21AZJ88HmM-6fCc9nRv3ExYj&export=download"
    existing = frappe.db.get_value(
        "File",
        {"attached_to_doctype": "Website Settings"},
        ["name", "file_url"],
        as_dict=True,
    )

    file_url = ""
    if existing:
        file_url = existing.file_url
    else:
        response = requests.get(url, timeout=20)
        content_type = response.headers.get("Content-Type", "")

        if not content_type.startswith("image/"):
            frappe.throw(
                f"Downloaded file is not an image. Content-Type: {content_type}"
            )

        file_doc = save_file(
            fname="app_logo.png",
            content=response.content,
            dt="Website Settings",
            dn="Website Settings",
            is_private=0,
        )
        file_url = file_doc.file_url

    if website.app_logo != file_url:
        website.app_logo = file_url
        updated = True

    # ---------- LANDING / HOME ----------
    if website.home_page != "/app":
        website.home_page = "/app"
        updated = True

    if website.title_prefix != "Vrugle":
        website.title_prefix = "Vrugle"
        updated = True

    # ---------- FOOTER ----------
    footer_html = """
    <div style="display:flex;align-items:center;gap:6px;justify-content:center;">
        <span>Made with</span>
        <img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Smilies/Blue%20Heart.png"
             width="18" height="18" />
        <span>by <b>Vrugle</b></span>
    </div>
    """

    if website.footer_powered != footer_html:
        website.footer_powered = footer_html
        updated = True

    if website.copyright != "Vrugle LLP":
        website.copyright = "Vrugle LLP"
        updated = True

    if updated:
        website.save(ignore_permissions=True)


def seed_sales_stages():
    doctype = "Sales Stage"
    sales_stages = [
        "Prospecting",
        "Qualification",
        "Needs Analysis",
        "Value Proposition",
        "Identifying Decision Makers",
        "Perception Analysis",
        "Proposal/Price Quote",
        "Negotiation/Review",
    ]

    for stage in sales_stages:
        if not frappe.db.exists(doctype, stage):
            doc = frappe.get_doc(
                {
                    "doctype": doctype,
                    "name1": stage,
                }
            )
            doc.insert(ignore_permissions=True)


def create_interview_statuses():
    statuses = [
        "Interview Scheduled",
        "Ongoing Interview",
        "Accepted",
        "Rejected",
    ]

    for name in statuses:
        if not frappe.db.exists("Interview Status", name):
            doc = frappe.get_doc(
                {
                    "doctype": "Interview Status",
                    "status_name": name,
                }
            )
            doc.insert(ignore_permissions=True)


def seed_party_types():
    if not frappe.db.exists("Party Type", "Customer"):
        frappe.get_doc(
            {
                "doctype": "Party Type",
                "account_type": "Receivable",
                "party_type": "Customer",
            }
        ).insert()
    if not frappe.db.exists("Party Type", "Supplier"):
        frappe.get_doc(
            {
                "doctype": "Party Type",
                "account_type": "Payable",
                "party_type": "Supplier",
            }
        ).insert()


def seed_type_of_interview():
    doctype = "Type Of Interview"
    types = [
        "Google Meet",
        "Microsoft Teams",
        "Zoom call",
        "WebEx",
        "Skype",
        "Phone Call",
        "On-site",
    ]

    for t in types:
        if not frappe.db.exists(doctype, t):
            doc = frappe.get_doc(
                {
                    "doctype": doctype,
                    "type": t,
                }
            )
            doc.insert(ignore_permissions=True)


def seed_form_tours():
    for reference_doctype, config in FORM_TOURS.items():
        tour_name = reference_doctype
        meta = frappe.get_meta(reference_doctype)

        # Load or create Form Tour
        if frappe.db.exists("Form Tour", tour_name):
            tour = frappe.get_doc("Form Tour", tour_name)
            # Clear existing steps to avoid duplication
            tour.set("steps", [])
        else:
            tour = frappe.new_doc("Form Tour")
            tour.name = tour_name
            tour.reference_doctype = reference_doctype

        tour.title = config.get("title", reference_doctype)
        tour.save_on_completion = 0 if reference_doctype == "Sales Order" else 1

        # Build steps fresh
        for step in config["steps"]:
            step_doc = {
                "doctype": "Form Tour Step",
                "title": step["title"],
                "description": step["description"],
                "position": step["position"],
                "label": step.get("label", ""),
                "fieldtype": step.get("fieldtype", ""),
            }

            # Validate mutually exclusive selectors
            if step.get("fieldname"):
                if meta.has_field(step["fieldname"]):
                    step_doc["fieldname"] = step["fieldname"]
                else:
                    frappe.log_error(
                        title="Invalid Form Tour Field",
                        message=f"{reference_doctype}.{step['fieldname']} does not exist",
                    )
                    continue

            if step.get("selector"):
                step_doc["selector"] = step["selector"]

            tour.append("steps", step_doc)

        tour.save(ignore_permissions=True)


def create_all_roles():
    """Create role if it doesn't already exist."""
    for role_name in ROLES:
        if not frappe.db.exists("Role", role_name):
            role = frappe.new_doc("Role")
            role.role_name = role_name
            role.desk_access = 1
            role.save(ignore_permissions=True)

    frappe.clear_cache()


def seed_employee_departments():
    for department_name, roles in DEPARTMENTS_ROLES.items():
        if frappe.db.exists("Department", department_name):
            # Fetch existing doc to get latest 'modified' timestamp
            doc = frappe.get_doc("Department", department_name)

            doc.role = []  # Clear existing roles to avoid duplication
            # doc.save(ignore_permissions=True)
            for r in roles:
                doc.append("role", {"role": r})
            doc.save(ignore_permissions=True)
            print(f"Updated Department: {department_name}")
        else:
            # Create new
            doc = frappe.get_doc(
                {
                    "doctype": "Department",
                    "department_name": department_name,
                }
            )
            for r in roles:
                doc.append("role", {"role": r})
            doc.insert(ignore_permissions=True)
            print(f"Created Department: {department_name}")


PROTECTED_DOCTYPES = {
    "User",
    "Role",
    "Has Role",
    "DocPerm",
    "Custom DocPerm",
    "Role Profile",
    "Role Permission for Page and Report",
    "Module Def",
    "Page",
    "Report",
    "Dashboard",
    "Workspace",
}


def assign_permissions_to_roles(role_permissions: dict):
    """
    Synchronize DocPerms from ROLE_PERMISSIONS.

    - Administrator permissions are never modified.
    - Protected doctypes are skipped.
    - Existing DocPerms for managed (DocType, Role) pairs are updated.
    - Missing DocPerms are inserted.
    - Other roles and ERPNext permissions remain untouched.
    """

    roles = set(frappe.get_all("Role", filters={"disabled": 0}, pluck="name"))
    doctypes = set(frappe.get_all("DocType", pluck="name"))

    for role, permissions in role_permissions.items():
        if role == "System Manager" or role == "Administrator":
            continue

        if role not in roles:
            continue

        for doctype, config in permissions.items():
            if doctype in PROTECTED_DOCTYPES:
                continue

            if doctype not in doctypes:
                continue

            if isinstance(config, list):
                allowed_perms = set(config)
                if_owner = 0

            elif isinstance(config, dict):
                allowed_perms = set(config.get("perms", []))
                if_owner = 1 if config.get("if_owner") else 0

            else:
                continue

            values = {
                "if_owner": if_owner,
            }

            for field in PERM_FIELDS:
                values[field] = 1 if field in allowed_perms else 0

            existing = frappe.get_all(
                "DocPerm",
                filters={
                    "parent": doctype,
                    "parenttype": "DocType",
                    "parentfield": "permissions",
                    "role": role,
                    "permlevel": 0,
                },
                order_by="creation asc",
                pluck="name",
            )

            # Remove duplicate rows if any exist
            if len(existing) > 1:
                for duplicate in existing[1:]:
                    frappe.delete_doc(
                        "DocPerm",
                        duplicate,
                        force=True,
                        ignore_permissions=True,
                    )

            existing = existing[0] if existing else None

            if existing:
                frappe.db.set_value(
                    "DocPerm",
                    existing,
                    values,
                    update_modified=False,
                )

            else:
                doc = frappe.get_doc(
                    {
                        "doctype": "DocPerm",
                        "parent": doctype,
                        "parenttype": "DocType",
                        "parentfield": "permissions",
                        "role": role,
                        "permlevel": 0,
                        "if_owner": if_owner,
                        **{
                            field: 1 if field in allowed_perms else 0
                            for field in PERM_FIELDS
                        },
                    }
                )

                doc.flags.ignore_permissions = True
                doc.insert(ignore_permissions=True)

    frappe.clear_cache()


def seed_hierarchy():
    doctype = "Hierarchy"

    for item in HIERARCHY_DATA:
        department = item["department"]

        payload = {
            "doctype": doctype,
            "department": department,
            "role_hierarchy_json": json.dumps(item["role_hierarchy_json"]),
            "auto_assign_config": json.dumps(item["auto_assign_config"]),
        }

        if frappe.db.exists(doctype, {"department": department}):
            doc = frappe.get_doc(doctype, department)
            doc.role_hierarchy_json = payload["role_hierarchy_json"]
            doc.auto_assign_config = payload["auto_assign_config"]
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc(payload)
            doc.insert(ignore_permissions=True)


def remove_default_workspaces():
    print("Hiding all workspaces except CRM and Users...")

    keep_list = [
        "Email Inbox",
        "Pending PE Requests",
    ]

    placeholders = ", ".join(["%s"] * len(keep_list))

    query = """
        UPDATE `tabWorkspace`
        SET is_hidden = 1
        WHERE name NOT IN (
    """

    query += placeholders
    query += ")"

    frappe.db.sql(
        query,
        tuple(keep_list),
    )

    print("Workspaces updated successfully.")


COMMON_PASSWORD = "Vrugle@2026"

ROLE_USER_COUNTS = {
    "Lead Master Manager": 1,
    "Lead Manager": 1,
    "Lead Team Lead": 1,
    "Lead Person": 1,
    "Sales Master Manager": 1,
    "Sales Manager": 1,
    "Sales Team Lead": 1,
    "Sales Person": 1,
    "Marketing Master Manager": 1,
    "Marketing Manager": 1,
    "Marketing Team Lead": 1,
    "Senior Recruiter": 1,
    "Marketing Mentor": 1,
    "Recruiter": 1,
    "Technical Master Manager": 1,
    "Technical Manager": 1,
    "Technical Coordinator": 1,
    "Senior Resume Person": 1,
    "Resume Person": 1,
    "HR Manager": 1,
    "HR": 1,
}


def _safe_role_slug(role: str) -> str:
    """
    Convert role to safe lowercase slug.
    'Lead Person' -> 'lead_person'
    """
    role = role.lower()
    role = re.sub(r"[^a-z0-9 ]", "", role)
    return role.replace(" ", "_")


def seed_bulk_users_with_password():
    created = 0
    skipped = 0

    # Disable throttling for bulk import
    frappe.flags.in_import = True

    try:
        for role_name, count in ROLE_USER_COUNTS.items():
            # Role must exist
            if not frappe.db.exists("Role", role_name):
                frappe.log_error(
                    "Missing Role",
                    f"Role '{role_name}' does not exist. Skipping users.",
                )
                continue

            role_slug = _safe_role_slug(role_name)

            for i in range(1, count + 1):
                email = f"{role_slug}_{i}@gmail.com"
                full_name = f"{role_name}{i}"

                if frappe.db.exists("User", email):
                    skipped += 1
                    continue

                user = frappe.new_doc("User")
                user.email = email
                user.first_name = full_name
                user.enabled = 1

                # Prevent emails
                user.send_welcome_email = 0
                user.send_me_a_copy = 0

                # Assign ONLY the role (no role profile, no permissions)
                user.append("roles", {"role": role_name})

                user.insert(ignore_permissions=True)

                # Set password
                frappe.utils.password.update_password(
                    user=email, pwd=COMMON_PASSWORD, logout_all_sessions=False
                )

                created += 1

    finally:
        frappe.flags.in_import = False

    print(f"Created {created} users, skipped {skipped} existing users.")
    return {
        "created": created,
        "skipped_existing": skipped,
    }


# Seed Employees ----------------------------------------------------------------------

from collections import defaultdict

TECH_PLACEHOLDER = "General"

DEPARTMENT_WORKSPACE_ROLE_MAP = {
    "Accounting": ["_show_accounting", "_show_sidebar_master"],
}


def seed_employees_with_hierarchy(HIERARCHY_DATA):
    """
    Create Employees for Users and assign hierarchy evenly
    based strictly on User roles (NO role profiles).
    """

    # -------------------------------------------------
    # 1. Build hierarchy edges per department
    # -------------------------------------------------
    hierarchy_edges = defaultdict(list)  # dept -> [(parent_role, child_role)]

    for dept in HIERARCHY_DATA:
        department = dept["department"]
        for edge in dept["role_hierarchy_json"]:
            parent = edge["parent_role"].strip()
            for child in edge["child_roles"]:
                hierarchy_edges[department].append((parent, child.strip()))

    # -------------------------------------------------
    # 2. Fetch users and their single role
    # -------------------------------------------------
    users_by_role = defaultdict(list)

    users = frappe.get_all(
        "User",
        filters={"enabled": 1},
        fields=["name", "email"],
    )

    for u in users:
        roles = frappe.get_all(
            "Has Role",
            filters={"parent": u.email},
            pluck="role",
        )

        # Enforce exactly one role
        if len(roles) != 1:
            frappe.log_error(
                "Invalid User Role State",
                f"User {u.email} has roles: {roles}",
            )
            continue

        role = roles[0]
        users_by_role[role].append(u)

    # -------------------------------------------------
    # 3. Create Employees (idempotent)
    # -------------------------------------------------
    employee_by_user = {}
    employee_by_role = defaultdict(list)

    for role, role_users in users_by_role.items():
        for u in role_users:
            emp_name = frappe.db.get_value("Employee", {"user": u.email}, "name")

            if emp_name:
                emp = frappe.get_doc("Employee", emp_name)
            else:
                emp = frappe.new_doc("Employee")
                emp.user = u.email
                emp.employee_name = u.name
                emp.insert(ignore_permissions=True)

            employee_by_user[u.email] = emp
            employee_by_role[role].append(emp)

    # -------------------------------------------------
    # 4. Clear existing assignment tables
    # -------------------------------------------------
    for emp in employee_by_user.values():
        emp.set("employee_assignment_details_table", [])
        emp.save(ignore_permissions=True)

    # -------------------------------------------------
    # 5. Assign hierarchy (round-robin)
    # -------------------------------------------------
    for department, edges in hierarchy_edges.items():
        for parent_role, child_role in edges:
            parents = employee_by_role.get(parent_role, [])
            children = employee_by_role.get(child_role, [])

            if not parents or not children:
                continue

            for idx, child in enumerate(children):
                parent = parents[idx % len(parents)]

                child.append(
                    "employee_assignment_details_table",
                    {
                        "department": department,
                        "designation": child_role,
                        "assigned_to": parent.name,
                        "technology": TECH_PLACEHOLDER,
                    },
                )

                child.save(ignore_permissions=True)
                # ---- ADD WORKSPACE ROLES BASED ON DEPARTMENT ----

                workspace_roles = DEPARTMENT_WORKSPACE_ROLE_MAP.get(department, [])
                if workspace_roles:
                    ensure_user_has_workspace_roles(child.user, workspace_roles)


def ensure_user_has_workspace_roles(user_email: str, roles: list[str]):
    if not roles:
        return

    existing = set(
        frappe.get_all(
            "Has Role",
            filters={"parent": user_email},
            pluck="role",
        )
    )

    for role in roles:
        if role in existing:
            continue

        if not frappe.db.exists("Role", role):
            frappe.log_error("Missing Workspace Role", f"Role '{role}' does not exist")
            continue

        frappe.get_doc(
            {
                "doctype": "Has Role",
                "parent": user_email,
                "parenttype": "User",
                "parentfield": "roles",
                "role": role,
            }
        ).insert(ignore_permissions=True)


def get_primary_business_role(user_email: str) -> str | None:
    """
    Return the single non-workspace role for a user.
    Workspace roles (_show_*) are ignored.
    """
    roles = frappe.get_all(
        "Has Role",
        filters={"parent": user_email},
        pluck="role",
    )

    business_roles = [r for r in roles if not r.startswith("_show_")]

    if len(business_roles) != 1:
        frappe.log_error(
            "Invalid Business Role State",
            f"User {user_email} has business roles: {business_roles}",
        )
        return None

    return business_roles[0]


SERVICE_DEPARTMENT_MAP = {
    "Technical": [
        "RUC",
        "JDC",
        "Training",
    ],
    "Resume": [
        "Resume",
        "Cover Letter",
    ],
    "Marketing": [
        "Marketing",
    ],
}


def seed_services_and_departments():
    for department_name, services in SERVICE_DEPARTMENT_MAP.items():
        # Step 1: Ensure each service Item exists with is_service=1
        if not frappe.db.exists("Item Category", "ALL"):
            frappe.get_doc(
                {"doctype": "Item Category", "item_category_name": "ALL"}
            ).insert()
        for service_name in services:
            if not frappe.db.exists("Item", service_name):
                frappe.get_doc(
                    {
                        "doctype": "Item",
                        "item_name": service_name,
                        "is_service": 1,
                        "item_category": "ALL",
                        "disabled": 0,
                    }
                ).insert(ignore_permissions=True)
            else:
                # Ensure existing item is flagged as service
                frappe.db.set_value("Item", service_name, "is_service", 1)

        # Step 2: Ensure Department exists
        if not frappe.db.exists("Department", department_name):
            department = frappe.get_doc(
                {
                    "doctype": "Department",
                    "department_name": department_name,
                }
            )
            department.insert(ignore_permissions=True)
        else:
            department = frappe.get_doc("Department", department_name)

        # Step 3: Reset and re-populate Department Service multiselect
        department.services = []
        for service_name in services:
            department.append("services", {"service_name": service_name})

        department.save(ignore_permissions=True)

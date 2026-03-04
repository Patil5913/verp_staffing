# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LeadDetails(Document):
    def autoname(self):
        import re

        if self.first_name:
            names = [self.surname, self.first_name, self.fathers_name]
            base_name = " ".join([name.strip() for name in names if name])
            
            if not base_name:
                # fallback to default naming if something is wrong
                self.name = frappe.generate_hash(length=10)
                return

            self.title = base_name
            
            # Fetch all titles that start with base_name
            existing_titles = frappe.get_all(
                "Customer",
                filters={"title": ["like", f"{base_name}%"]},
                pluck="title"
            )
            
            max_count = 0

            for title in existing_titles:
                # Exact match (e.g., "name")
                if title == base_name:
                    max_count = max(max_count, 1)
                    continue

                # Match pattern name_number
                match = re.match(rf"^{re.escape(base_name)}_(\d+)$", title)
                if match:
                    count = int(match.group(1))
                    max_count = max(max_count, count)

            # Generate next title
            if max_count == 0:
                self.name = f"{base_name}_1"
            else:
                self.name = f"{base_name}_{max_count + 1}"

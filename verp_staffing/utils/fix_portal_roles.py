"""One-off clean-up: make every customer login a Website User whose only role is "Chat External".

Customers who were given (or ended up with) staff roles, or were made System Users, get the staff
app instead of the portal. This finds every customer login and fixes it. It changes nothing unless
you say so, so run it once to see the list, then again to apply:

    # 1. see what would change (nothing is written)
    bench --site <site> execute verp_staffing.utils.fix_portal_roles.run

    # 2. apply it
    bench --site <site> execute verp_staffing.utils.fix_portal_roles.run --kwargs '{"dry_run": false}'

For each customer login (linked to a Customer, or holding the Chat External role) it:
  * removes every role except Chat External, and any role/module profile that would put them back
  * sets the user type to Website User
  * switches desk access off on the Chat External role itself (the usual cause: Frappe makes a user
    a System User as soon as any of their roles grants desk access)
  * signs their sessions out, so their next page load is the portal

The Administrator and anyone with an Employee record are never touched; they are listed as skipped.
Passwords, enabled/disabled state and portal access (Customer.chat_access) are left as they are.
"""

from verp_staffing.crm.api.customer_chat import enforce_portal_roles


def run(dry_run: bool = True) -> dict:
    report = enforce_portal_roles(dry_run=dry_run)

    print(("DRY RUN, nothing was changed" if report["dry_run"] else "APPLIED") + f": checked {report['checked']} customer logins")
    for c in report["changed"]:
        extras = ", ".join(c["remove_roles"]) or "none"
        note = " | add Chat External" if c["add_role"] else ""
        note += " | clear role/module profile" if c["clear_profiles"] else ""
        print(f"  {c['user']:<34} was {c['user_type']:<12} remove roles: {extras}{note}")
    if not report["changed"]:
        print("  every customer login is already a Website User with only Chat External")
    for u in report["skipped_staff"]:
        print(f"  SKIPPED (staff, not touched): {u}")
    if report["dry_run"] and report["changed"]:
        print("To apply: add --kwargs '{\"dry_run\": false}'")
    return report

"""One company time zone, and per-user display of it.

The company time zone is System Settings' Time Zone, edited from ERP Configuration > Website
Settings. Every User's Time Zone defaults to it (and follows it when it changes, unless the user
picked their own), so by default the whole company sees the same clock.

Interview rounds are the one place a time is entered in a different zone: the recruiter types the
candidate's Eastern time and labels it EDT or EST. Everything that shows or groups a round by day
(calendar, "Today", dashboards, customer history) converts it into the viewer's zone through
`convert_round`, so the date can differ from the one that was typed (9 pm EST is the next morning
in India).
"""

from datetime import date, datetime, time, timedelta, timezone as dt_timezone

import frappe
import pytz
from frappe.utils import get_system_timezone, getdate

# The label the recruiter picks says which Eastern offset the time was typed in.
EASTERN_OFFSET_HOURS = {"EDT": -4, "EST": -5}


def company_time_zone():
    return get_system_timezone()


def user_time_zone(user=None):
    """The zone this user sees times in: their own Time Zone, else the company's."""
    user = user or frappe.session.user
    if not user or user == "Guest":
        return company_time_zone()
    return frappe.get_cached_value("User", user, "time_zone") or company_time_zone()


def time_zone_label(tz=None):
    """The zone's short name as of now - "IST", "EDT"."""
    zone = pytz.timezone(tz or user_time_zone())
    return datetime.now(zone).tzname() or zone.zone


def _seconds(value):
    if value is None or value == "":
        return None
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    if isinstance(value, time):
        return value.hour * 3600 + value.minute * 60 + value.second
    parts = [int(float(p)) for p in str(value).split(":")]
    parts += [0] * (3 - len(parts))
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def _fmt(seconds):
    seconds %= 86400
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def convert_round(day, from_time, to_time, label, tz=None):
    """An interview round's date and times, typed in US Eastern (`label` = EDT / EST), in zone `tz`
    (default: the current user's). Returns {date, from_time, to_time, tz_label, entered, moved_days};
    a round with no label or no start time is returned exactly as typed."""
    day = getdate(day) if day else None
    start, end = _seconds(from_time), _seconds(to_time)
    entered = " ".join(x for x in (f"{_fmt(start)[:5]}" if start is not None else "", label or "") if x)
    as_typed = {"date": day, "from_time": _fmt(start) if start is not None else None, "to_time": _fmt(end) if end is not None else None, "tz_label": label or "", "entered": entered, "moved_days": 0}
    offset = EASTERN_OFFSET_HOURS.get(label)
    if day is None or start is None or offset is None:
        return as_typed

    zone = pytz.timezone(tz or user_time_zone())
    origin = datetime.combine(day, time.min)

    def to_zone(seconds):
        utc = (origin + timedelta(seconds=seconds) - timedelta(hours=offset)).replace(tzinfo=dt_timezone.utc)
        return utc.astimezone(zone)

    local = to_zone(start)
    return {
        "date": local.date(),
        "from_time": local.strftime("%H:%M:%S"),
        "to_time": to_zone(end).strftime("%H:%M:%S") if end is not None else None,
        "tz_label": local.tzname() or zone.zone,
        "entered": entered,
        "moved_days": (local.date() - day).days,
    }


def round_day(day, from_time, label, tz=None):
    """Just the date a round falls on in `tz` (default: the company's), for grouping and 'today'."""
    if not day:
        return None
    return convert_round(day, from_time, None, label, tz or company_time_zone())["date"]


@frappe.whitelist()
def get_clock():
    """What the navbar clock shows, worked out here so it never depends on the browser's zone or clock
    (or the server's own): the current wall time in the user's Time Zone, that zone, its short name
    ("EDT"), and the company zone for comparison."""
    zone = user_time_zone()
    try:
        now = datetime.now(pytz.timezone(zone))
    except pytz.UnknownTimeZoneError:
        zone = company_time_zone()
        now = datetime.now(pytz.timezone(zone))
    return {"zone": zone, "company_zone": company_time_zone(), "label": now.tzname() or zone, "wall": now.strftime("%Y-%m-%dT%H:%M:%S")}


def viewer_today():
    """Today's date on the current user's clock - what "today" means on their dashboards."""
    return datetime.now(pytz.timezone(user_time_zone())).date()


def sync_users_to_company_time_zone(doc, method=None):
    """System Settings on_update: when the company time zone changes, users who were following it
    (same zone as before, or none) move to the new one. A user who picked their own zone keeps it."""
    before = doc.get_doc_before_save()
    old, new = (before.time_zone if before else None), doc.time_zone
    if not new or old == new:
        return
    users = frappe.db.sql_list("select name from `tabUser` where ifnull(time_zone, '') in (%s, '')", (old or "",))
    for user in users:
        frappe.db.set_value("User", user, "time_zone", new, update_modified=False)
        frappe.defaults.set_default("time_zone", new, user)
        frappe.clear_cache(user=user)

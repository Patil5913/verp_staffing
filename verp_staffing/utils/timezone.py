"""One company time zone, for everyone.

The company time zone is System Settings' Time Zone, edited from ERP Configuration > Website
Settings. Every date and time is stored, shown and compared in it: a User's own Time Zone is not used
(it is kept equal to the company's, see `force_company_time_zone`), so everyone sees the same clock
and the same "today".

Interview rounds are stored in the company time zone like everything else. The recruiter may type a
round in another zone (the candidate's); the round's Time Zone says which, and saving converts the date
and times to the company zone (`normalize_round`), keeping what was typed in `entered_as`. Everything
that shows or groups a round by day (calendar, "Today", dashboards, customer history) goes through
`convert_round`, which moves it from the zone it is stored in into the company's.
"""

from datetime import date, datetime, time, timedelta, timezone as dt_timezone

import frappe
import pytz
from frappe.utils import get_system_timezone, getdate

def company_time_zone():
    return _valid(get_system_timezone()) or "UTC"


def _valid(tz):
    """`tz` if pytz knows it, else None - a free-typed or stale Time Zone must never break a page."""
    try:
        return tz if tz and pytz.timezone(tz) else None
    except pytz.UnknownTimeZoneError:
        return None


def _zone(tz=None):
    return pytz.timezone(_valid(tz) or user_time_zone())


def user_time_zone(user=None):
    """The zone this user sees times in: always the company's."""
    return company_time_zone()


def time_zone_label(tz=None):
    """The zone's short name as of now - "IST", "EDT"."""
    zone = _zone(tz)
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


def _abbr(zone, moment):
    return moment.tzname() or zone.zone


def convert_round(day, from_time, to_time, source_tz, tz=None):
    """An interview round's date and times, stored in zone `source_tz` (default: the company's), in
    zone `tz` (default: the current user's). Daylight saving is applied by the zone database, so a
    round in March or November gets the right offset. Returns {date, from_time, to_time, tz_label,
    entered, moved_days, converted}; a round with no start time is returned as stored."""
    day = getdate(day) if day else None
    start, end = _seconds(from_time), _seconds(to_time)
    source = pytz.timezone(_valid(source_tz) or company_time_zone())
    as_stored = {"date": day, "from_time": _fmt(start) if start is not None else None, "to_time": _fmt(end) if end is not None else None, "tz_label": "", "entered": "", "moved_days": 0, "converted": False}
    if day is None or start is None:
        return as_stored

    zone = _zone(tz)
    origin = datetime.combine(day, time.min)

    def at(seconds, target):
        wall = origin + timedelta(seconds=seconds)
        return source.localize(wall, is_dst=False).astimezone(target)

    started = at(start, source)
    entered = f"{_fmt(start)[:5]} {_abbr(source, started)}"
    local = at(start, zone)
    return {
        "date": local.date(),
        "from_time": local.strftime("%H:%M:%S"),
        "to_time": at(end, zone).strftime("%H:%M:%S") if end is not None else None,
        "tz_label": _abbr(zone, local),
        "entered": entered,
        "moved_days": (local.date() - day).days,
        "converted": source.zone != zone.zone,
    }


def round_day(day, from_time, source_tz, tz=None):
    """Just the date a round falls on in `tz` (default: the company's), for grouping and 'today'."""
    if not day:
        return None
    return convert_round(day, from_time, None, source_tz, tz or company_time_zone())["date"]


def normalize_round(row, previous=None):
    """Interview Round validate: put the round's date and times in the company time zone. The row's
    Time Zone says which zone they were typed in (blank = the company's); afterwards it is the company's,
    and `entered_as` keeps what was typed ("09:00 IST") when that was a different zone. `previous` is the
    row as last saved: retyping the round in the company zone drops a stale `entered_as`."""
    company = company_time_zone()
    typed_in = row.time_zone or company
    if not _valid(typed_in):
        frappe.throw(frappe._("Row #{0}: '{1}' is not a known time zone.").format(row.idx, typed_in))
    if typed_in != company and row.date_of_interview and row.from_time:
        local = convert_round(row.date_of_interview, row.from_time, row.to_time, typed_in, company)
        row.entered_as = f"{local['entered']} ({typed_in})"
        row.date_of_interview = local["date"]
        row.from_time = local["from_time"]
        row.to_time = local["to_time"]
    elif row.entered_as and previous and (row.date_of_interview, row.from_time, row.to_time) != (previous.date_of_interview, previous.from_time, previous.to_time):
        row.entered_as = None
    row.time_zone = company


@frappe.whitelist()
def get_clock():
    """What the navbar clock shows, worked out here so it never depends on the browser's zone or clock
    (or the server's own): the current wall time in the user's Time Zone, that zone, its short name
    ("EDT"), and the company zone for comparison."""
    zone = user_time_zone()
    now = datetime.now(pytz.timezone(zone))
    return {"zone": zone, "company_zone": company_time_zone(), "label": now.tzname() or zone, "wall": now.strftime("%Y-%m-%dT%H:%M:%S")}


def company_today():
    """Today's date in the company time zone - the "today" every stored date is compared with."""
    return datetime.now(pytz.timezone(company_time_zone())).date()


viewer_today = company_today


def company_now():
    """The current moment, as a datetime in the company time zone (timezone-aware)."""
    return datetime.now(pytz.timezone(company_time_zone()))


def sync_users_to_company_time_zone(doc, method=None):
    """System Settings on_update: when the company time zone changes, every user moves to it.
    Never blocks saving System Settings: a failure is logged."""
    try:
        before = doc.get_doc_before_save()
        old, new = (before.time_zone if before else None), doc.time_zone
        if not _valid(new) or old == new:
            return
        move_users_to(new)
    except Exception:
        frappe.log_error(title="Company time zone: could not update users", message=frappe.get_traceback())


def force_company_time_zone(doc, method=None):
    """User validate: a user's Time Zone is always the company's, whatever was sent."""
    doc.time_zone = company_time_zone()


def move_users_to(new):
    """Set every user's Time Zone to `new`."""
    rows = frappe.db.sql("select name, time_zone from `tabUser` where name not in ('Guest')", as_dict=True)
    moved = 0
    for r in rows:
        if r.time_zone == new:
            continue
        frappe.db.set_value("User", r.name, "time_zone", new, update_modified=False)
        frappe.defaults.set_default("time_zone", new, r.name)
        frappe.clear_cache(user=r.name)
        moved += 1
    return moved


@frappe.whitelist()
def apply_company_time_zone_to_all_users():
    """System Manager: put every user on the company time zone."""
    frappe.only_for("System Manager")
    return {"time_zone": company_time_zone(), "users_updated": move_users_to(company_time_zone())}

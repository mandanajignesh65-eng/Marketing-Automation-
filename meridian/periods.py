"""Date ranges, comparison windows and the small time-formatting helpers the screens share."""

import calendar
from datetime import date, datetime, time, timedelta

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
               "October", "November", "December"]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAYS_LONG = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def midnight(d):
    return datetime.combine(d, time.min)


def day_label(d, year=False):
    s = "{} {}".format(d.day, MONTHS[d.month - 1])
    return s + " " + str(d.year) if year else s


def span_label(s, e, spaced=False):
    """'24 Sep', '1–24 Sep' or '28 Aug – 3 Sep'."""
    if s == e:
        return day_label(s)
    if (s.year, s.month) == (e.year, e.month):
        return ("{} – {} {}" if spaced else "{}–{} {}").format(s.day, e.day, MONTHS[e.month - 1])
    return "{} – {}".format(day_label(s), day_label(e))


def days_in_month(d):
    return calendar.monthrange(d.year, d.month)[1]


def month_key(d):
    return "{:04d}-{:02d}".format(d.year, d.month)


def next_month(d):
    return (d.replace(day=1) + timedelta(days=32)).replace(day=1)


BASELINE_DAYS = 90


class Window(tuple):
    """A comparison window (start_dt, end_dt, start_date, end_date) that knows how much to scale its counts by."""

    def __new__(cls, parts, scale=1.0):
        w = super().__new__(cls, parts)
        w.scale = scale
        return w


def scaled(value, factor):
    """A count from the comparison window brought to the length of the range being looked at."""
    if factor is None or value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    x = value * factor
    return round(x) if abs(x) >= 10 else round(x, 1)


def scale_all(obj, factor):
    """scaled() on every number in a dict or list (counts only: never pass averages or rates)."""
    if isinstance(obj, dict):
        return {k: scale_all(v, factor) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scale_all(v, factor) for v in obj]
    return scaled(obj, factor)


class Period:
    """A date range plus the comparison range before it.

    Lead and deal counts use datetime windows. When the range runs to today, the comparison
    window stops at the same time of day, so a half-finished day is compared like for like.
    Daily feeds (spend, impressions, sessions) use whole dates.
    """

    def __init__(self, now, rng="month", start=None, end=None):
        today = now.date()
        if rng == "day":
            s = e = today
        elif rng == "week":
            s, e = today - timedelta(days=today.weekday()), today
        elif rng == "custom" and start and end:
            e = min(date.fromisoformat(end), today)
            s = min(date.fromisoformat(start), e)
        else:
            rng, s, e = "month", today.replace(day=1), today

        # The comparison is the daily average of the three months before the range, times the range's length.
        # The window is the 90 days before it; every count from that window is multiplied by `scale`.
        ps, pe = s - timedelta(days=BASELINE_DAYS), s - timedelta(days=1)

        self.now, self.rng, self.s, self.e, self.ps, self.pe = now, rng, s, e, ps, pe
        self.to_date = e == today
        self.start_dt = iso(midnight(s))
        self.pstart_dt = iso(midnight(ps))
        self.pend_dt = iso(midnight(s))
        if self.to_date:
            self.end_dt = iso(now + timedelta(seconds=1))
            length = (e - s).days + min(1.0, max(0.05, (now - midnight(e)).total_seconds() / 86400))  # today counts as the part already gone
        else:
            self.end_dt = iso(midnight(e + timedelta(days=1)))
            length = (e - s).days + 1
        self.scale = length / BASELINE_DAYS

    @property
    def cur(self):
        return (self.start_dt, self.end_dt, self.s.isoformat(), self.e.isoformat())

    @property
    def prev(self):
        return Window((self.pstart_dt, self.pend_dt, self.ps.isoformat(), self.pe.isoformat()), self.scale)

    @property
    def days(self):
        return [self.s + timedelta(days=i) for i in range((self.e - self.s).days + 1)]

    def prev_name(self):
        return "the 3-month average"

    def as_json(self):
        return {
            "range": self.rng,
            "start": self.s.isoformat(),
            "end": self.e.isoformat(),
            "label": span_label(self.s, self.e, spaced=True) + " " + str(self.e.year),
            "short": span_label(self.s, self.e),
            "prev_short": "3-month avg",
            "prev_name": self.prev_name(),
            "to_date": self.to_date,
        }


def ago(now, then):
    """'just now', '4 min ago', '2 h ago', 'Yesterday', '21 Sep'."""
    if isinstance(then, str):
        then = datetime.fromisoformat(then)
    secs = (now - then).total_seconds()
    if secs < 60:
        return "just now"
    if secs < 3600:
        return "{} min ago".format(int(secs // 60))
    if secs < 86400 and then.date() == now.date() or secs < 6 * 3600:
        return "{} h ago".format(int(secs // 3600))
    if (now.date() - then.date()).days == 1:
        return "Yesterday"
    return day_label(then.date(), year=then.year != now.year)


def age_short(now, then):
    """Compact age: '40m', '4h', then calendar days ('7d') once a day has passed."""
    if isinstance(then, str):
        then = datetime.fromisoformat(then)
    secs = max(0, (now - then).total_seconds())
    if secs < 3600:
        return "{}m".format(max(1, int(secs // 60)))
    if secs < 86400:
        return "{}h".format(int(secs // 3600))
    return "{}d".format((now.date() - then.date()).days)


def stamp(dt):
    """'24 Sep 10:12'."""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return "{} {:02d}:{:02d}".format(day_label(dt.date()), dt.hour, dt.minute)


def fired_label(now, dt):
    """'Today 12:40', 'Yesterday', '22 Sep', 'Never'."""
    if not dt:
        return "Never"
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    gap = (now.date() - dt.date()).days
    if gap == 0:
        return "Today {:02d}:{:02d}".format(dt.hour, dt.minute)
    if gap == 1:
        return "Yesterday"
    return day_label(dt.date(), year=dt.year != now.year)

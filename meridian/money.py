"""Currency formatting. The currency is a setting, so wording written by the back end and
figures formatted by the front end always agree."""

DEFAULT = "INR"

# units: (threshold, suffix, decimals) from largest to smallest, for compact figures
CURRENCIES = {
    "INR": dict(symbol="₹", locale="en-IN", indian=True, units=[(1e7, "Cr", 2), (1e5, "L", 1), (1e3, "K", 1)]),
    "USD": dict(symbol="$", locale="en-US", indian=False, units=[(1e9, "B", 2), (1e6, "M", 2), (1e3, "k", 1)]),
}

_code = DEFAULT


def use(code):
    global _code
    _code = code if code in CURRENCIES else DEFAULT


def load(conn):
    """Pick up the database's currency setting."""
    row = conn.execute("SELECT value FROM settings WHERE key = 'currency'").fetchone()
    use(row["value"] if row else DEFAULT)


def spec():
    return dict(CURRENCIES[_code], code=_code)


def group(n):
    """Digit grouping: 12,34,567 for rupees, 1,234,567 otherwise."""
    n = int(round(n))
    if not CURRENCIES[_code]["indian"]:
        return "{:,}".format(n)
    sign, digits = ("-" if n < 0 else ""), str(abs(n))
    if len(digits) <= 3:
        return sign + digits
    head, tail = digits[:-3], digits[-3:]
    pairs = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    return sign + ",".join([head] + pairs + [tail])


def money(n):
    """Whole amount: ₹48,620."""
    return CURRENCIES[_code]["symbol"] + group(n)


def money_short(n):
    """Compact amount with up to one decimal: ₹9.6Cr, ₹48.6K."""
    c = CURRENCIES[_code]
    for threshold, suffix, _ in c["units"]:
        if abs(n) >= threshold:
            return c["symbol"] + ("%.1f" % (n / threshold)).rstrip("0").rstrip(".") + suffix
    return money(n)

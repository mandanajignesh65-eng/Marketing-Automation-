"""Integer allocation helpers used to build sample data whose totals add up exactly."""


def split(total, weights, caps=None):
    """Split an integer total across weights by largest remainder, optionally capped per slot."""
    n = len(weights)
    out = [0] * n
    active = [i for i in range(n) if weights[i] > 0 and (caps is None or caps[i] > 0)]
    remaining = total
    while remaining > 0 and active:
        wsum = sum(weights[i] for i in active)
        raw = {i: remaining * weights[i] / wsum for i in active}
        base = {i: int(raw[i]) for i in active}
        left = remaining - sum(base.values())
        for i in sorted(active, key=lambda i: raw[i] - base[i], reverse=True)[:left]:
            base[i] += 1
        still = []
        for i in active:
            add = base[i] if caps is None else min(base[i], caps[i] - out[i])
            out[i] += add
            remaining -= add
            if caps is None or out[i] < caps[i]:
                still.append(i)
        if caps is None:
            break
        active = still
    if remaining:
        raise ValueError("cannot place {} of {}".format(remaining, total))
    return out


def matrix(row_totals, col_totals, rng=None, jitter=0.0):
    """Integer matrix with the given row and column sums. Rows follow the remaining column need."""
    if sum(row_totals) != sum(col_totals):
        raise ValueError("row total {} != column total {}".format(sum(row_totals), sum(col_totals)))
    need = list(col_totals)
    rows = []
    for r, total in enumerate(row_totals):
        if r == len(row_totals) - 1:
            row = list(need)
        else:
            weights = [c * (1 + jitter * (rng.random() - 0.5)) if rng else c for c in need]
            row = split(total, weights, caps=need)
        need = [a - b for a, b in zip(need, row)]
        rows.append(row)
    return rows

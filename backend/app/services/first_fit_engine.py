"""1D First-Fit stall placement along a street segment; stalls cannot cross pillars.

Anchor placement:
    A vendor may register an expected anchor meter ``anchor_m`` with a tolerance
    ``tolerance_m``. When filling free gaps in priority order, an anchored stall's
    START must land within ``[anchor - tol, anchor + tol]``. A gap that is wide
    enough but whose feasible start falls outside the band is skipped and the
    search continues. When no gap satisfies the band the vendor is rejected with
    reason "锚点不符" — provided at least one gap was in fact wide enough, so a
    genuinely-too-wide stall is still reported as lacking free span rather than
    mislabelled. Vendors without an anchor keep the existing leftmost-first fill.

The placement decision and the map both consume exactly the numbers produced
here: a rejected vendor has no placement interval, so nothing out-of-band can
ever be drawn.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

# Floating-point comparison slack shared by width checks and band checks, so the
# reason written here and the interval drawn on the map come from one tolerance.
_EPS = 1e-9

REASON_NO_SPAN = "无连续空档可放下且不跨越挡柱"
REASON_ANCHOR = "锚点不符：空档宽度够，但起点无法落在期望锚点容差带内"


@dataclass
class Placement:
    vendor_id: int
    vendor_name: str
    start_m: float
    end_m: float
    width_m: float
    anchor_m: float | None = None
    tolerance_m: float | None = None


@dataclass
class Rejected:
    vendor_id: int
    vendor_name: str
    width_m: float
    reason: str
    anchor_m: float | None = None
    tolerance_m: float | None = None


@dataclass
class AllocResult:
    placements: list[Placement]
    rejected: list[Rejected]
    free_spans: list[tuple[float, float]]


def free_spans_from_pillars(width_m: float, pillars: list[dict]) -> list[tuple[float, float]]:
    """pillars: position_m, thickness_m — treated as blocked intervals."""
    blocked = []
    for p in pillars:
        half = p.get("thickness_m", 0.4) / 2.0
        lo = max(0.0, p["position_m"] - half)
        hi = min(width_m, p["position_m"] + half)
        if hi > lo:
            blocked.append((lo, hi))
    blocked.sort()
    merged = []
    for lo, hi in blocked:
        if not merged or lo > merged[-1][1]:
            merged.append([lo, hi])
        else:
            merged[-1][1] = max(merged[-1][1], hi)
    spans = []
    cursor = 0.0
    for lo, hi in merged:
        if lo > cursor:
            spans.append((cursor, lo))
        cursor = hi
    if cursor < width_m:
        spans.append((cursor, width_m))
    return [(round(a, 3), round(b, 3)) for a, b in spans if b - a > _EPS]


def _anchor_spec(v: dict) -> tuple[float | None, float]:
    """Return (anchor, tolerance); anchor is None when the vendor has none."""
    a = v.get("anchor_m")
    if a is None:
        return None, 0.0
    tol = v.get("tolerance_m")
    return float(a), float(tol) if tol is not None else 0.0


def _feasible_start(gap_lo: float, gap_hi: float, need: float,
                    anchor: float, tol: float) -> float | None:
    """Start inside the gap that best honours the anchor, or None if the band
    ``[anchor-tol, anchor+tol]`` cannot be met within this gap.

    The start is the anchor projected onto the feasible window
    ``[gap_lo, gap_hi-need]``: anchor when the stall fits around it, otherwise the
    edge nearest the anchor. It is accepted only if it stays inside the band —
    this single check governs both placement and rejection."""
    lo = max(gap_lo, anchor - tol)
    hi = min(gap_hi - need, anchor + tol)
    if hi + _EPS < lo:
        return None
    start = min(max(anchor, lo), hi)
    return start


def _consume(free: list[list[float]], gap: list[float], start: float, end: float) -> None:
    """Carve [start, end) out of gap, splitting into left/right fragments and
    merging neighbour fragments when they touch, keeping `free` sorted."""
    free.remove(gap)
    if start - gap[0] > _EPS:
        free.append([gap[0], start])
    if gap[1] - end > _EPS:
        free.append([end, gap[1]])
    free.sort(key=lambda g: g[0])
    merged: list[list[float]] = []
    for g in free:
        if merged and g[0] <= merged[-1][1] + _EPS:
            merged[-1][1] = max(merged[-1][1], g[1])
        else:
            merged.append([g[0], g[1]])
    free[:] = merged


def allocate_first_fit(width_m: float, vendors: list[dict], pillars: list[dict]) -> AllocResult:
    """vendors sorted by priority ascending then id.

    Each stall needs ``stall_width_m`` contiguous metres inside one free span
    (never crossing a pillar). Anchored stalls additionally require their start
    inside the anchor tolerance band; gaps wide enough but off-band are skipped."""
    spans = free_spans_from_pillars(width_m, pillars)
    # mutable free intervals (may split when an anchored stall sits mid-gap)
    free: list[list[float]] = [[a, b] for a, b in spans]
    ordered = sorted(vendors, key=lambda v: (v.get("priority", 1), v["id"]))
    placements: list[Placement] = []
    rejected: list[Rejected] = []
    for v in ordered:
        need = float(v["stall_width_m"])
        anchor, tol = _anchor_spec(v)
        placed = False
        seen_wide_enough = False
        if anchor is None:
            # existing behaviour: first gap that fits, pack from the left
            for gap in free:
                if gap[1] - gap[0] + _EPS >= need:
                    start, end = gap[0], gap[0] + need
                    placements.append(Placement(v["id"], v["name"], round(start, 3),
                                                 round(end, 3), need))
                    _consume(free, gap, start, end)
                    placed = True
                    break
            if not placed:
                rejected.append(Rejected(v["id"], v["name"], need, REASON_NO_SPAN))
            continue
        band_lo, band_hi = anchor - tol, anchor + tol
        for gap in free:
            if gap[1] - gap[0] + _EPS < need:
                continue
            # width is sufficient in this gap — remember it for the rejection reason
            seen_wide_enough = True
            start = _feasible_start(gap[0], gap[1], need, anchor, tol)
            if start is None:
                # wide enough but the start would leave the band: skip this gap
                continue
            end = start + need
            placements.append(Placement(v["id"], v["name"], round(start, 3), round(end, 3),
                                         need, round(anchor, 3), round(tol, 3)))
            _consume(free, gap, start, end)
            placed = True
            break
        if not placed:
            # Same tolerance decision as the band check above: if some gap was
            # wide enough the failure is the anchor band, never "no free span".
            reason = REASON_ANCHOR if seen_wide_enough else REASON_NO_SPAN
            rejected.append(Rejected(v["id"], v["name"], need, reason,
                                     round(anchor, 3), round(tol, 3)))
    free_out = [(round(a, 3), round(b, 3)) for a, b in free if b - a > _EPS]
    return AllocResult(placements, rejected, free_out)


def result_to_dict(r: AllocResult) -> dict:
    return {
        "placements": [asdict(p) for p in r.placements],
        "rejected": [asdict(x) for x in r.rejected],
        "free_spans": [{"start_m": a, "end_m": b} for a, b in r.free_spans],
    }

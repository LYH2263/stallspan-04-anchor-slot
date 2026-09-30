from app.services.first_fit_engine import (
    REASON_ANCHOR,
    REASON_NO_SPAN,
    allocate_first_fit,
    free_spans_from_pillars,
)

PILLARS = [
    {"position_m": 10.0, "thickness_m": 0.5},
    {"position_m": 20.0, "thickness_m": 0.5},
]
# free spans: [0,9.75] [10.25,19.75] [20.25,30]


def _by_name(r, name):
    p = [x for x in r.placements if x.vendor_name == name]
    x = [y for y in r.rejected if y.vendor_name == name]
    return (p[0] if p else None), (x[0] if x else None)


def test_free_spans_with_pillars():
    spans = free_spans_from_pillars(30.0, PILLARS)
    assert len(spans) == 3
    assert spans[0][0] == 0.0


def test_first_fit_no_cross_pillar():
    vendors = [
        {"id": 1, "name": "A", "stall_width_m": 4.0, "priority": 1},
        {"id": 2, "name": "B", "stall_width_m": 12.0, "priority": 1},
    ]
    r = allocate_first_fit(30.0, vendors, [{"position_m": 10.0, "thickness_m": 0.5}])
    assert any(p.vendor_name == "A" for p in r.placements)
    assert len(r.placements) + len(r.rejected) == 2


def test_reject_oversized():
    vendors = [{"id": 1, "name": "Huge", "stall_width_m": 25.0, "priority": 1}]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    assert len(r.rejected) == 1
    assert r.rejected[0].vendor_name == "Huge"
    assert r.rejected[0].reason == REASON_NO_SPAN


def test_no_anchor_keeps_left_fill():
    vendors = [{"id": 1, "name": "A", "stall_width_m": 4.0, "priority": 1}]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    p, _ = _by_name(r, "A")
    assert p is not None and p.start_m == 0.0


def test_anchor_seed_linji_lands_in_band_without_crossing_pillar():
    # Seed scenario: 林记糖水 anchor 11, tol 1, width 3.
    # Priority-1 stalls fill first; its start must be within [10,12].
    vendors = [
        {"id": 1, "name": "阿强烧烤", "stall_width_m": 4.0, "priority": 1},
        {"id": 2, "name": "林记糖水", "stall_width_m": 3.0, "priority": 1,
         "anchor_m": 11.0, "tolerance_m": 1.0},
        {"id": 3, "name": "老周水果", "stall_width_m": 5.0, "priority": 2},
        {"id": 4, "name": "小美饰品", "stall_width_m": 2.5, "priority": 2},
        {"id": 5, "name": "大碗面", "stall_width_m": 6.0, "priority": 1},
        {"id": 6, "name": "手作皮具", "stall_width_m": 3.5, "priority": 3},
        {"id": 7, "name": "巨型舞台车", "stall_width_m": 12.0, "priority": 9},
    ]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    p, rej = _by_name(r, "林记糖水")
    assert p is not None and rej is None
    assert 10.0 <= p.start_m <= 12.0
    # stall wholly inside the middle free span (no pillar cross)
    assert p.start_m >= 10.25 and p.end_m <= 19.75


def test_anchor_places_at_anchor_when_it_fits():
    vendors = [{"id": 1, "name": "Anc", "stall_width_m": 3.0, "priority": 1,
                "anchor_m": 5.0, "tolerance_m": 1.0}]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    p, _ = _by_name(r, "Anc")
    assert p is not None
    assert p.start_m == 5.0 and p.end_m == 8.0
    # leaves fragments on both sides
    flat = [s for span in r.free_spans for s in span]
    assert any(abs(s - 5.0) < 1e-6 for s in flat)
    assert any(abs(s - 8.0) < 1e-6 for s in flat)


def test_wide_enough_gap_off_band_is_skipped_then_anchor_reason():
    # Anchor 11 ±1 (band [10,12]); an earlier anchored stall occupies
    # [10.25,12.25] at the left of the middle span. The remaining middle gap
    # [12.25,19.75] is wide enough but a 3 m start there is off-band, as are
    # the first/last spans. Width clearly exists, so the reason must be anchor
    # mismatch — NOT "no free span".
    vendors = [
        {"id": 1, "name": "blocker", "stall_width_m": 2.0, "priority": 1,
         "anchor_m": 10.25, "tolerance_m": 0.0},
        {"id": 2, "name": "Anc", "stall_width_m": 3.0, "priority": 2,
         "anchor_m": 11.0, "tolerance_m": 1.0},
    ]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    p, rej = _by_name(r, "Anc")
    assert p is None and rej is not None
    assert rej.reason == REASON_ANCHOR
    assert rej.anchor_m == 11.0 and rej.tolerance_m == 1.0


def test_skips_first_gap_fits_later_gap():
    # Anchor 25 ±1 (band [24,26]) only the last span can satisfy it; earlier
    # spans are wide enough but off-band and must be skipped, not consume it.
    vendors = [{"id": 1, "name": "Anc", "stall_width_m": 3.0, "priority": 1,
                "anchor_m": 25.0, "tolerance_m": 1.0}]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    p, _ = _by_name(r, "Anc")
    assert p is not None
    assert 24.0 <= p.start_m <= 26.0
    assert p.start_m >= 20.25  # in last span


def test_anchor_near_edge_clamps_inside_band_and_gap():
    # anchor 1 ±1, width 3; feasible start window inside first span is
    # [0, 6.75], band [0,2]; clamp anchor(1) -> start 1, inside band.
    vendors = [{"id": 1, "name": "Edge", "stall_width_m": 3.0, "priority": 1,
                "anchor_m": 1.0, "tolerance_m": 1.0}]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    p, _ = _by_name(r, "Edge")
    assert p is not None and p.start_m == 1.0


def test_anchor_band_impossibly_far_reports_anchor_when_width_ok():
    # Two stalls share the exact anchor 11 ±0. The first (2 m) takes [11,13];
    # the second (3 m) can no longer start exactly at 11 (left fragment only
    # 0.75 m, right fragment starts at 13). Width is available but the band
    # cannot be met -> anchor mismatch.
    vendors = [
        {"id": 1, "name": "a", "stall_width_m": 2.0, "priority": 1,
         "anchor_m": 11.0, "tolerance_m": 0.0},
        {"id": 2, "name": "b", "stall_width_m": 3.0, "priority": 2,
         "anchor_m": 11.0, "tolerance_m": 0.0},
    ]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    p_a, _ = _by_name(r, "a")
    assert p_a is not None and p_a.start_m == 11.0
    p_b, rej_b = _by_name(r, "b")
    assert p_b is None and rej_b is not None
    assert rej_b.reason == REASON_ANCHOR


def test_too_wide_anchored_stall_still_reports_no_span():
    # 25 m exceeds every span regardless of anchor: must NOT be relabelled
    # anchor mismatch even though it carries an anchor.
    vendors = [{"id": 1, "name": "HugeAnc", "stall_width_m": 25.0, "priority": 1,
                "anchor_m": 11.0, "tolerance_m": 2.0}]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    assert len(r.rejected) == 1
    assert r.rejected[0].reason == REASON_NO_SPAN
    assert r.placements == []


def test_rejected_anchor_has_no_drawn_block():
    # A rejected anchored vendor must produce no placement interval at all,
    # so the map (which only renders placements) can never show an out-of-band block.
    vendors = [
        {"id": 1, "name": "blocker", "stall_width_m": 2.0, "priority": 1,
         "anchor_m": 10.25, "tolerance_m": 0.0},
        {"id": 2, "name": "Anc", "stall_width_m": 3.0, "priority": 2,
         "anchor_m": 11.0, "tolerance_m": 1.0},
    ]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    assert all(p.vendor_name != "Anc" for p in r.placements)

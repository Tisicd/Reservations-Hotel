"""Pruebas unitarias del arnés de caos (sin Docker)."""

import statistics

from harness import aggregate, classify_error, compute_outage_windows, _percentile  # noqa: E402
from harness import CanarySample, RequestSample  # noqa: E402


def _sample(ok: bool, latency: float = 10.0, status: int | None = 200,
            error_class: str = "") -> RequestSample:
    return RequestSample("baseline", "w", 0.0, "availability", "GET", latency,
                         status, error_class, None, ok)


def _csample(ok: bool, mono: float, status: int | None = 200,
             error: str | None = None) -> CanarySample:
    return CanarySample("w", mono, "availability", ok, status, error)


def test_compute_outage_windows_consecutive_fails():
    samples = [
        _csample(True, 0.0),
        _csample(False, 1.0),
        _csample(False, 2.0),
        _csample(False, 3.0),
        _csample(True, 4.0),
        _csample(True, 5.0),
    ]
    windows = compute_outage_windows(samples, min_consecutive=2)
    assert len(windows) == 1
    assert windows[0].start == 1.0
    assert windows[0].end == 3.0


def test_compute_outage_windows_single_fail_not_a_window():
    samples = [
        _csample(True, 0.0),
        _csample(False, 1.0),
        _csample(True, 2.0),
    ]
    assert compute_outage_windows(samples, min_consecutive=2) == []


def test_compute_outage_windows_open_at_end():
    samples = [
        _csample(True, 0.0),
        _csample(False, 1.0),
        _csample(False, 2.0),
        _csample(False, 3.0),
    ]
    windows = compute_outage_windows(samples, min_consecutive=2)
    assert len(windows) == 1
    assert windows[0].start == 1.0
    assert windows[0].end == 3.0


def test_percentile_known():
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert _percentile(values, 50) == 5.5
    assert _percentile(values, 100) == 10.0
    assert _percentile([], 50) == 0.0


def test_classify_error():
    from harness import classify_error
    assert classify_error(None, 500) == "5xx"
    assert classify_error(None, 422) == "4xx"
    assert classify_error(None, 200) == "other"
    assert "connection" in classify_error(Exception("ConnectError"), None)
    assert "timeout" in classify_error(Exception("ConnectTimeout"), None)


def test_aggregate_success_pct_and_errors():
    samples = [
        _sample(True, 10.0),
        _sample(True, 20.0),
        _sample(False, 5.0, status=500, error_class="5xx"),
        _sample(False, 5.0, status=500, error_class="5xx"),
        _sample(False, 5.0, status=422, error_class="4xx"),
    ]
    m = aggregate(samples)
    assert m["total"] == 5
    assert m["ok"] == 2
    assert m["success_pct"] == 40.0
    assert m["errors_by_class"] == {"5xx": 2, "4xx": 1}
    assert m["p50_ms"] == statistics.median([10.0, 20.0])

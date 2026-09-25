"""Tests for the lazy adapters and trade-lifecycle policy compatibility."""

import hashlib
import os

import pytest

from trade_mandate import adapters
from trade_mandate.adapters import resolve_policy
from trade_mandate.amend import MandateStore
from trade_mandate.mandate import new_mandate


@pytest.fixture()
def store(tmp_path):
    s = MandateStore(str(tmp_path))
    s.create("house", approver="Charlie", rationale="genesis",
             effective_date="2026-09-24")
    return s


def test_resolve_policy_finds_md(store, tmp_path):
    r = resolve_policy("house", [str(tmp_path)])
    assert r is not None
    assert r["path"].endswith("house.md")
    with open(r["path"], "rb") as fh:
        assert r["checksum"] == hashlib.sha256(fh.read()).hexdigest()


def test_resolve_policy_checksum_matches_lifecycle_algorithm(store, tmp_path):
    # trade-lifecycle's policy.policy_checksum is SHA-256 over raw file bytes;
    # our resolver must produce the identical digest for the same file.
    import sys
    sys.path.insert(0, "/home/hatch/workspace/trade-suite/trade-lifecycle/src")
    try:
        from trade_lifecycle.policy import policy_checksum
    except ImportError:
        pytest.skip("trade-lifecycle not on path")
    finally:
        sys.path.remove("/home/hatch/workspace/trade-suite/trade-lifecycle/src")
    r = resolve_policy("house", [str(tmp_path)])
    with open(r["path"], "rb") as fh:
        assert r["checksum"] == policy_checksum(fh.read())


def test_resolve_policy_missing_returns_none(tmp_path):
    assert resolve_policy("ghost", [str(tmp_path)]) is None


def test_load_mandate_round_trip(store, tmp_path):
    m = adapters.load_mandate("house", [str(tmp_path)])
    assert m["policy_id"] == "house" and m["version"] == 1


def test_load_mandate_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        adapters.load_mandate("ghost", [str(tmp_path)])


def test_pm_check_with_mandate_dict():
    m = new_mandate("house")
    proposal = {"orders": [], "equity": 100_000.0, "regime_conviction": 80,
                "current_drawdown": 0.0}
    r = adapters.pm_check(m, proposal)
    assert r["allowed"] is True
    assert any("mandate v1" in n for n in r["notes"])


def test_pm_check_fail_closed_without_mandate(tmp_path):
    r = adapters.pm_check("ghost", {"orders": []}, search_dirs=[str(tmp_path)])
    assert r["allowed"] is False
    assert r["violations"][0]["rule"] == "mandate.missing"


def test_pm_check_resolves_policy_id(store, tmp_path):
    proposal = {"orders": [], "equity": 100_000.0, "regime_conviction": 80,
                "current_drawdown": 0.0}
    r = adapters.pm_check("house", proposal, search_dirs=[str(tmp_path)])
    assert r["allowed"] is True


def test_risk_limits_shape():
    m = new_mandate("house")
    lim = adapters.risk_limits(m)
    assert lim == {
        "max_leverage": 1.5, "per_position_cap": 0.25,
        "max_single_name_weight": 0.10, "max_sector_weight": 0.35,
        "max_drawdown": 0.15, "vol_target": 0.12,
        "policy_id": "house", "mandate_version": 1,
    }


def test_check_against_lifecycle_policy_ok(store, tmp_path):
    r = resolve_policy("house", [str(tmp_path)])
    out = adapters.check_against_lifecycle_policy(
        "house", [str(tmp_path)], expected_checksum=r["checksum"])
    assert out["ok"] is True


def test_check_against_lifecycle_policy_tamper(store, tmp_path):
    out = adapters.check_against_lifecycle_policy(
        "house", [str(tmp_path)], expected_checksum="0" * 64)
    assert out["ok"] is False
    assert "mismatch" in out["reason"]


def test_check_against_lifecycle_policy_missing(tmp_path):
    out = adapters.check_against_lifecycle_policy("ghost", [str(tmp_path)])
    assert out["ok"] is False


def test_sibling_available_probe():
    assert adapters.sibling_available("json") is True
    assert adapters.sibling_available("definitely_not_a_package_xyz") is False


def test_adapters_module_has_no_hard_sibling_imports():
    # adapters.py must not import siblings at top level: parse the source
    src = open(os.path.join(os.path.dirname(adapters.__file__),
                            "adapters.py")).read()
    top = src.split('"""', 2)[2].split("def sibling_available")[0]
    for sib in ("trade_agents", "trade_risk", "trade_lifecycle", "trade_swing"):
        assert f"import {sib}" not in top and f"from {sib}" not in top

"""Tests for the Mandate schema, builder, checksum, and rendering."""

import pytest

from trade_mandate.mandate import (
    SCHEMA_VERSION, new_mandate, validate_mandate, mandate_checksum,
    render_markdown, DEFAULTS,
)
from trade_mandate.templates import get_preset, preset_names, PHILOSOPHY


def test_new_mandate_defaults():
    m = new_mandate("house")
    assert m["schema_version"] == SCHEMA_VERSION
    assert m["policy_id"] == "house"
    assert m["version"] == 1
    assert m["max_drawdown"] == DEFAULTS["max_drawdown"] == 0.15
    assert m["leverage_caps"]["portfolio"] == 1.5
    assert validate_mandate(m) == []


def test_new_mandate_overrides_merge_one_level():
    m = new_mandate("x", leverage_caps={"portfolio": 2.0})
    assert m["leverage_caps"]["portfolio"] == 2.0
    assert m["leverage_caps"]["per_position"] == 0.25  # default kept


def test_new_mandate_rejects_bad_values():
    with pytest.raises(ValueError):
        new_mandate("x", max_drawdown=1.5)          # not a fraction
    with pytest.raises(ValueError):
        new_mandate("x", max_drawdown=-0.1)
    with pytest.raises(ValueError):
        new_mandate("x", leverage_caps={"portfolio": 0})
    with pytest.raises(ValueError):
        new_mandate("x", concentration={"max_single_name_weight": 2.0})
    with pytest.raises(ValueError):
        new_mandate("x", forbidden_behaviors=["time_travel"])
    with pytest.raises(ValueError):
        new_mandate("x", order_constraints={"allowed_order_types": ["yolo"]})
    with pytest.raises(ValueError):
        new_mandate("x", regime_rules={"min_conviction_to_trade": 101})
    with pytest.raises(ValueError):
        new_mandate("x", allowed_instruments={
            "derivatives": {"allowed_types": ["naked_short_call"],
                            "forbidden": ["naked_short_call"]}})  # overlap


def test_new_mandate_requires_policy_id():
    with pytest.raises(ValueError):
        new_mandate("")


def test_checksum_deterministic_and_content_bound():
    m1 = new_mandate("a")
    m2 = new_mandate("a")
    assert mandate_checksum(m1) == mandate_checksum(m2)
    m2["max_drawdown"] = 0.10
    assert mandate_checksum(m1) != mandate_checksum(m2)
    # checksum field itself is excluded (no infinite regress)
    m1["checksum"] = mandate_checksum(m1)
    assert mandate_checksum(m1) == m1["checksum"]


def test_render_markdown_names_key_limits():
    m = new_mandate("house")
    m["checksum"] = mandate_checksum(m)
    md = render_markdown(m)
    assert "# Investment Mandate: house" in md
    assert "15%" in md  # max drawdown rendered
    assert "naked_short_options" in md
    assert m["checksum"] in md


def test_presets_valid_mandates():
    for name in preset_names():
        m = new_mandate(f"p-{name}", **get_preset(name))
        assert validate_mandate(m) == [], (name, validate_mandate(m))


def test_presets_have_philosophies():
    for name in preset_names():
        assert len(PHILOSOPHY[name]) > 40, name


def test_unknown_preset_rejected():
    with pytest.raises(ValueError):
        get_preset("reckless")


def test_conservative_tighter_than_aggressive():
    c = new_mandate("c", **get_preset("conservative"))
    a = new_mandate("a", **get_preset("aggressive"))
    assert c["max_drawdown"] < a["max_drawdown"]
    assert c["leverage_caps"]["portfolio"] < a["leverage_caps"]["portfolio"]
    assert (c["regime_rules"]["min_conviction_to_trade"]
            > a["regime_rules"]["min_conviction_to_trade"])
    # aggression is size, not recklessness: naked shorts forbidden in both
    assert "naked_short_call" in a["allowed_instruments"]["derivatives"]["forbidden"]

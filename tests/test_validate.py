"""Tests for check(): every violation class, the exit door, and the pass."""

import pytest

from trade_mandate.mandate import new_mandate
from trade_mandate.validate import check, resulting_weights


@pytest.fixture()
def mandate():
    return new_mandate("house")


def base(**kw):
    p = {
        "orders": [
            {"symbol": "AAPL", "side": "buy", "qty": 40, "price": 200.0,
             "order_type": "limit", "asset_class": "equity", "adv": 80_000_000},
        ],
        "current_positions": {
            "AAPL": {"weight": 0.02, "sector": "tech", "unrealized_pnl": 150.0},
        },
        "equity": 100_000.0,
        "regime_conviction": 62,
        "current_drawdown": 0.03,
        "holds_overnight": False,
    }
    p.update(kw)
    return p


def rules(result):
    return [v["rule"] for v in result["violations"]]


def test_valid_proposal_passes(mandate):
    r = check(mandate, base())
    assert r["allowed"], r["violations"]
    assert r["violations"] == []


def test_leverage_breach_names_rule_and_numbers(mandate):
    r = check(mandate, base(target_weights={"A": 0.6, "B": 0.6, "C": 0.6}))
    assert not r["allowed"]
    assert "leverage_caps.portfolio" in rules(r)
    v = next(x for x in r["violations"] if x["rule"] == "leverage_caps.portfolio")
    assert v["limit"] == 1.5 and v["observed"] == 1.8


def test_per_position_cap(mandate):
    r = check(mandate, base(target_weights={"AAPL": 0.30}))
    assert "leverage_caps.per_position" in rules(r)


def test_single_name_concentration(mandate):
    r = check(mandate, base(target_weights={"NVDA": 0.25}))
    assert not r["allowed"]
    assert "concentration.max_single_name_weight" in rules(r)


def test_sector_concentration():
    m = new_mandate("s", concentration={"max_sector_weight": 0.20,
                                        "max_single_name_weight": 0.10})
    p = base(target_weights={"AAPL": 0.09, "MSFT": 0.09, "NVDA": 0.09},
             current_positions={
                 "AAPL": {"weight": 0.0, "sector": "tech"},
                 "MSFT": {"weight": 0.0, "sector": "tech"},
                 "NVDA": {"weight": 0.0, "sector": "tech"}})
    r = check(m, p)
    assert "concentration.max_sector_weight" in rules(r)


def test_concentration_math_hand_computed(mandate):
    # 0.10 exactly is allowed (cap inclusive within epsilon)
    r = check(mandate, base(target_weights={"AAPL": 0.10}))
    assert "concentration.max_single_name_weight" not in rules(r)
    # 0.11 breaches
    r = check(mandate, base(target_weights={"AAPL": 0.11}))
    assert "concentration.max_single_name_weight" in rules(r)


def test_forbidden_derivative_refused(mandate):
    p = base(orders=[{"symbol": "SPY", "side": "sell", "qty": 10,
                      "price": 500.0, "order_type": "limit",
                      "asset_class": "option",
                      "instrument_type": "naked_short_call",
                      "adv": 10_000_000}])
    r = check(mandate, p)
    assert not r["allowed"]
    rs = rules(r)
    assert "allowed_instruments.derivatives.forbidden" in rs
    assert "forbidden_behaviors.naked_short_options" in rs


def test_unlisted_derivative_fails_closed(mandate):
    p = base(orders=[{"symbol": "SPY", "side": "buy", "qty": 10,
                      "price": 5.0, "order_type": "limit",
                      "asset_class": "option",
                      "instrument_type": "exotic_barrier",
                      "adv": 10_000_000}])
    r = check(mandate, p)
    assert "allowed_instruments.derivatives.allowed_types" in rules(r)


def test_symbol_allowlist(mandate):
    m = new_mandate("s", allowed_instruments={"symbols": ["AAPL", "MSFT"]})
    r = check(m, base())
    assert r["allowed"]
    p = base(orders=[{"symbol": "GME", "side": "buy", "qty": 10,
                      "price": 20.0, "order_type": "limit",
                      "asset_class": "equity", "adv": 50_000_000}])
    r = check(m, p)
    assert "allowed_instruments.symbols" in rules(r)


def test_asset_class_not_allowed(mandate):
    p = base(orders=[{"symbol": "BTC", "side": "buy", "qty": 1,
                      "price": 60_000.0, "order_type": "limit",
                      "asset_class": "crypto", "adv": 1_000_000}])
    r = check(mandate, p)
    assert "allowed_instruments.asset_classes" in rules(r)


def test_stand_down_blocks_new_risk(mandate):
    r = check(mandate, base(regime_conviction=10))
    assert not r["allowed"]
    assert "forbidden_behaviors.stand_down_trading" in rules(r)


def test_stand_down_exit_door_open(mandate):
    # selling to shrink a position during stand-down is allowed
    p = base(regime_conviction=10,
             current_positions={"AAPL": {"weight": 0.08, "sector": "tech",
                                         "unrealized_pnl": 100.0}},
             orders=[{"symbol": "AAPL", "side": "sell", "qty": 40,
                      "price": 200.0, "order_type": "limit",
                      "asset_class": "equity", "adv": 80_000_000}])
    r = check(mandate, p)
    assert r["allowed"], r["violations"]


def test_drawdown_stop_blocks_new_risk(mandate):
    r = check(mandate, base(current_drawdown=0.20))
    assert not r["allowed"]
    assert "max_drawdown" in rules(r)


def test_drawdown_stop_exit_door_open(mandate):
    p = base(current_drawdown=0.20,
             current_positions={"AAPL": {"weight": 0.08, "sector": "tech",
                                         "unrealized_pnl": -50.0}},
             orders=[{"symbol": "AAPL", "side": "sell", "qty": 40,
                      "price": 200.0, "order_type": "limit",
                      "asset_class": "equity", "adv": 80_000_000}])
    r = check(mandate, p)
    assert r["allowed"], r["violations"]
    assert any("drawdown stop" in n for n in r["notes"])


def test_overnight_leverage(mandate):
    p = base(holds_overnight=True, target_weights={"A": 0.6, "B": 0.6})
    r = check(mandate, p)
    assert "forbidden_behaviors.overnight_leverage" in rules(r)
    # same exposure intraday is fine on this rule
    p2 = base(holds_overnight=False, target_weights={"A": 0.6, "B": 0.6})
    r2 = check(mandate, p2)
    assert "forbidden_behaviors.overnight_leverage" not in rules(r2)


def test_martingale_averaging(mandate):
    p = base(
        current_positions={"TSLA": {"weight": 0.05, "sector": "auto",
                                    "unrealized_pnl": -800.0}},
        orders=[{"symbol": "TSLA", "side": "buy", "qty": 50, "price": 200.0,
                 "order_type": "limit", "asset_class": "equity",
                 "adv": 100_000_000}])
    r = check(mandate, p)
    assert "forbidden_behaviors.martingale_averaging" in rules(r)
    # adding to a WINNER is not martingale
    p2 = base(
        current_positions={"TSLA": {"weight": 0.05, "sector": "auto",
                                    "unrealized_pnl": 800.0}},
        orders=[{"symbol": "TSLA", "side": "buy", "qty": 50, "price": 200.0,
                 "order_type": "limit", "asset_class": "equity",
                 "adv": 100_000_000}])
    assert "forbidden_behaviors.martingale_averaging" not in rules(check(mandate, p2))


def test_oversized_order_vs_adv(mandate):
    p = base(orders=[{"symbol": "AAPL", "side": "buy", "qty": 5_000_000,
                      "price": 200.0, "order_type": "limit",
                      "asset_class": "equity", "adv": 80_000_000}])
    r = check(mandate, p)
    assert "order_constraints.max_order_pct_adv" in rules(r)


def test_disallowed_order_type(mandate):
    p = base(orders=[{"symbol": "AAPL", "side": "buy", "qty": 10,
                      "price": 200.0, "order_type": "stop",
                      "asset_class": "equity", "adv": 80_000_000}])
    r = check(mandate, p)
    assert "order_constraints.allowed_order_types" in rules(r)


def test_resulting_weights_from_orders():
    w = resulting_weights(base())
    # 40*200/100000 = 0.08 on top of 0.02
    assert abs(w["AAPL"] - 0.10) < 1e-9


def test_resulting_weights_target_wins():
    w = resulting_weights(base(target_weights={"X": 0.5}))
    assert w == {"X": 0.5}


def test_check_result_shape(mandate):
    r = check(mandate, base())
    assert set(r) >= {"allowed", "violations", "notes",
                      "resulting_gross_leverage", "mandate_version",
                      "policy_id"}
    assert r["mandate_version"] == 1

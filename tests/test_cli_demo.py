"""Tests for the demo theater determinism and the CLI surface."""

import json
import subprocess
import sys

from trade_mandate.demo import run_demo
from trade_mandate.cli import main as cli_main


def test_demo_deterministic():
    a = run_demo(seed=7)
    b = run_demo(seed=7)
    # strip the embedded v1 mandate (contains no timestamps) — compare rest
    a2 = {k: v for k, v in a.items() if k != "mandate"}
    b2 = {k: v for k, v in b.items() if k != "mandate"}
    assert a2 == b2


def test_demo_valid_passes_and_violations_refused():
    r = run_demo(seed=7)
    assert r["valid_proposal"]["allowed"] is True
    for name, v in r["violations"].items():
        assert v["allowed"] is False, name
        assert v["rules"], name


def test_demo_violation_rules_named():
    r = run_demo(seed=7)["violations"]
    assert "concentration.max_single_name_weight" in r["concentration"]["rules"]
    assert "leverage_caps.portfolio" in r["leverage"]["rules"]
    assert "allowed_instruments.derivatives.forbidden" in r["forbidden_instrument"]["rules"]
    assert "forbidden_behaviors.stand_down_trading" in r["stand_down"]["rules"]
    assert "order_constraints.max_order_pct_adv" in r["order_size"]["rules"]
    assert "forbidden_behaviors.martingale_averaging" in r["martingale"]["rules"]


def test_demo_exit_door_and_amendment_and_tamper():
    r = run_demo(seed=7)
    assert r["exit_door_open"] is True
    assert r["amendment"]["ratified_version"] == 2
    assert r["amended_max_drawdown"] == 0.12
    assert r["verify_clean"] is True
    assert r["verify_tampered"]["ok"] is False
    assert r["verify_tampered"]["tampered_files"] == ["json_sha256"]


def test_demo_pm_hook_fail_closed():
    r = run_demo(seed=7)["pm_hook"]
    assert r["with_mandate"] is True
    assert r["without_mandate_refused"] is True


def _run_cli(*argv, store):
    return cli_main(["--store", store, *argv])


def test_cli_new_show_verify(tmp_path):
    store = str(tmp_path)
    assert _run_cli("new", "house", "--preset", "balanced",
                    "--approver", "Charlie", "--rationale", "genesis",
                    "--effective-date", "2026-09-24", store=store) == 0
    assert _run_cli("show", "house", "--json", store=store) == 0
    assert _run_cli("verify", "house", store=store) == 0


def test_cli_new_unsigned_refused(tmp_path):
    store = str(tmp_path)
    assert _run_cli("new", "house", "--preset", "balanced", store=store) == 1


def test_cli_check_pass_and_refuse(tmp_path):
    store = str(tmp_path)
    _run_cli("new", "house", "--preset", "balanced", "--approver", "C",
             "--rationale", "g", "--effective-date", "2026-09-24", store=store)
    ok_path = str(tmp_path / "ok.json")
    with open(ok_path, "w") as fh:
        json.dump({"orders": [], "equity": 100_000.0,
                   "regime_conviction": 80, "current_drawdown": 0.0}, fh)
    assert _run_cli("check", "house", "--proposal", ok_path,
                    "--json", store=store) == 0
    bad_path = str(tmp_path / "bad.json")
    with open(bad_path, "w") as fh:
        json.dump({"target_weights": {"A": 0.6, "B": 0.6, "C": 0.6},
                   "equity": 100_000.0, "regime_conviction": 80,
                   "current_drawdown": 0.0}, fh)
    assert _run_cli("check", "house", "--proposal", bad_path,
                    "--json", store=store) == 1


def test_cli_amend_flow(tmp_path):
    store = str(tmp_path)
    _run_cli("new", "house", "--preset", "balanced", "--approver", "C",
             "--rationale", "g", "--effective-date", "2026-09-24", store=store)
    assert _run_cli("amend", "house", "--changes", '{"max_drawdown": 0.12}',
                    "--proposer", "C", "--json", store=store) == 0
    # ratify without sign-off refused
    assert _run_cli("amend", "house", "--ratify", "house-a2", "--json",
                    store=store) == 1
    assert _run_cli("amend", "house", "--ratify", "house-a2",
                    "--approver", "C", "--rationale", "tighter",
                    "--effective-date", "2026-09-25", "--json",
                    store=store) == 0
    assert _run_cli("history", "house", "--json", store=store) == 0


def test_cli_presets_and_demo(tmp_path):
    store = str(tmp_path)
    assert _run_cli("presets", store=store) == 0
    assert _run_cli("demo", "--seed", "7", store=store) == 0


def test_cli_as_subprocess_json(tmp_path):
    # exercises the console-script path end to end
    store = str(tmp_path / "sub")
    cmd = [sys.executable, "-m", "trade_mandate", "--store", store,
           "new", "house", "--preset", "conservative",
           "--approver", "C", "--rationale", "g",
           "--effective-date", "2026-09-24", "--json"]
    import os
    env = dict(os.environ, PYTHONPATH=os.path.join(
        os.path.dirname(__file__), "..", "src"))
    out = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["version"] == 1

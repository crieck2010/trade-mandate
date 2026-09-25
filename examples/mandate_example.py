"""Full walkthrough: ratify a mandate, check proposals, amend it."""

import json
import tempfile

from trade_mandate.adapters import pm_check, risk_limits, resolve_policy
from trade_mandate.amend import MandateStore
from trade_mandate.demo import run_demo
from trade_mandate.templates import get_preset
from trade_mandate.validate import check

store_dir = tempfile.mkdtemp(prefix="mandate-example-")
store = MandateStore(store_dir)

# 1. Ratify the constitution (sign-off required — no unsigned genesis)
store.create("house", approver="Charlie",
             rationale="first live mandate; swing system only",
             effective_date="2026-09-24", **get_preset("balanced"))
mandate = store.load("house")
print("ratified:", mandate["policy_id"], "v%d" % mandate["version"])

# 2. A sensible proposal passes
proposal = {
    "orders": [{"symbol": "AAPL", "side": "buy", "qty": 40, "price": 200.0,
                "order_type": "limit", "asset_class": "equity",
                "adv": 80_000_000}],
    "current_positions": {},
    "equity": 100_000.0,
    "regime_conviction": 62,
    "current_drawdown": 0.03,
}
result = check(mandate, proposal)
print("sensible proposal allowed:", result["allowed"])

# 3. A reckless one is refused with the rules named
reckless = dict(proposal, target_weights={"A": 0.6, "B": 0.6, "C": 0.6})
result = check(mandate, reckless)
print("reckless proposal allowed:", result["allowed"])
for v in result["violations"]:
    print("  refused by:", v["rule"], "—", v["detail"])

# 4. The PM hook: fail-closed without a mandate
print("pm_check with mandate:",
      pm_check("house", proposal, search_dirs=[store_dir])["allowed"])
print("pm_check without mandate refused:",
      not pm_check("ghost", proposal, search_dirs=[store_dir])["allowed"])

# 5. Feed the numbers to trade-risk
print("risk limits:", json.dumps(risk_limits(mandate), indent=None)[:120], "...")

# 6. trade-lifecycle compatibility: resolve + checksum like its gate does
resolved = resolve_policy("house", [store_dir])
print("resolved:", resolved["path"].split("/")[-1],
      "sha256:", resolved["checksum"][:16], "...")

# 7. Amend with sign-off, then verify integrity
a = store.propose_amendment("house", {"max_drawdown": 0.12}, proposer="Charlie")
store.ratify("house", a["amendment_id"], approver="Charlie",
             rationale="tighter leash", effective_date="2026-09-25")
print("amended to v%d," % store.load("house")["version"],
      "verify:", store.verify("house")["ok"])

# 8. The full theater
theater = run_demo(seed=7)
print("theater: valid=%s violations_refused=%s tamper_caught=%s" % (
    theater["valid_proposal"]["allowed"],
    all(not v["allowed"] for v in theater["violations"].values()),
    not theater["verify_tampered"]["ok"]))

# trade-mandate

The machine-readable investment policy — the portfolio manager's written
constitution. A versioned, checksummed mandate constraining every
allocation decision, amendable only with explicit human sign-off.

Part of the [trade-suite](https://github.com/crieck2010/trade-suite)
algorithmic trading system. It is the full implementation behind the
policy hooks `trade-lifecycle` v0.1.0 already records (`policy_id` +
SHA-256): this module writes the `<policy_id>.md` that `trade-lifecycle`
discovers and the `<policy_id>.json` that is actually enforced.

## Install

```bash
pip install trade-mandate
# or from source
git clone https://github.com/crieck2010/trade-mandate
cd trade-mandate
pip install -e .
```

Requires Python 3.10+. No third-party dependencies — not even NumPy.

## Quick start

```python
from trade_mandate.amend import MandateStore
from trade_mandate.templates import get_preset
from trade_mandate.validate import check

store = MandateStore("./mandates")
store.create("house", approver="Charlie", rationale="initial constitution",
             effective_date="2026-09-24", **get_preset("balanced"))
mandate = store.load("house")

proposal = {
    "orders": [{"symbol": "AAPL", "side": "buy", "qty": 40, "price": 200.0,
                "order_type": "limit", "asset_class": "equity",
                "adv": 80_000_000}],
    "current_positions": {},
    "equity": 100_000.0,
    "regime_conviction": 62,   # trade-regime 0-100
    "current_drawdown": 0.03,
}
result = check(mandate, proposal)
print(result["allowed"])          # True
print(result["violations"])       # []
```

A refused proposal names every rule:

```python
bad = dict(proposal, target_weights={"A": 0.6, "B": 0.6, "C": 0.6})
result = check(mandate, bad)
print(result["allowed"])          # False
print(result["violations"][0]["rule"])    # leverage_caps.portfolio
print(result["violations"][0]["detail"])  # gross exposure 1.800x exceeds ...
```

The PM-agent hook fails closed — no mandate, no trading:

```python
from trade_mandate import adapters
adapters.pm_check("house", proposal, search_dirs=["./mandates"])  # allowed
adapters.pm_check("ghost", proposal, search_dirs=["./mandates"])  # REFUSED
```

CLI:

```bash
trade-mandate new house --preset balanced --approver Charlie \
    --rationale "initial constitution" --effective-date 2026-09-24
trade-mandate show house --markdown
trade-mandate check house --proposal proposal.json   # exit 1 on refusal
trade-mandate amend house --changes '{"max_drawdown": 0.12}' --proposer Charlie
trade-mandate amend house --ratify house-a2 --approver Charlie \
    --rationale "tighter leash" --effective-date 2026-09-25
trade-mandate history house
trade-mandate verify house        # tamper detection
trade-mandate demo                # the mandate theater
trade-mandate presets
```

See `examples/mandate_example.py` for the full walkthrough.

## The maths

**What you learn.** How to turn "don't blow up" into arithmetic: the exact
numbers that separate an allowed allocation from a refused one, and the
paper trail that proves which constitution was in force when.

**Why it matters.** Agents without a mandate are smart interns with no
constitution — they will find the cleverest way to do the wrong thing at
scale. A fund's risk committee doesn't give vibes; it gives limits. This
module is those limits, in code, with amendments requiring your signature.

**The maths.**

- *Leverage.* Gross exposure `G = Σ|wᵢ|` over equity, capped at
  `leverage_caps.portfolio`; each `|wᵢ|` capped at `per_position`.
  1.8x gross against a 1.5x cap refuses — no judgment call, just arithmetic.
- *Drawdown.* `DD = (peak − equity) / peak`. Beyond `max_drawdown`, new
  risk is refused but the exit door stays open: risk-reducing orders
  (they shrink `|wᵢ|`) always pass. The mandate constrains entries, never
  exits.
- *Concentration (Herfindahl-flavored).* Single-name `|wᵢ|` and sector
  `Σ|wᵢ|` caps. The deeper read is the Herfindahl index `H = Σwᵢ²` with
  effective breadth `1/H`: ten equal 10% positions give `H = 0.10`
  (effective N = 10); one 50% position plus dust gives `H ≈ 0.25`
  (effective N ≈ 4). Caps are the enforceable proxy; `1/H` is the diagnostic.
- *Vol-target scaling.* To hold portfolio volatility near `vol_target`
  `σ*`, scale gross exposure by `σ*/σ̂` where `σ̂` is estimated portfolio
  vol. The mandate stores the target; the sizer (e.g. `trade-risk`) does
  the scaling. Target without measurement is a wish — see limitations.
- *Fractional Kelly (wired via trade-risk).* `f = fraction · (p − (1−p)/b)`
  with win rate `p` and payoff ratio `b`, capped. Full Kelly maximizes
  log-growth and drawdowns in equal measure; the mandate's leverage and
  concentration caps are what keep a Kelly sizer honest.
- *Amendment integrity.* SHA-256 over the canonical JSON payload
  (sorted keys, no whitespace ambiguity) binds content to version; SHA-256
  over raw file bytes binds the rendered `.md` to what `trade-lifecycle`
  checksummed at sign-off. `verify()` recomputes both against the
  append-only history anchor. Any byte changed without ratification is
  tampering, detected, not debated.

**Honest limitations.** A mandate constrains *stated* behavior, not
intent: twenty small correlated positions sail under single-name caps —
catching that needs the correlation engine (`trade-eda`), not this one.
Forbidden-behavior patterns are syntactic (an "overnight leverage" check
can't see intent, only `holds_overnight` and gross exposure). The history
file is the trust anchor and is only as tamper-proof as its storage;
mirror it off-machine in production. And the mandate is only as wise as
its author — it prevents skipping steps and breaking stated limits, not
bad judgment encoded as generous limits.

## Interop

Stable `schema_version: 1` mandate contract (see `docs/ARCHITECTURE.md`).
Writes `<policy_id>.json` (machine constitution) and `<policy_id>.md`
(human constitution) with byte-identical SHA-256 semantics to
`trade-lifecycle`'s `policy.resolve_policy()` — a checksum recorded by
`trade-lifecycle`'s PAPER→LIVE gate verifies here unchanged. Lazy
adapters: `pm_check()` for the `trade-agents` portfolio manager (call
before any allocation; fail-closed), `risk_limits()` feeding `trade-risk`,
`resolve_policy()` for `trade-lifecycle`. No hard dependencies; siblings
are probed, never required.

## Docs

- `docs/ARCHITECTURE.md` — module map, data flow, scaling, mandate contract
- `docs/METHODOLOGY.md` — every check's formula and its failure modes
- `docs/MANDATE.md` — the constitution-writing guide: how to write your
  own mandate, field by field, with worked examples
- `CHANGELOG.md` — release history

## License

MIT. See `LICENSE`.

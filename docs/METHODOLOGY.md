# METHODOLOGY — trade-mandate

Every check's formula, and how each one can be wrong.

## Weight computation

`resulting_weights(proposal)`:

- If `target_weights` is present, it wins outright: `{symbol: weight}` is
  the portfolio after the proposal. Fractions of equity; shorts negative.
- Otherwise, orders apply onto `current_positions` weights:
  `Δw = side × qty × price / equity`, summed per symbol.

Assumption: `price` is the expected fill. Stale prices → wrong weights →
wrong verdicts. Garbage in, garbage out — the mandate checks arithmetic,
not market data quality.

## Check families

**Drawdown gate.** `DD = current_drawdown` (supplied by the caller —
typically `trade-risk` or the ledger). If `DD > max_drawdown`, every
non-risk-reducing order is refused. Risk-reducing =
`resulting |wᵢ| < current |wᵢ| − ε`. The exit door is never locked.

**Leverage.** `G = Σ|wᵢ| ≤ leverage_caps.portfolio`; each
`|wᵢ| ≤ leverage_caps.per_position`. Gross, not net: a 100% long / 100%
short book is 2.0x, not 0x.

**Concentration.** `|wᵢ| ≤ max_single_name_weight`; per-sector
`Σ|wᵢ| ≤ max_sector_weight` using the `sector` field on current
positions. Positions without a sector tag are invisible to the sector
cap — tag your universe or the cap is decorative.

**Instruments.** Symbol allowlist when `symbols` is set (None = any
symbol in the allowed asset classes). Derivative `instrument_type` must
not be in `forbidden`; for `asset_class == "option"`, an *unlisted* type
is refused (fail-closed). Non-option orders without `instrument_type`
are treated as plain equity — the default `asset_class` is `"equity"`.

**Behaviors (syntactic — read the caveats).**

- `naked_short_options`: `instrument_type ∈ {naked_short_call,
  naked_short_put}` → refused.
- `overnight_leverage`: `holds_overnight ∧ G > 1.0` → refused. The
  module cannot see the clock; it trusts the caller's flag.
- `stand_down_trading`: `regime_conviction < min_conviction_to_trade` →
  any order that is not risk-reducing is refused (one violation explains
  the stand-down; the rest would be noise).
- `martingale_averaging`: order grows `|wᵢ|` of a position with
  `unrealized_pnl < 0` → refused. Adding to winners is untouched.

**Orders.** `qty / adv > max_order_pct_adv` → refused (caller supplies
`adv`; missing ADV skips the check — documented, not silent: without
ADV data there is nothing to compare against). `order_type` must be
listed.

## Amendments

`propose_amendment` stages changes against the current version; the
mandate file is untouched. `ratify` requires approver id, rationale, and
effective date — any missing, refused. Changes merge one level deep onto
the current mandate, the result re-validated, version bumped, files
rewritten, history appended. An amendment based on a stale version is
refused (re-propose on current). Ratification rewrites the amendments
log marking the record `ratified`.

`verify()` compares fresh SHA-256s of both artifacts against the latest
history entry, plus a payload-checksum round-trip. Mismatch on either
file, or a payload checksum that doesn't recompute, → tampered.

## Presets

`conservative` (10% DD, 1.0x, 5% single-name, limit-only, conviction
40), `balanced` (the defaults: 15% DD, 1.5x, 10%, conviction 25),
`aggressive` (25% DD, 2.0x, 15%, conviction 15 — still no naked shorts,
no martingale), `blank` (permissive schema so every number is a deliberate
choice). Philosophies in `templates.PHILOSOPHY`.

## Failure modes of the methodology itself

- Caps are per-name; correlated names dodge them. Needs `trade-eda`.
- Behavior patterns match order shapes, not intent.
- `verify()` trusts the history file; a forged history blesses a forgery.
- A mandate with generous limits "passes" everything — the law is only
  as wise as the legislator. That's why amendments need *your* signature.

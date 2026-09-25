# MANDATE.md — the constitution-writing guide

How Charlie (or anyone) writes their own mandate, field by field, with
worked examples. A mandate is a risk committee's decisions written down
*before* money is at stake, when you're calm — not during a drawdown,
when you're not.

## The one rule

Every number must be chosen on a calm day and hard to change on a bad
day. That's the entire philosophy. If you can loosen the drawdown cap
mid-drawdown with no friction, you don't have a mandate — you have a
suggestion. Amendments require your explicit sign-off, a rationale, and
an effective date precisely so future-you can't quietly rewrite the law
mid-crisis.

## Field by field

**`max_drawdown`** — the fraction of peak equity you'll tolerate before
new risk is refused. Worked example: with $10,000 funded, `0.15` means a
$1,500 drawdown from the peak locks the exit door open and the entry
door shut until recovery. Set it where you'd *want* to be stopped, not
where you think you'll never reach. Most retail systems die between 20%
and 30%; 15% is a working default.

**`vol_target`** — annualized portfolio volatility you're aiming for.
12% is roughly a balanced equity portfolio; 20% is aggressive. This is a
*target*, not a cap: it tells the sizer how hard to press, while the
leverage and concentration caps say how far it may go. If you don't
measure portfolio vol anywhere, set the target anyway — it's the number
`trade-risk` will steer toward once it can.

**`allowed_instruments`** — what the system may touch, and what it may
not. Start narrow: `["equity", "etf"]`. Add `"option"` only with the
derivatives lists filled in deliberately. The `forbidden` list should
always contain `naked_short_call` and `naked_short_put` — undefined risk
has no place in an automated system, at any preset. A `symbols` allowlist
(`["SPY", "QQQ", "AAPL", ...]`) is the strongest instrument control you
have: with it set, a stray symbol from a data bug is refused, not traded.

**`leverage_caps`** — `portfolio` is gross exposure over equity (1.5 =
$15,000 of positions on $10,000). `per_position` is the single-name
weight ceiling from the leverage side (0.25). Keep `per_position` below
`max_single_name_weight`'s intent or the two caps argue; the tighter one
wins silently, which is fine as long as you know which it is.

**`concentration`** — `max_single_name_weight: 0.10` means no position
above 10% of equity. `max_sector_weight: 0.35` needs sector tags on your
positions — untagged positions are invisible to it, so tag the universe
or drop the cap rather than pretend. Worked example: five 10% tech
positions = 50% tech > 35% cap → refused, correctly: that's a sector bet
wearing a diversification costume.

**`forbidden_behaviors`** — the four the engine understands:

- `naked_short_options` — never sell undefined-risk premium. No exceptions.
- `overnight_leverage` — no >1.0x gross held past the close. Gap risk is
  the risk you can't stop out of.
- `stand_down_trading` — when `trade-regime` conviction falls below your
  minimum, no new risk. Exits always allowed.
- `martingale_averaging` — never add to losers. The most expensive
  sentence in trading is "it'll come back."

**`order_constraints`** — `max_order_pct_adv: 0.05` keeps any single
order under 5% of average daily volume (your fills stop moving the
market against you). `allowed_order_types: ["limit"]` for the
conservative; add `"market"` when you accept paying the spread for
certainty. Note: the ADV check needs ADV data on the order — without it,
the check skips (documented), so feed it.

**`regime_rules`** — `min_conviction_to_trade: 25` means the regime
arbiter must read at least 25/100 constructive before new risk opens.
`stand_down_flat: true` is the honest setting: below the bar, flat is a
position. Set it false only if you have a strategy designed to trade
defensive regimes — and if you do, say so in the rationale when you
ratify.

## Worked example: Charlie's first mandate

```
policy_id: house
preset: balanced, then amended:
  max_drawdown: 0.12        # tighter leash after the vol spike (amendment a2)
  symbols: [SPY, QQQ, AAPL, MSFT, NVDA]   # no stray symbols, ever
  regime_rules.min_conviction_to_trade: 30
rationale (recorded): "First live mandate. Swing system only, defined-risk
  options later. Revisit after one quarter of paper."
```

## Amending without lying to yourself

1. `trade-mandate amend house --changes '{...}' --proposer Charlie` —
   stages, changes nothing.
2. Sleep on it. Seriously.
3. `trade-mandate amend house --ratify house-a2 --approver Charlie
   --rationale "..." --effective-date YYYY-MM-DD` — now it's law.
4. `trade-mandate history house` — the paper trail.
5. `trade-mandate verify house` — periodically; catches tampering.

Never loosen a limit during the drawdown it was designed for. If you
must, the rationale field will preserve exactly what you were thinking —
that's the point.

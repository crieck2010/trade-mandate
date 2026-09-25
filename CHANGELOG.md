# Changelog — trade-mandate

## v0.1.0 — 2026-09-24

Initial release: the machine-readable investment policy (the PM agent's
written constitution).

- `mandate.py`: schema v1, `new_mandate()` builder with type/range
  validation, canonical SHA-256 payload checksum, human `.md` rendering
- `validate.py`: `check(mandate, proposal)` — drawdown gate, leverage
  caps, concentration caps, instrument allowlists, four forbidden-behavior
  patterns (naked shorts, overnight leverage, stand-down trading,
  martingale averaging), order constraints (ADV participation, order
  types); risk-reducing exits always allowed
- `amend.py`: `MandateStore` — create/propose/ratify/history/verify;
  sign-off required for every ratification; SHA-256 tamper detection on
  both artifacts
- `templates.py`: conservative / balanced / aggressive / blank presets
  with documented philosophies
- `adapters.py`: lazy `pm_check()` (fail-closed), `risk_limits()` for
  trade-risk, `resolve_policy()` byte-compatible with trade-lifecycle's
  checksum algorithm
- `demo.py`: deterministic mandate theater (valid → six violations →
  exit door → amendment → tamper caught)
- Full CLI; `docs/MANDATE.md` constitution-writing guide
- 69 tests, fresh-clone verified

# ARCHITECTURE — trade-mandate

## Position in the system

```
trade-lifecycle ──policy_id + checksum──▶ trade-mandate
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    ▼                         ▼                         ▼
              trade-agents               trade-risk               trade-hedge
           (PM calls pm_check()      (risk_limits() feeds      (mandate caps
            before any allocation;    sizers: Kelly, ATR,       inform hedge
            fail-closed)              vol-target)               triggers)
```

`trade-mandate` is the constitution; `trade-lifecycle` is the
legislature's procedure. The lifecycle gates *reference* a mandate
(`policy_id` + SHA-256 of the `.md`); this module *authors, versions,
and enforces* it. Neither executes trades — `trade-paper` never
consults either, keeping permission and execution in separate failure
domains by design.

## Module map

| Module | Responsibility |
|---|---|
| `mandate.py` | Schema v1, `new_mandate()` builder + validation, canonical checksum, `.md` rendering |
| `validate.py` | `check(mandate, proposal)` — pure functions, plain data in/out |
| `amend.py` | `MandateStore`: create / propose / ratify / history / verify (tamper detection) |
| `templates.py` | `conservative` / `balanced` / `aggressive` / `blank` presets + philosophies |
| `adapters.py` | Lazy `pm_check()`, `risk_limits()`, `resolve_policy()`, lifecycle-checksum verification |
| `demo.py` | Deterministic mandate theater (valid → violations → amendment → tamper) |
| `cli.py` | Full command surface; refusals exit non-zero |
| `licensing.py` | License-key / update-check hooks (suite convention) |

## The check pipeline

`check()` runs six independent check families over the proposal and
concatenates violations — no early exit, so a refusal lists *everything*
wrong, not just the first problem:

1. `check_drawdown` — beyond max DD: new risk refused, exits allowed
2. `check_leverage` — portfolio gross + per-position caps
3. `check_concentration` — single-name + sector caps
4. `check_instruments` — allowlists, derivative allow/forbid (fail-closed)
5. `check_behaviors` — naked shorts, overnight leverage, stand-down,
   martingale (syntactic patterns, documented)
6. `check_orders` — ADV participation, allowed order types

Resulting weights come from `target_weights` when present (absolute
intent), else orders applied onto current position weights. Every
violation carries `{rule, detail, limit, observed, ...}` — a refusal
without numbers is a shrug.

## Store layout

```
<store>/
  <policy_id>.json            # machine mandate (includes payload checksum)
  <policy_id>.md              # human rendering (trade-lifecycle checksums this)
  <policy_id>.history.jsonl   # append-only: every ratification + both SHAs
  <policy_id>.amendments.jsonl# pending + ratified amendment records
```

Checksums: SHA-256 over canonical JSON (sorted keys, compact separators)
for the payload; SHA-256 over raw file bytes for the artifacts — the
latter byte-identical to `trade_lifecycle.policy.policy_checksum`, so a
checksum recorded at the PAPER→LIVE transition verifies here unchanged.

## Scaling

`check()` is a pure function over small dicts — microseconds, no I/O,
no locks. It parallelizes trivially: one process can gate thousands of
proposals per second; sharding is unnecessary at any realistic size.
`MandateStore` is file-based and single-writer by convention (amendments
are rare, human-paced events); concurrent writers are out of scope for
v0.1.0 and documented as such. History is append-only JSONL — replay is
the audit.

## Failure domains (deliberate)

- A corrupt or missing mandate **refuses** (fail-closed). There is no
  "default allow."
- `trade-paper` never imports `trade-mandate`: if the constitution
  module is down, the PM hook refuses and nothing trades — execution
  cannot outrun permission.
- Tamper detection trusts the history file; mirror it off-machine in
  production (documented, not solved, in v0.1.0).

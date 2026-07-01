# ReplicAudit

**A research-reproducibility registry where GenLayer validators reach consensus on whether a study replicates.**

[![GenLayer](https://img.shields.io/badge/GenLayer-Bradbury-ff4d6d)](https://genlayer.com) [![chainId](https://img.shields.io/badge/chainId-4221-4dd0e1)](https://docs.genlayer.com) [![contract](https://img.shields.io/badge/contract-Python%20GenVM-8a63d2)](https://docs.genlayer.com) [![tests](https://img.shields.io/badge/tests-4%2F4%20passing-3fb950)](tests) [![License](https://img.shields.io/badge/license-MIT-2dd4bf)](LICENSE)

An author registers a study — a **claim**, the **methods**, and a link to the **data**. An independent
replicator later files a **replication report** describing what they observed when they re-ran the
methods. `assess` then has every validator independently compare the original claim against the
replication and decide one verdict — accepted only when validators agree on the **outcome** enum
(`replicates` / `partial` / `fails`), not on the wording of the reasoning.

The verb is **"decide whether an independent replication reproduces a claimed result"** — distinct from
scoring a debate or ranking entries; it is a one-shot reproducibility audit of one study against one
replication report.

- **Contract (Bradbury, chain 4221):** `DEPLOY_PENDING`
- **Deployed from:** `rivale`
- **Explorer:** https://explorer-bradbury.genlayer.com/contract/DEPLOY_PENDING

---

## Why GenLayer is essential

Deciding whether a replication reproduces a study's claim is qualitative judgment over natural-language
methods and results — impossible to compute on a deterministic EVM. GenLayer has every validator read
the same claim + replication report and accept a verdict only when they **agree on the outcome enum**,
turning a subjective reproducibility call into a single, reproducible on-chain result. The registry is
also tamper-evident: the claim, methods, replication report, and final outcome are all recorded on-chain.

## Workflow

| Step | Method | What happens |
| --- | --- | --- |
| Register | `submit_study(claim, methods, data_url)` | Author records the claim, methods, and data link; returns the study id. |
| Replicate | `submit_replication(study_id, report, result_url)` | An independent replicator attaches their report; state stays `open`. |
| Assess | `assess(study_id)` | Consensus compares claim vs replication → `outcome` (`replicates` / `partial` / `fails`) + reasoning. |
| Read | `get_study(study_id)` / `stats()` | Full record + outcome; totals (`total_studies`, `assessed`). |

## Correctness check

`_assess` wraps the local `do_assess` in **`gl.eq_principle.prompt_comparative`** with the principle
*"the outcome enum (replicates / partial / fails) must be identical across validators; reasoning wording
may differ."* This is what catches a **wrong** decision: validators must converge on the same decisive
enum, not merely return JSON of the same shape. A validator that returns `partial` when the report
clearly contradicts the claim breaks equivalence and is rejected. `validate_assessment` enforces the
outcome enum + a non-empty reasoning; `normalize_assessment` clamps any unknown/garbled outcome to the
conservative default `fails`, trims the reasoning, and **never raises** (so `{}` from a silent model
still yields a valid record). On-chain guards enforce the `open → assessed` state machine: you cannot
`assess` before a replication report exists, and you cannot re-assess or replicate a finished study.

## Architecture

Contract-only — **no frontend**.

```
ReplicAudit/
├── contracts/replic_audit.py  ← GenLayer Intelligent Contract (registry + consensus reproducibility verdict)
└── tests/                     ← pytest: normalize/validate guards + full submit → replicate → assess flow
```

## Tests

```bash
python3 -m venv .venv && .venv/bin/pip install pytest -q
.venv/bin/python -m pytest tests -q
```

Covers `normalize_assessment` / `validate_assessment` on good **and** adversarial inputs (bad enum →
`fails`, non-dict, empty reasoning), plus a full **register → replicate → assess** integration run that
asserts the `open → assessed` transition and that the finalized `outcome` is within the valid enum
(the shim's consensus returns the normalized default).

## Deploy

```bash
genlayer deploy --contract contracts/replic_audit.py
```

The deployed address replaces `DEPLOY_PENDING` in `.env.example` and above.

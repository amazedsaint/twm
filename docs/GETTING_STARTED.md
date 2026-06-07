# Getting Started

Transactional Reversible World Model is an executable research workbench for
audited proposal systems. A proposal may rank or suggest a candidate, but it
cannot commit state. Commit authority stays with typed projection, hard
verification, replay, rollback, manifest checks, and hash-chained receipts.

The short control loop is:

```text
propose -> project -> hard verify -> commit or rollback -> receipt -> learn
```

## Current Boundary

The repository currently supports a `G1` evidence grade: deterministic unit
tests, browser demos, and local synthetic experiments. It is not a learned-model
safety proof, a robotics safety case, a public benchmark result, or a claim that
reversibility alone improves held-out performance.

The active real-task proof path starts with
`python3 -m examples.real_task_benchmark_manifest` for preflight, then
`python3 -m examples.real_task_execution_plan` for a certificate-bound run
contract, and finally `python3 -m examples.real_task_evidence_bundle` for the
auditable proof artifact. The bundle command runs the robotics, hardware,
program, and quantum benchmark adapters, rebuilds the aggregate suite from
those exact child results, and rejects unless all real backends produce
manifest-covered, report-bound adapter evidence certificates, compact
receipt-bound execution provenance hashes, normalized backend execution
evidence hashes, receipt-bound task/candidate artifact hashes, supported
held-out call-reduction evidence, and zero invalid commits.

The current implementation includes:

- a Python package under `trwm/`,
- a TypeScript ESM library under `src/` with built browser output in `dist/`,
- standalone demos under `html/`,
- Python tests under `tests/`,
- TypeScript tests under `test-ts/`,
- a long design record in `transactional_reversible_world_model_full_proposal.md`,
- a concise research boundary in `docs/research_hypothesis.md`.

`dist/` is checked in deliberately so the HTML demos can run from a static file
server or GitHub Pages-style host without requiring a local build step.

## Verify Everything

From the repository root:

```sh
python3 -m unittest
python3 -m trwm.demo
node --disable-warning=ExperimentalWarning scripts/build.mjs
node --disable-warning=ExperimentalWarning scripts/check-dist-fresh.mjs
node --test test-ts/*.test.mjs
```

To open the demos:

```sh
python3 -m http.server 8765
```

Then visit `http://localhost:8765/html/`.

## What Is Unique Here

The distinctive direction is not another latent dynamics model. TRWM is a
transaction layer around untrusted proposers. The unusual combination is:

- hard-verifier authority over every commit,
- reversible replay and rollback as first-class audit checks,
- receipts and certificates that bind learner updates back to source evidence,
- RRLM-style reversible proposal artifacts that remain inspectable but never
  become commit authority,
- world-program replay packages that validate the trace, candidate, receipt,
  step-certificate, learner-update, and learner-delta bodies before promotion.

This makes the project closer to an auditable runtime-assurance substrate for
proposal systems than to a standalone model architecture.

## Reading Order

1. Start with this file.
2. Read `README.md` for the package map and runnable surfaces.
3. Read `docs/research_hypothesis.md` for the evidence boundary and claim
   limits.
4. Use `html/index.html` to explore the demos.
5. Read `transactional_reversible_world_model_full_proposal.md` only when you
   want the full proposal and rationale.

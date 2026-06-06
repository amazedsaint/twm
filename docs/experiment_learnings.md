# Experiment Learnings

The new examples push the same pattern across robotics, molecular dynamics, and
materials:

```text
proposal is useful for search -> transaction owns physical validity -> receipt teaches the next proposal
```

## What Improved

- Robotics showed that a high soft score for a short path must not outrank a
  signed-distance safety violation. Residuals can repair the path while commit
  authority stays with the hard verifier.
- Molecular dynamics showed that the candidate must bind the integrator, not
  just a plausible next state. The verifier rejects Euler when the contract is a
  velocity-Verlet step, then commits the repaired state with bounded energy and
  momentum drift.
- Material lattice dynamics showed that proposal randomness belongs in the
  receipt. A Metropolis accept/reject decision is auditable only when the
  Hamiltonian delta, beta, uniform sample, and post-flip lattice are bound.

## Substrate Direction

The frontier is a programmable transactional world model where each scientific
domain contributes:

- a typed state and candidate schema,
- a hard verifier that owns the domain law,
- a replay/rollback adapter,
- residuals that are specific enough to repair proposals,
- manifests or replay packages that bind evidence before claim promotion.

The current examples suggest the next hardening step: promote a shared example
report/certificate shape so every domain can publish the same fields for
receipt hashes, verifier identity, replay status, rollback status, residual
kinds, and claim boundary.

## Certified Evidence Layer

The examples now use `trwm.example_evidence_certificate.v1` to bind each local
report to verifier identity, ledger head, receipt hashes, replay/rollback
status, invalid-commit count, hard-gate keys, residual kinds, claim boundary,
and source URLs. This moves the examples from narrative reports to bounded G1
claim artifacts.

The aggregate frontier report confirms the same substrate requirements across
all three domains:

- typed physical state,
- hard law verifier,
- receipt-bound randomness or dynamics parameters,
- replay/rollback adapter,
- residual repair surface,
- evidence certificate before claim promotion.

This is still a local G1 result. It improves claim discipline and implementation
shape, but it is not a robotics safety case, production molecular-dynamics
validation, materials discovery evidence, or proof of broad scientific
autonomy.

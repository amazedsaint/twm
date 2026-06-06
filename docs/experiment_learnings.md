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

## Branches Of The Past

The ancestral branch exploration example adds the next substrate lesson:
exploration itself should be replayable. Across the robotics-replan,
molecule-repair, and material-process toy domains, each training episode
records three branch outcomes:

- a hard-rejected attractive proposal,
- an accepted but rolled-back loser,
- a committed winner.

The later budget-one static pass spends its only verifier call on the old first
proposal and fails in all three domains. The past-branch-guided pass ranks the
previously committed branch first and commits in all three domains, still only
after the hard verifier and replay/rollback checks pass.

This evolves the design in one concrete way: "branch of past" data should be a
first-class proposal-ordering input with its own certificate, not an informal
memory side channel. The new `trwm.ancestral_branch_exploration_certificate.v1`
binds report hash, ledger head, receipt hashes, branch-selection certificate
hashes, static versus learned exploration success, winner-rank improvement,
hard-gate keys, residual kinds, replay/rollback status, and claim boundary.

The follow-up substrate primitive is `trwm.ancestral`. `AncestralBranchMemory`
learns only from statically valid receipts, rejects branch updates whose
`BranchSelectionCertificate` fails validation or receipt audit, deduplicates
receipt hashes, and emits `trwm.ancestral_branch_memory_snapshot.v1`. That
snapshot binds the learning weights, receipt hashes, branch-selection
certificate hashes, per-context action stats, and snapshot hash. The certified
ancestral branch example now binds this memory snapshot into its exploration
certificate.

The next programmable transactional world model substrate therefore needs:

- ancestral branch retrieval keyed by typed context,
- hash-checked ancestral memory snapshots,
- branch-selection certificate replay before learned ordering is trusted,
- budget-aware proposal ordering separate from commit authority,
- residual categories that distinguish unsafe rejects from safe dominated
  losers,
- claim promotion gates that prove exploration improvement under the same
  verifier budget.

The analogical branch transfer example adds one more design constraint:
cross-context reuse must name its ancestor contexts explicitly. For each toy
domain, two positive ancestor contexts reorder the target budget-one search
toward the previously committed action. A separate misleading ancestor context
also reorders the target search, but toward an action that is unsafe under the
target payload; the hard verifier rejects that proposal in all domains. The
substrate lesson is that context-neighborhood selection is now part of the
world-model surface and needs certificates before it can become trusted
proposal evidence.

The boundary remains narrow. This is a deterministic G1 canary inspired by
experience replay, counterfactual regret evidence, and selective tree-search
sampling; it is not a statistical exploration algorithm, regret guarantee,
MCTS implementation, automatic similarity metric, or cross-domain scientific
discovery result.

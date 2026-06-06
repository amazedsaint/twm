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

The context-selection transfer example makes that surface explicit. Each source
and target context now has an `AncestralContextDescriptor` with domain, family,
hard-gate keys, residual kinds, and required tags. The
`trwm.ancestral_context_selection_certificate.v1` artifact selects compatible
ancestors and records rejected contexts with reasons such as
`tag_mismatch:regime`. Across the three toy domains, selected ancestors commit
under the same one-call target budget, while a bypass attempt using the rejected
context is blocked by the target hard verifier. This moves the design from
"explicitly named ancestors" to "certified ancestor retrieval."

The context-refinement transfer example closes the loop from failed target
branches back into retrieval. A coarse selector that omits `regime` admits
misleading ancestors, ranks their unsafe action first, and records a hard
rejected target receipt. The
`trwm.ancestral_context_refinement_certificate.v1` artifact binds that
counterexample receipt, the base selection certificate, the added `regime` tag,
and the refined selection certificate. The refined selector narrows the ancestor
set and commits under the same one-call target budget. This is the first local
evidence that branches of the past can improve exploration policy itself, not
only candidate order.

The context-query-policy transfer example adds held-out checks for that policy
update. Each domain uses one calibration target to record the coarse-query
counterexample and refinement certificate, then applies the refined required-tag
policy to two sibling targets. The sibling stale-query baselines still rank the
unsafe misleading action first and fail under one verifier call. The refined
query policy ranks the committed action first and commits in all six held-out
transfers under the same one-call budget. The new
`trwm.context_query_policy_certificate.v1` artifact binds the counterexample
receipt, base and refined selection certificates, each held-out sibling
selection, top actions, receipt hashes, and same-budget comparison. The
substrate implication is that retrieval refinement should be a portable query
policy artifact before it is treated as reusable exploration improvement on
future contexts.

The context-retention transfer example adds the next memory transition. After
refinement commits, the committed target branch is retained with a
`trwm.ancestral_branch_retention_certificate.v1` artifact that binds the
pre-memory snapshot hash, post-memory snapshot hash, retained context
descriptor hash, retained receipt hash, audited branch-selection certificate
hash, and memory row/receipt deltas. A sibling target then uses the retained
target context as its only ancestor. The new
`trwm.ancestral_branch_influence_certificate.v1` artifact binds the exact
memory snapshot, query context, candidate action set, ranked order, top action,
and supporting receipt hashes before the sibling target spends verifier budget.
The same report now adds
`trwm.context_retention_influence_ablation_certificate.v1`, comparing a static
sibling pass and an influence-ranked sibling pass under one verifier call each.
The static sibling pass fails in all three toy domains; the influence-ranked
sibling pass commits in all three under the same hard verifier. This turns the
loop into:

```text
retrieve -> fail -> refine -> commit -> retain -> certify influence -> compare same-budget baseline -> improve sibling exploration
```

The substrate implication is that world-model memory needs certified mutation
and certified query, plus a matched ablation certificate before claiming
exploration improvement. A programmable transactional world model should be
able to prove when a branch becomes reusable future evidence, which memory
snapshot it entered, which later proposal order was derived from that retained
branch, and whether that proposal order beat a same-budget non-influenced
baseline.

The boundary remains narrow. This is a deterministic G1 canary inspired by
experience replay, counterfactual regret evidence, and selective tree-search
sampling; it is not a statistical exploration algorithm, regret guarantee,
MCTS implementation, automatic similarity metric, CEGAR system, or cross-domain
scientific discovery result.

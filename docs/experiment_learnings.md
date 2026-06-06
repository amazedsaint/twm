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

The branch-counterfactual transfer example isolates accepted but rolled-back
losers. Each domain records a source branch with one hard reject, one committed
winner, and one accepted loser that is rolled back because it was not selected.
The target then makes the prior winner stale. A stale-winner one-call baseline
fails in all three domains, while the counterfactual one-call branch commits
the previously rolled-back accepted action in all three domains. The new
`trwm.branch_counterfactual_certificate.v1` artifact binds source winner
receipts, accepted-loser rollback receipts, stale target rejects,
counterfactual target commits, branch-selection certificates, and the
same-budget comparison. The substrate implication is that rollback is not just
undo machinery: accepted losers are reusable counterfactual evidence, but only
after a certificate separates them from committed authority.

The branch-abstraction transfer example adds option-family evidence. Each
domain records a source branch where a concrete source action commits inside an
abstract family. The target makes that exact source action stale, so exact
one-call replay fails in all three domains. A different target-specific action
in the same family commits in all three domains under the same one-call budget.
The new `trwm.branch_abstraction_certificate.v1` artifact binds source family,
source commit receipts, stale exact target rejects, same-family target commits,
branch-selection certificates, and the same-budget comparison. The substrate
implication is that past branch evidence needs typed abstraction levels: exact
action reuse, family-level reuse, and composed reuse should be separate
certified surfaces rather than one memory score.

The branch-prerequisite transfer example adds stateful ordering evidence. Each
domain records source receipts where a prerequisite action commits before the
final action. The target static branch spends two verifier calls on final and
distractor actions without first satisfying the target prerequisite, so it
commits nothing. The guided target spends the same two calls on target
prerequisite and final actions; both commit through the hard verifier and
replay/rollback audit. The new `trwm.branch_prerequisite_certificate.v1`
artifact binds source prerequisite/final receipts, static target rejects,
guided prerequisite/final commits, branch-selection certificates, and the
same-budget comparison. The substrate implication is that branch memory needs
stateful ordering certificates: a useful branch of the past may say what must
be true before another proposal is worth spending verifier budget on.

The branch-contingency transfer example adds context-feature switchpoints. Each
domain records one source branch for a stale/default regime and one source
branch for the target regime. The target static branch spends one verifier call
on the stale-regime action and fails. The contingent target spends the same one
verifier call on the source branch whose regime tag matches the target, and it
commits through the hard verifier. The new
`trwm.branch_contingency_certificate.v1` artifact binds stale and matched
source receipts, static target rejects, contingent target commits,
branch-selection certificates, selected/rejected source contexts, and the
same-budget comparison. The substrate implication is that branch memory needs
conditional reuse certificates: a past branch may be useful only under a typed
target-context feature, and stale unconditional reuse should fail closed.

The branch-hindsight relabel transfer example adds goal labels to rejected
branch evidence. Each domain records a source branch that is physically valid
but misses its intended goal while exposing a different achieved goal. The
target static branch spends one verifier call on a direct proposal and fails.
The hindsight-relabeled target spends the same one verifier call on the achieved
goal branch, and it commits only after fresh target hard verification. The new
`trwm.branch_hindsight_relabel_certificate.v1` artifact binds source reject
receipts, intended goals, achieved/relabeled goals, static target rejects,
relabeled target commits, branch-selection certificates, and the same-budget
comparison. The substrate implication is that rejected receipts can suggest new
exploration goals, but relabeling is proposal evidence only; it must be
separated from commit authority by a fresh target receipt.

The branch-intervention transfer example adds typed field edits to branch
evidence. Each domain records a source branch with one hard reject and one
committed repair that differ in a verifier-critical field: robot clearance,
molecular strain, or material thermal gradient. The target static branch spends
one verifier call on the unedited candidate and fails. The intervention target
spends the same one verifier call on the field-edited candidate and commits
only after fresh target hard verification. The new
`trwm.branch_intervention_certificate.v1` artifact binds source reject/commit
receipts, source and target before/after values, static target rejects,
intervened target commits, branch-selection certificates, and the same-budget
comparison. The substrate implication is that branches of the past can propose
which typed variable to edit, but the edit is not a causal-inference result or
commit authority.

The branch-diagnostic probe transfer example adds active probing evidence. Each
domain records a source branch where a cheap prior probe is rejected and a
diagnostic probe commits an observation: corridor regime, molecular site
regime, or thermal regime. The target static branch spends the same two
verifier calls on unprobed final actions and fails. The guided target spends
one verifier call on the diagnostic probe and one verifier call on the
observation-bound final action; both commit only after fresh target hard
verification. The new `trwm.branch_diagnostic_probe_certificate.v1` artifact
binds source probe reject/commit receipts, static unprobed rejects, guided
probe/final commits, branch-selection certificates, and the same-budget
comparison. The substrate implication is that branches of the past can propose
what to measure before acting, but the measurement and action still require
their own receipts.

The branch-residual template transfer example adds repair-template evidence.
Each domain records a source branch with a rejected proposal and a committed
repair, then maps the residual kind to a named repair template for the target
branch. The static target spends one verifier call on the unsafe proposal and
fails; the template-guided target spends the same one verifier call on the
template-produced proposal and commits only after fresh target hard
verification. The new `trwm.branch_residual_template_certificate.v1` artifact
binds the source reject/repair receipts, static target reject, templated target
commit, branch-selection certificates, template fields, and same-budget
comparison. The substrate implication is that residual repair templates can
propose structured edits, but they cannot transfer commit authority.

The branch-boundary bracket transfer example adds threshold-neighborhood
evidence. Each domain records a source unsafe endpoint and a source safe
endpoint, then uses that reject/commit pair to prioritize a target candidate
near the hard-gate boundary. The static target spends one verifier call on the
unsafe endpoint and fails; the bracket-guided target spends the same one
verifier call on the boundary candidate and commits only after fresh target
hard verification. The new `trwm.branch_boundary_bracket_certificate.v1`
artifact binds the source reject/safe receipts, static target reject, bracketed
target commit, branch-selection certificates, bracket fields, and same-budget
comparison. The substrate implication is that past branches can narrow where to
look near a verifier boundary, but cannot certify the boundary candidate
without a target receipt.

The branch-consensus transfer example adds multi-source agreement evidence.
Each domain records two source branches that support a safe proposal family and
one singleton source branch that supports a tempting family. The static target
spends one verifier call on the singleton-family proposal and fails; the
consensus-guided target spends the same one verifier call on the majority-family
proposal and commits only after fresh target hard verification. The new
`trwm.branch_consensus_certificate.v1` artifact binds majority source receipts,
the singleton source receipt, static target reject, consensus target commit,
support counts, branch-selection certificates, and same-budget comparison. The
substrate implication is that source agreement can rank target proposals, but
majority support is still not commit authority.

The branch-invariant transfer example adds positive/negative contrast evidence.
Each domain records two committed source branches and two rejected source
branches, then binds the fields that separate those receipt classes as an
invariant signature. The static target spends one verifier call on a tempting
proposal outside the invariant and fails; the invariant-guided target spends
the same one verifier call on a matching proposal and commits only after fresh
target hard verification. The new `trwm.branch_invariant_certificate.v1`
artifact binds positive source receipts, negative source receipts, invariant
field keys, static target reject, invariant target commit, branch-selection
certificates, and same-budget comparison. The substrate implication is that
positive/negative past branches can filter target proposals, but the filter is
not a classifier or commit authority.

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
companion `trwm.context_branch_conflict_certificate.v1` artifact binds the
conflict explicitly: committed source receipts support the stale unsafe action,
the calibration and sibling target receipts reject that action, and the refined
query policy commits the target action at the same budget. The substrate
implication is that retrieval refinement should be a portable query policy
artifact before it is treated as reusable exploration improvement on future
contexts, and contradictory past evidence should be resolved by a certificate
rather than by raw memory score alone.

The context-drift quarantine example adds a validity-scope check. Each domain
records an old-epoch source branch whose committed action becomes stale for the
current target. A stale query reuses that old branch and fails under one
verifier call. An epoch-aware selection certificate then quarantines the old
context, selects current-compatible branch evidence, and commits under the same
one-call budget. The new `trwm.context_drift_quarantine_certificate.v1` artifact
binds stale source commits, current source commits, stale target rejects,
current target commits, selected/quarantined context ids, and the quarantine
reason. The substrate implication is that memory needs explicit validity scope:
old branches should not influence exploration just because they once committed.

The branch-pruning transfer example adds negative-evidence admission. Each
domain records a source branch with two hard-rejected actions and one committed
winner. The unpruned target spends the same two-call verifier budget on the
known-dead actions and commits nothing. The pruning certificate removes those
actions from the target candidate set, and the pruned target commits under the
same two-call budget. The new `trwm.branch_pruning_certificate.v1` artifact
binds source reject receipts, source commit receipts, target baseline rejects,
pruned target receipts, branch-selection certificates, pruned action ids, and
the same-budget comparison. The substrate implication is that rejected branches
can improve exploration by shaping verifier-budget allocation, but pruning is
only an admission filter; surviving candidates still need hard-verifier
receipts before commit.

The branch-diversity transfer example adds coverage pressure. Each domain
records two same-family source rejects and one committed repair. The repeated
family target baseline spends two verifier calls on the same saturated failure
family and commits nothing. The diversity-certified target spends the same two
verifier calls across a distinct failure family and the repair family, then
commits after hard verification. The new
`trwm.branch_diversity_certificate.v1` artifact binds the saturated family id,
candidate action families, source reject receipts, source commit receipts,
target repeated-family receipts, target diverse-family receipts,
branch-selection certificates, and same-budget comparison. The substrate
implication is that exploration memory needs coverage certificates in addition
to ranking and pruning certificates: a failed family should be able to force a
budgeted search to cover a different family, but that pressure is not commit
authority.

The branch-budget transfer example adds explicit verifier-cost allocation. Each
domain records past receipts for two cheap reject probes and one higher-cost
repair. The static target spends the same three-unit verifier budget on the two
cheap rejects, then abstains the repair because the remaining budget is too
small. The budget-allocated target spends one cheap probe plus the higher-cost
repair, and commits under the same total budget. The new
`trwm.branch_budget_certificate.v1` artifact binds memory receipts, static and
allocated target receipt hashes, abstain counts, exact spent verifier cost, and
the same-budget comparison. The substrate implication is that past branches
should be allowed to shape resource allocation only through receipt-bound cost
certificates: resource policy can decide which hard checks to spend, but it
still cannot commit without a domain verifier receipt.

The branch-stop-rule transfer example adds explicit no-good abstention. Each
domain records two source rejects from a matched failure family and one source
commit as a positive control. The static target spends two verifier calls on
the matched failure family and commits nothing. The stop-rule target sees the
same target candidate surface but records two abstain receipts, spends zero
verifier calls, and promotes no target commit. The new
`trwm.branch_stop_rule_certificate.v1` artifact binds source rejects, source
commits, static target rejects, stop-rule abstentions, branch-selection
certificates, unused verifier budget, and the same-budget comparison. The
substrate implication is that past branches should sometimes improve
exploration by proving when not to explore: abstention is a first-class
receipt outcome, not missing data.

The branch-composition transfer example adds a proposal-construction check.
Each domain records two source branches whose committed receipts stand for
distinct hard-gate fragments. A static target branch fails under one verifier
call, and both single-fragment target branches also fail under one verifier
call. Only the composed target proposal, built from both receipt-bound
fragments, commits under the same one-call budget. The new
`trwm.branch_composition_certificate.v1` artifact binds source contexts,
fragment keys, source commit/reject receipts, target static/component/composed
receipts, branch-selection certificates, and the same-budget comparison. The
substrate implication is that reusable past branches need a construction layer
as well as a ranking layer: fragments may shape a proposal, but the composed
proposal still needs its own hard-verifier receipt before any claim can be
promoted.

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

The branch-history frontier report now aggregates the twenty-three local branch-memory
stages in `trwm.example.branch_history_frontier.v1`. It checks evidence
certificates, primary experiment certificates, and claim certificates for raw
receipt-bound ordering, accepted-loser counterfactual reuse, option-family
abstraction, stateful prerequisite ordering, regime-conditioned contingency
reuse, hindsight goal relabeling, receipt-bound field intervention,
receipt-bound diagnostic probing, residual-template repair, boundary
bracketing, source consensus, contrastive invariant transfer, analogical
ancestor reuse, certified context selection, counterexample refinement,
conflict-aware query-policy transfer,
drift quarantine, receipt-bound branch pruning, diversity-certified family
coverage, receipt-bound budget allocation, no-good stop-rule abstention, branch composition, and retained
memory influence.
This changes the design posture from isolated demos to a staged substrate map:
each branch-history capability must expose its own certificate, and later
stages are only meaningful if earlier evidence still validates.

The boundary remains narrow. This is a deterministic G1 canary inspired by
experience replay, counterfactual regret evidence, and selective tree-search
sampling plus nogood-style pruning, diversity pressure, and recombinable
building-block search plus successive resource allocation and temporal
abstraction plus contextual bandits with side information and hindsight
experience replay plus intervention notation as a variable-edit analogy and
experimental-design information as a probe-selection analogy plus case-based
reuse/revise as a residual-template analogy plus safe exploration as a
boundary-bracketing analogy plus query-by-committee as a source-consensus
analogy plus version-space learning as a positive/negative invariant analogy
plus nogood learning and backjumping as a stop-rule analogy;
it is not a
statistical exploration algorithm, regret guarantee, MCTS implementation,
automatic similarity metric, CEGAR system, CDCL solver, novelty-search result,
MAP-Elites implementation, Hyperband implementation, options-framework result,
contextual-bandit result, Hindsight Experience Replay result, causal-inference result, do-calculus result, Bayesian experimental-design result, active-learning result, query-by-committee result, version-space learning result, safe Bayesian optimization result, case-based reasoning system, genetic algorithm, program synthesizer, or
cross-domain scientific discovery result.

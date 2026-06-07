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

The branch-curriculum transfer example generalizes one prerequisite into a
monotone easy-to-hard sequence. Each domain records a source sequence with two
curriculum steps and one final commit. The target static branch spends three
verifier calls on a direct final, a skipped-level step, and a bad early-level
candidate, committing nothing. The guided target spends the same three calls
on level 1, level 2, and final target actions; all three commit through fresh
hard verification and replay/rollback audit. The new
`trwm.branch_curriculum_certificate.v1` artifact binds source curriculum
receipts, static target rejects, guided curriculum commits, guided final
commits, branch-selection certificates, and the matched three-call budget. The
substrate implication is that branch memory needs certified continuation
surfaces: a useful branch of the past may define the order of target
difficulty, but every intermediate and final state still needs its own receipt.

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

The branch-trust-region transfer example adds proposal-radius evidence. Each
domain records one source branch outside a radius cap that rejects and one
bounded source branch that commits. The static target spends one verifier call
on an oversized proposal and fails; the trust-region target spends the same
one verifier call on a bounded proposal and commits only after fresh target
hard verification. The new `trwm.branch_trust_region_certificate.v1` artifact
binds source reject/commit receipts, source and target proposal radii, the
trusted radius cap, static target reject, trust-region target commit,
branch-selection certificates, and same-budget comparison. The substrate
implication is that past branches can shape the scale of exploration before
they shape action ranking: a proposal radius cap is evidence for candidate
construction, not commit authority.

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

The branch-recency weight transfer example adds a freshness check inside valid
branch history. Each domain records two older source commits for a stale action,
then a recent source branch where that stale action is rejected and an adapted
action commits. The cumulative-history target spends one verifier call on the
stale action and fails; the recency-window target spends the same one verifier
call on the adapted action and commits. The new
`trwm.branch_recency_certificate.v1` artifact binds old stale commit receipts,
recent stale reject receipts, recent adapted commit receipts, static target
rejects, recency target commits, branch-selection certificates, and the
same-budget comparison. The substrate implication is that memory needs
receipt-freshness policy in addition to validity scope: recent verified
counterevidence should be able to override older cumulative support, but only
through a certificate and fresh target verification.

The branch-restart transfer example adds restart-anchor evidence. Each domain
records a source branch where a local continuation is rejected and a restart
anchor commits. The static target spends one verifier call on the matching local
continuation and fails; the restart-guided target spends the same verifier call
on the restart anchor and commits. The new
`trwm.branch_restart_certificate.v1` artifact binds source local-dead-end
rejects, source restart-anchor commits, static target rejects, restart target
commits, branch-selection certificates, and the same-budget comparison. The
substrate implication is that memory should be able to certify when exploration
should backtrack or restart from a known anchor, but the restart action still
needs its own target hard-verifier receipt before commit.

The branch-symmetry transfer example adds typed transform evidence. Each
domain records a source branch where a mirrored or reflected action commits.
Exact replay of that source action in the target spends one verifier call and
fails; the symmetry-guided target spends the same verifier call on the
transformed action and commits. The new
`trwm.branch_symmetry_certificate.v1` artifact binds the transform id, source
commit receipt, static exact-replay reject, symmetry target commit,
branch-selection certificates, and the same-budget comparison. The substrate
implication is that memory should be able to carry typed transforms over past
branches, but a transform is only proposal evidence. The transformed target
action still needs its own hard-verifier receipt before commit.

The branch-constraint transfer example adds pairwise relation evidence. Each
domain records a source branch where an incompatible pair is rejected and a
compatible pair commits. The static target spends one verifier call on the
incompatible pair and fails; the constraint-guided target spends the same
verifier call on the compatible pair and commits. The new
`trwm.branch_constraint_certificate.v1` artifact binds the incompatible pair,
compatible pair, source reject/commit receipts, target baseline reject, target
compatible commit, branch-selection certificates, and the same-budget
comparison. The substrate implication is that branch memory needs relation
certificates, not only unary action scores: a past branch can shape which
combinations are worth trying, but the surviving combination still needs its
own target hard-verifier receipt before commit.

The branch-confidence transfer example adds support-strength evidence. Each
domain records one thin optimistic source commit and three better-supported
source commits. The static target spends one verifier call on the thin
optimistic action and fails; the confidence-guided target spends the same
verifier call on the better-supported action and commits. The new
`trwm.branch_confidence_certificate.v1` artifact binds the source support
counts, source receipt hashes, fixed Wilson-style lower bounds, target baseline
reject, target confidence commit, branch-selection certificates, and the
same-budget comparison. The substrate implication is that branch memory needs
support certificates before sparse successes can influence exploration:
thin positive evidence is still only proposal evidence, and the selected target
branch still needs its own hard-verifier receipt before commit.

The branch-pareto transfer example adds multi-objective dominance evidence.
Each domain records a source branch where a scalar-favored action is rejected
and a nondominated balanced action commits. The static target spends one
verifier call on the scalar action and fails; the Pareto-guided target spends
the same verifier call on the nondominated action and commits. The new
`trwm.branch_pareto_certificate.v1` artifact binds dominated and Pareto
objective vectors, source reject/commit receipts, target scalar replay reject,
target Pareto commit, branch-selection certificates, and the same-budget
comparison. The substrate implication is that branch memory needs
multi-objective evidence certificates: a past branch can say which tradeoff is
dominated, but the surviving nondominated target branch still needs its own
hard-verifier receipt before commit.

The branch-outlier-filter transfer example adds feature-provenance evidence for
source-valid but anomalous branches. Each domain records two inlier source
commits and one source outlier commit. The static target spends one verifier
call replaying the anomalous source branch and fails; the inlier-filtered
target spends the same verifier call on a target action near the source inlier
cluster and commits. The new `trwm.branch_outlier_filter_certificate.v1`
artifact binds inlier feature values, source outlier distance, distance
threshold, source inlier/outlier receipts, static target reject, filtered
target commit, branch-selection certificates, and same-budget comparison. The
substrate implication is that source validity is not enough for target
priority: branch memory needs feature-distance provenance certificates before
an anomalous but committed source branch can influence exploration.

The branch-provenance-guard transfer example adds source-id admission evidence.
Each domain records two trusted source commits and one source-valid quarantined
commit. The static target spends one verifier call replaying the quarantined
source branch and fails; the provenance-guarded target spends the same verifier
call on a trusted-source branch and commits. The new
`trwm.branch_provenance_guard_certificate.v1` artifact binds trusted source
ids, quarantined source id, trusted/quarantined source receipts, static target
reject, guarded target commit, branch-selection certificates, and same-budget
comparison. The substrate implication is that source-valid receipts can remain
in the ledger while being excluded from target proposal priority: branch memory
needs source-id guard certificates before untrusted provenance can influence
exploration.

The branch-credit-assignment transfer example adds marginal-contribution
evidence for source branch fragments. Each domain records three source commits:
one high-credit fragment and two source-valid distractors. The static target
spends one verifier call replaying a low-credit distractor and fails; the
credit-guided target spends the same verifier call on the high-credit fragment
and commits. The new `trwm.branch_credit_assignment_certificate.v1` artifact
binds source actions, credit values, credited and distractor source receipts,
static target reject, credit target commit, branch-selection certificates, and
same-budget comparison. The substrate implication is that source-valid branch
fragments should not all receive equal proposal priority: branch memory needs
marginal-credit certificates before correlated source commits can influence
target exploration.

The branch-propensity-match transfer example adds covariate-comparability
evidence for source branch reuse. Each domain records one source-valid but
covariate-mismatched commit and one source-valid matched commit. The static
target spends one verifier call replaying the mismatched branch and fails; the
propensity-matched target spends the same verifier call on the matched branch
and commits. The new `trwm.branch_propensity_match_certificate.v1` artifact
binds target/source covariates, propensity-style scores, caliper distance,
covariate L1 distance, source receipts, static target reject, matched target
commit, branch-selection certificates, and same-budget comparison. The
substrate implication is that branch memory needs context-comparability
certificates before a source-valid branch can influence target proposal
priority.

The branch-robustness transfer example adds uncertainty-set coverage evidence
for source branch reuse. Each domain records one source-valid nominal branch and
three robust source commits across perturbation variants. The static target
spends one verifier call replaying the brittle nominal branch and fails; the
robust target spends the same one verifier call on the uncertainty-set-covered
action and commits. The new `trwm.branch_robustness_certificate.v1` artifact
binds variant ids, source and target contexts, brittle source receipts, robust
source receipts, positive robust margins, static target reject, robust target
commit, branch-selection certificates, and same-budget comparison. The substrate
implication is that source-valid history is not enough for robust reuse:
branch memory needs receipt-bound uncertainty-set coverage certificates before
a nominally successful past branch can influence target priority.

The branch-calibration transfer example adds proposer-confidence admission
evidence for source branch reuse. Each domain records one overconfident source
reject and three lower-confidence source receipts whose empirical accept rate
matches the confidence bin. The static target spends one verifier call
replaying the overconfident source family and fails; the calibrated target
spends the same one verifier call on the confidence-bin-supported action and
commits. The new `trwm.branch_calibration_certificate.v1` artifact binds
confidence-bin ids, predicted confidence values, empirical accept rates,
calibration gaps, source receipts, static target reject, calibrated target
commit, branch-selection certificates, and same-budget comparison. The
substrate implication is that proposer confidence is not branch authority:
branch memory needs receipt-bound calibration certificates before soft scores
can influence target proposal priority.

The branch-conformal transfer example adds nonconformity-envelope admission
evidence for source branch reuse. Each domain records three in-envelope source
calibration commits and one out-of-envelope source reject. The static target
spends one verifier call replaying an out-of-envelope source-like action and
fails; the conformal target spends the same one verifier call on an in-envelope
target action and commits. The new `trwm.branch_conformal_certificate.v1`
artifact binds alpha, quantile rank, calibration nonconformity scores, source
calibration receipt hashes, out-of-envelope source reject, static target
reject, conformal target commit, branch-selection certificates, and same-budget
comparison. The substrate implication is that branch memory needs
receipt-bound nonconformity quantile certificates before soft nonconformity
scores can filter source replay.

The branch-active-subspace transfer example adds low-rank direction admission
evidence for source branch reuse. Each domain records two source commits whose
direction vectors project onto a one-dimensional active axis, plus one rejected
source proposal on the orthogonal axis. The static target spends one verifier
call replaying an orthogonal proposal and fails; the active-subspace target
spends the same one verifier call on an in-subspace proposal and commits. The
new `trwm.branch_active_subspace_certificate.v1` artifact binds active and
orthogonal basis vectors, dot-product projection scores, projection threshold,
source active receipts, source orthogonal reject, static target reject,
active-subspace target commit, branch-selection certificates, and same-budget
comparison. The substrate implication is that branch memory needs
receipt-bound low-rank direction certificates before learned search subspaces
can filter target proposals.

The branch-sensitivity transfer example adds one-factor perturbation admission
evidence for source branch reuse. Each domain records a negative perturbation
that rejects and a positive perturbation that commits. The static target spends
one verifier call on the wrong perturbation direction and fails; the
sensitivity-guided target spends the same one verifier call on the useful
direction and commits. The new `trwm.branch_sensitivity_certificate.v1`
artifact binds parameter id, baseline value, perturbation delta, source
negative and positive receipts, static wrong-direction target reject,
sensitivity-guided target commit, branch-selection certificates, and
same-budget comparison. The substrate implication is that branch memory needs
receipt-bound sensitivity-axis certificates before parameter-direction evidence
can filter target proposals.

The branch-shield-fallback transfer example adds runtime guard/fallback
admission evidence for source branch reuse. Each domain records an unsafe
source proposal that rejects and a fallback proposal that commits. The static
target spends one verifier call on the unsafe family and fails; the
shield-guided target spends the same one verifier call on the fallback family
and commits. The new `trwm.branch_shield_fallback_certificate.v1` artifact
binds shield spec id, unsafe family, fallback family, source unsafe reject,
source fallback commit, static unsafe target reject, shield target commit,
branch-selection certificates, and same-budget comparison. The substrate
implication is that branch memory needs receipt-bound shield/fallback
certificates before runtime guard evidence can filter target proposals.

The branch-potential-heuristic transfer example adds search-priority evidence
for source branch reuse. Each domain records a high-potential source proposal
that rejects and a low-potential source proposal that commits. The static
target spends one verifier call on a high-potential target proposal and fails;
the heuristic-guided target spends the same one verifier call on a
low-potential proposal and commits. The new
`trwm.branch_potential_heuristic_certificate.v1` artifact binds potential id,
threshold, high-potential source reject, low-potential source commit, static
high-potential target reject, low-potential target commit, branch-selection
certificates, and same-budget comparison. The substrate implication is that
branch memory needs receipt-bound heuristic-potential certificates before
estimated cost-to-feasible-state evidence can rank target proposals.

The branch-continuation transfer example adds path-following admission evidence
for source branch reuse. Each domain records three source continuation commits
along a lambda schedule and one source direct-jump reject. The static target
spends the same three verifier calls on direct jump proposals and commits
nothing; the continuation target spends three verifier calls on intermediate
target steps and commits each step. The new
`trwm.branch_continuation_certificate.v1` artifact binds lambda values, max
lambda step, source path receipts, source direct-jump reject, static target
rejects, continuation target commits, branch-selection certificates, and
same-budget comparison. The substrate implication is that branch memory needs
receipt-bound path certificates before continuation-style schedules can filter
direct target jumps.

The branch-commutativity transfer example adds partial-order admission evidence
for source branch reuse. Each domain records two committed source orders with a
shared canonical order key and one rejected conflict order. The target static
branch spends one verifier call on the non-canonical conflict order and fails;
the commutative target spends the same one verifier call on the canonical order
and commits. The new `trwm.branch_commutativity_certificate.v1` artifact binds
canonical order key, conflict order key, source AB commit, source BA commit,
source conflict reject, static target reject, commutative target commit,
branch-selection certificates, and same-budget comparison. The substrate
implication is that branch memory needs receipt-bound partial-order
certificates before independent target orders can be canonicalized or
non-canonical orders can be demoted.

The branch-switch transfer example adds switchpoint admission evidence for
source branch reuse. Each domain records a source pre-switch commit, a stale
post-switch source reject, and a switched post-switch source commit. The target
static stale branch spends one verifier call and fails; the switched target
branch spends the same one verifier call and commits. The new
`trwm.branch_switch_certificate.v1` artifact binds the switch parameter, stale
and switched branch ids, source pre-switch receipt, source stale reject, source
switched commit, static stale reject, switched target commit, branch-selection
certificates, and same-budget comparison. The substrate implication is that
branch memory needs receipt-bound switchpoint certificates before stale source
branches can be replaced by switched branches.

The branch-transposition transfer example adds canonical duplicate-state
admission evidence for source branch reuse. Each domain records a rejected
source branch with a canonical state key and a committed non-duplicate source
branch. The target static branch spends one verifier call on a different action
that reaches the same rejected canonical state and fails; the transposition
target spends the same one verifier call on a non-duplicate branch and commits.
The new `trwm.branch_transposition_certificate.v1` artifact binds canonical
state key, source duplicate reject, source alternative commit, static duplicate
target reject, transposition target commit, branch-selection certificates, and
same-budget comparison. The substrate implication is that branch memory needs
receipt-bound canonicalization certificates before duplicate target branches
can be skipped or demoted.

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

The branch-history frontier report now aggregates the forty-six local branch-memory
stages in `trwm.example.branch_history_frontier.v1`. It checks evidence
certificates, primary experiment certificates, and claim certificates for raw
receipt-bound ordering, accepted-loser counterfactual reuse, option-family
abstraction, stateful prerequisite ordering, curriculum sequencing, regime-conditioned contingency
reuse, hindsight goal relabeling, receipt-bound field intervention,
receipt-bound diagnostic probing, residual-template repair, boundary
bracketing, source consensus, contrastive invariant transfer, trust-region radius transfer, analogical
ancestor reuse, certified context selection, counterexample refinement,
conflict-aware query-policy transfer,
drift quarantine, recency-weighted source freshness, restart-anchor backtracking, typed symmetry transfer, pairwise constraint transfer, confidence-bound support, Pareto-front transfer, outlier-filter transfer, provenance-guard transfer, credit-assignment transfer, propensity-match transfer, robustness transfer, confidence calibration, conformal transfer, active-subspace transfer, sensitivity transfer, shield-fallback transfer, potential-heuristic transfer, continuation transfer, commutativity transfer, branch-switch transfer, transposition transfer, receipt-bound branch pruning, diversity-certified family
coverage, receipt-bound budget allocation, no-good stop-rule abstention, branch composition, and retained
memory influence.
This changes the design posture from isolated demos to a staged substrate map:
each branch-history capability must expose its own certificate, and later
stages are only meaningful if earlier evidence still validates.

The boundary remains narrow. This is a deterministic G1 canary inspired by
experience replay, counterfactual regret evidence, and selective tree-search
sampling plus nogood-style pruning, diversity pressure, and recombinable
building-block search plus successive resource allocation and temporal
abstraction plus curriculum learning and continuation methods plus contextual bandits with side information and hindsight
experience replay plus intervention notation as a variable-edit analogy and
experimental-design information as a probe-selection analogy plus case-based
reuse/revise as a residual-template analogy plus safe exploration as a
boundary-bracketing analogy plus query-by-committee as a source-consensus
analogy plus version-space learning as a positive/negative invariant analogy
plus trust-region methods as a proposal-radius analogy
plus discounted/sliding-window non-stationary bandits as a freshness analogy
plus heavy-tailed SAT/CSP search and random restarts as a backtracking analogy
plus group equivariance as a typed symmetry-transform analogy
plus network consistency as a pairwise constraint-propagation analogy
plus Wilson-style proportion intervals as a support-confidence analogy
plus non-dominated sorting as a multi-objective tradeoff analogy
plus RANSAC as a robust-inlier/outlier analogy
plus Byzantine agreement as a faulty-source provenance analogy
plus Shapley value as a marginal-contribution analogy
plus propensity score matching as a covariate-balance analogy
plus robust optimization as an uncertainty-set analogy
plus reliability diagrams and expected calibration error as a confidence-calibration analogy
plus conformal prediction as a nonconformity-envelope analogy
plus active subspaces as a low-rank direction analogy
plus Morris elementary effects and SPSA as one-factor perturbation analogies
plus shielded reinforcement learning and shield synthesis as guard/fallback analogies
plus A* and potential-based reward shaping as search-priority analogies
plus numerical continuation as a path-following analogy
plus partial-order reduction as an independent-transition analogy
plus branch switching and bifurcation points as a switchpoint analogy
plus transposition tables, Zobrist hashing, and duplicate detection as a canonical-state analogy
plus nogood learning and backjumping as a stop-rule analogy;
it is not a
statistical exploration algorithm, regret guarantee, MCTS implementation,
automatic similarity metric, CEGAR system, CDCL solver, novelty-search result,
MAP-Elites implementation, Hyperband implementation, options-framework result,
contextual-bandit result, curriculum-learning result, homotopy-optimization result, Hindsight Experience Replay result, causal-inference result, do-calculus result, Bayesian experimental-design result, active-learning result, query-by-committee result, version-space learning result, safe Bayesian optimization result, group-equivariant neural network, automatic symmetry-search system, CSP solver, arc-consistency algorithm, statistical validation, production calibration, multiobjective optimizer, Pareto-front approximation guarantee, case-based reasoning system, genetic algorithm, program synthesizer, Shapley-value computation, propensity-score estimator, covariate-balance proof, treatment-effect estimate, reinforcement-learning credit-assignment result, robust optimization, worst-case guarantee, distributional robustness, neural-network calibration, statistical calibration, probability estimation, model reliability assurance, conformal prediction, distribution-free coverage, conditional coverage, uncertainty quantification, active-subspace discovery, dimensionality-reduction performance, sensitivity-analysis algorithm, elementary-effects screening result, SPSA gradient estimate, derivative estimate, gradient-estimation guarantee, shield synthesis, runtime assurance, safe reinforcement learning, temporal-logic enforcement, controller switching, A* search, admissible heuristic proof, shortest-path optimality, potential-based reward shaping, policy-invariance proof, reinforcement learning, pattern-database search, optimization result, numerical continuation, homotopy continuation, nonlinear root finding, path-following performance, partial-order reduction algorithm, model-checking correctness proof, dynamic partial-order reduction result, concurrency verification result, state-space reduction guarantee, bifurcation analysis, branch-switching algorithm performance, transposition-table performance, Zobrist-hashing implementation, duplicate-detection algorithm, graph-search scalability, RANSAC implementation, robust estimator, outlier-detection guarantee, Byzantine fault-tolerant protocol, consensus algorithm, security proof, or cross-domain scientific discovery result.

## Receipt-Trained Reversible Proposer Gate

The new receipt-trained reversible proposer benchmark makes the next target
explicit. The proposer learns only from statically valid receipts, stores a
hash-stable snapshot, and ranks candidates by transferable action signatures
rather than held-out task ids. The candidates are reversible delta-token
programs, so each proposal has a checked forward/inverse cycle before it can
support the claim.

Across the local robotics, hardware, program, and quantum canaries:

- training records one rejected proposal and one committed repair per domain,
- the static held-out baseline spends two verifier calls per domain,
- the receipt-trained proposer spends one verifier call per domain,
- both held-out arms commit all four tasks,
- invalid commits remain zero,
- replay, rollback, ledger, evidence, learning, and claim certificates validate.

The practical learning is sharper than the earlier branch-history examples:
the next frontier metric is not just "learned ordering succeeds." It is
"learned ordering preserves success while reducing hard-verifier calls." That
is the right measurement for expensive real-task verifiers.

The next substrate requirements are now concrete:

- external task manifests with fixed train/held-out splits,
- receipt-bound verifier-cost accounting,
- real-domain replay/rollback adapters,
- no learned-verifier commit authority,
- isolated held-out baseline and learned arms that start from the same frozen
  post-training state on separate ledgers,
- benchmark certificates that bind baseline receipts as well as learned
  evaluation receipts,
- aggregate reports that fail if any domain has an invalid commit or loses
  held-out success.

## Real-Task Adapter Readiness

The real-task manifest adds an environment-facing gate before the final proof
can be attempted. It names concrete external adapters for MotionBenchMaker/OMPL,
`riscv-formal`, Defects4J, and MQT Bench/QCEC/RevLib, then probes the local
toolchain, Python modules, task-root directories, and required task assets.
Missing requirements, task-root variables that do not point at existing
directories, or empty/mis-shaped task roots produce a rejected G0 readiness
claim instead of a runtime crash or a softened performance claim.
Each probe now carries an evidence hash. Tools bind their discovered path and
available version output, Python modules bind their origin, task-root variables
bind their resolved directory, and task assets bind deterministic file or
directory fingerprints. This makes task-package or toolchain drift visible in
the preflight report hash before any performance claim can be promoted.

This adds a useful substrate rule: real benchmark evidence starts only after an
adapter-readiness certificate validates. A programmable transactional world
model should distinguish:

- canary evidence that proves local metric mechanics,
- readiness evidence that proves external hard verifiers can run,
- performance evidence that binds real-task receipts and verifier-call
  reductions.

The last category is still open.

## Optional Real Benchmark Adapters

The optional MotionBenchMaker/MoveIt/OMPL, riscv-formal, Defects4J, and MQT
adapters are the first concrete steps from readiness evidence toward real
benchmark receipt streams. They keep the repository dependency-free while
exposing real adapter boundaries. Each adapter now emits
`trwm.real_task_adapter_evidence_certificate.v1`, which binds the adapter
report hash, backend identity, task splits, claim certificate hash, learning
certificate hash, ledger head, and exact training/baseline/learned receipt
partitions plus any backend execution error. It also binds whether held-out
baseline and learned arms were isolated from the same frozen post-training
state, plus typed-candidate hashes, hard-result hashes, and hard-metadata
hashes for every receipt, which turns command output summaries, QCEC
equivalence metadata, and test-verifier metadata into compact certificate
lanes. It now also binds receipt artifact hashes for every receipt and
normalized backend execution evidence hashes for every receipt, so a supported
real-backend claim must expose both the task/candidate inputs and the expected
domain-specific execution shape rather than only a raw metadata hash. Missing
real backends can still produce a valid G0 zero-receipt evidence certificate;
only real-backend supported claims can produce G1 adapter evidence. The
single-domain claim grade now uses the same full objective predicate across all
four adapters: real backend, runtime hashes, receipt artifacts, backend
execution evidence, valid learning support, verifier-call reduction, held-out
success preservation, zero invalid commits, hard-commit-only receipts,
train/evaluation disjointness, held-out arm isolation, and replay, rollback,
and ledger audits must all pass before a child claim can be labeled G1.
The aggregate suite now additionally binds each adapter evidence certificate to
the domain's `trwm.real_task_benchmark_manifest.v1` spec hash and source URL
envelope, so an otherwise valid adapter report cannot satisfy a different
benchmark manifest.

For robotics:

- MotionBenchMaker/MoveIt/OMPL task assets provide train and held-out motion
  planning candidates,
- `roslaunch` owns execution of the configured benchmark command,
- result JSON owns the hard decision by binding solved/correct status,
  approximate-solution rejection, and explicit nonnegative clearance,
- missing `roslaunch` or `TRWM_MOTION_BENCHMARK_TASK_ROOT` produces a rejected
  claim with zero receipts,
- deterministic test doubles can validate transaction mechanics but not
  robotics safety or planner performance,
- the current candidate surface compares unsafe and safe motion candidates, so
  it is adapter evidence rather than a motion-planning optimality or robot
  safety proof.

For hardware:

- riscv-formal provides RVFI instruction/check-family tasks,
- generated SymbiYosys checks own the hard decision,
- missing `sby`, `yosys`, `make`, `python3`, or
  `TRWM_RISCV_FORMAL_TASK_ROOT` produces a rejected claim with zero receipts,
- deterministic test doubles can validate transaction mechanics but not
  hardware-verification performance,
- the current candidate surface compares RVFI-violating and RVFI-compliant
  task directories, so it is adapter evidence rather than a RISC-V core
  correctness proof.

For quantum:

- MQT Bench provides train and held-out circuit tasks,
- MQT QCEC owns the hard equivalence decision,
- missing `mqt.bench` or `mqt.qcec` produces a rejected claim with zero
  receipts,
- backend task-generation or QCEC execution errors now produce a rejected claim
  with zero receipts and a certificate-bound `backend_error`, not a suite crash,
- deterministic test doubles can validate transaction mechanics but not
  quantum benchmark performance,
- the real backend must preserve held-out success, reduce QCEC calls, validate
  the learning certificate, pass replay/rollback audit, and keep invalid
  commits at zero before a single-domain quantum claim can be supported.

For program repair:

- Defects4J provides real bug ids and version checkouts,
- Defects4J `compile` plus relevant-test execution owns the hard decision,
- missing `defects4j`, `java`, `git`, `svn`, or `perl` produces a rejected
  claim with zero receipts,
- deterministic test doubles can validate transaction mechanics but not
  program-repair performance,
- the current candidate surface compares buggy-version and fixed-version
  candidates, so it is adapter evidence rather than an APR patch-generation
  result.

This changes the substrate requirement from "name the external verifier" to
"ship an adapter that can fail closed until the verifier is available." All
four goal-domain adapter shapes now exist. The remaining work is real
task-root/toolchain execution, broader hardware suites, deeper Defects4J
patch-candidate receipts, independent audit verifiers, and aggregate
four-domain receipts before the proof is attempted.

The real-task benchmark suite adds the aggregate promotion gate for the active
objective. It composes the robotics, hardware, program, and quantum adapter
reports into one `trwm.real_task_benchmark_suite_report.v1` report plus a
`trwm.real_task_benchmark_suite_certificate.v1` certificate. The suite binds
the readiness manifest, preflight report hash, manifest spec hashes, child
adapter report hashes, adapter evidence certificate hashes, child claim hashes,
learning certificate hashes, receipt hashes, training/baseline/learned receipt
partition hashes, typed-candidate hashes, hard-result hashes,
hard-metadata hashes, manifest split task hashes, manifest and adapter
train/held-out task ids, receipt artifact hashes, receipt artifact value
hashes, manifest runtime requirement evidence hashes, adapter runtime
requirement evidence hashes, manifest task-asset content hashes,
missing requirements, backend errors, backend execution evidence hashes,
verifier-call totals, held-out success totals, replay/rollback/ledger status,
and invalid-commit totals. It also binds the aggregate `heldout_arms_isolated`
gate, which requires every child baseline and learned evaluation arm to start
from the same frozen post-training state on separate ledgers. It also
cross-checks that each adapter evidence
certificate and child claim
certificate matches the report it accompanies, that adapter evidence is covered
by the manifest spec sources for that domain, and that each learning
certificate matches the report's learner snapshot, verifier-call metrics,
success metrics, hard-commit flag, ledger audit, and exact
training/baseline/learned receipt partitions.

That changes the proof boundary again: single-domain adapter success is no
longer enough. The final claim is supported only if all four real backends are
available, all child claims are supported, all learning certificates support
call reduction, every adapter evidence certificate is report-consistent and
manifest-covered, every child claim and learning certificate is
report-consistent, the suite certificate directly binds aggregate
backend-availability and learning-support gates, every held-out arm comparison is isolated, every domain
reduces hard-verifier calls while preserving held-out success, all receipt and
execution-provenance counts bind exact hash lanes, all receipt artifact lanes
bind exact receipt counts, aggregate training/baseline/learned receipt
partition lanes bind the flat receipt lane, adapter train/held-out task ids exactly match the
manifest split task ids, adapter runtime requirement evidence hashes match the
manifest preflight requirement hashes, receipt artifact value hashes cover every
preflighted manifest task-asset content hash, all backend execution evidence
lanes bind exact receipt counts, and invalid commits remain zero. On
the current local machine the suite correctly rejects with G0 because the
external toolchains and task roots are missing.

`examples.real_task_evidence_bundle` turns that gate into a portable proof
artifact for external runs. It emits the full child adapter results plus the
aggregate suite result, then certifies that the bundle's child report hashes,
adapter evidence certificate hashes, child claim hashes, learning certificate
hashes, receipt counts, missing requirements, failed aggregate gates, and
zero-invalid-commit count match the rebuilt suite. That changes the next
execution requirement from "run several modules and compare their outputs by
hand" to "produce one bundle whose certificate can be validated against all
included child evidence." On this machine it is still a valid G0 bundle with
zero receipts; on a provisioned machine it is the artifact that must carry the
real robotics, hardware, program, and quantum receipt streams.

`examples.real_task_execution_plan` now fills the pre-run side of that path.
It derives a certificate-bound run contract from the manifest and current
preflight, binding every adapter module/command, required tool, Python module,
task-root environment variable, task asset, train/held-out split, preflight
probe hash, runtime requirement hash, task-asset content hash, aggregate suite
command, and evidence-bundle command. That makes the remaining external work
concrete: a provisioned runner must first make this plan ready, then produce a
validated evidence bundle from the same manifest-bound commands.

The real-task adapters and aggregate suite now also bind the learned proposer
path itself. Each receipt-bearing adapter report includes a valid
receipt-trained reversible proposer snapshot, the snapshot's training receipt
hashes and row hashes, and one proposer-rank audit hash per held-out task. The
audit proves the learned arm submitted the prefix of the candidate order ranked
from the training snapshot. The suite lifts these into
`all_learner_snapshots_bound` and `all_proposer_rank_audits_bound`, so a
real-task G1 promotion now requires not only fewer verifier calls and zero
invalid commits, but also a certificate-bound explanation of why the learned
arm made fewer calls.

The evidence bundle now carries those same lanes as portable proof material:
child learner snapshot hashes, snapshot receipt hashes, snapshot row hashes,
child proposer-rank audit hashes, `all_learner_snapshots_bound`, and
`all_proposer_rank_audits_bound`. That closes the handoff gap where the suite
could validate the learned proposer path but the final bundle did not expose
the compact hashes needed for downstream review.

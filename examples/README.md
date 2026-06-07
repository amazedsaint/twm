# Examples

These examples are executable experiments that compose the TRWM substrate
directly. They are not separate simulations or mock demos. Each one uses the
transaction engine, hard verifier, receipt ledger, replay audit, and rollback
audit to show where a proposer may help and where the transaction layer must
retain authority.

Run them from the repository root:

```sh
python3 -m examples.robotic_safety_envelope
python3 -m examples.molecular_dynamics_verlet
python3 -m examples.material_lattice_metropolis
python3 -m examples.ancestral_branch_exploration
python3 -m examples.branch_counterfactual_transfer
python3 -m examples.branch_abstraction_transfer
python3 -m examples.branch_prerequisite_transfer
python3 -m examples.branch_curriculum_transfer
python3 -m examples.branch_contingency_transfer
python3 -m examples.branch_hindsight_relabel_transfer
python3 -m examples.branch_intervention_transfer
python3 -m examples.branch_diagnostic_probe_transfer
python3 -m examples.branch_residual_template_transfer
python3 -m examples.branch_boundary_bracket_transfer
python3 -m examples.branch_consensus_transfer
python3 -m examples.branch_invariant_transfer
python3 -m examples.branch_trust_region_transfer
python3 -m examples.analogical_branch_transfer
python3 -m examples.context_selection_transfer
python3 -m examples.context_refinement_transfer
python3 -m examples.context_query_policy_transfer
python3 -m examples.context_drift_quarantine
python3 -m examples.branch_recency_weight_transfer
python3 -m examples.branch_restart_transfer
python3 -m examples.branch_symmetry_transfer
python3 -m examples.branch_constraint_transfer
python3 -m examples.branch_confidence_transfer
python3 -m examples.branch_pareto_transfer
python3 -m examples.branch_outlier_filter_transfer
python3 -m examples.branch_provenance_guard_transfer
python3 -m examples.branch_credit_assignment_transfer
python3 -m examples.branch_propensity_match_transfer
python3 -m examples.branch_robustness_transfer
python3 -m examples.branch_calibration_transfer
python3 -m examples.branch_conformal_transfer
python3 -m examples.branch_active_subspace_transfer
python3 -m examples.branch_sensitivity_transfer
python3 -m examples.branch_shield_fallback_transfer
python3 -m examples.branch_potential_heuristic_transfer
python3 -m examples.branch_continuation_transfer
python3 -m examples.branch_commutativity_transfer
python3 -m examples.branch_switch_transfer
python3 -m examples.branch_transposition_transfer
python3 -m examples.branch_pruning_transfer
python3 -m examples.branch_diversity_transfer
python3 -m examples.branch_budget_transfer
python3 -m examples.branch_stop_rule_transfer
python3 -m examples.branch_composition_transfer
python3 -m examples.context_retention_transfer
python3 -m examples.receipt_trained_reversible_proposer_benchmark
python3 -m examples.real_task_benchmark_manifest
python3 -m examples.robotics_motion_benchmark_adapter
python3 -m examples.hardware_riscv_formal_adapter
python3 -m examples.program_defects4j_adapter
python3 -m examples.quantum_mqt_bench_adapter
python3 -m examples.real_task_benchmark_suite
python3 -m examples.branch_history_frontier
python3 -m examples.programmable_world_model_frontier
```

Each command emits JSON. The three domain commands now include top-level
`report`, `evidence_certificate`, and `claim_certificate` objects. The
ancestral branch command adds an `exploration_certificate` that binds past
branch receipts to later budgeted proposal ordering. The branch-counterfactual
command adds
`trwm.branch_counterfactual_certificate.v1` artifacts showing that
accepted-but-rolled-back branch losers can become proposal evidence when the
old winner is stale in a target context. The branch-abstraction command adds
`trwm.branch_abstraction_certificate.v1` artifacts showing that an abstract
option family can guide a target-specific same-family action when exact
source-action replay is stale. The branch-prerequisite command adds
`trwm.branch_prerequisite_certificate.v1` artifacts showing that past branches
can certify prerequisite-before-final ordering under a matched two-call budget.
The branch-curriculum command adds `trwm.branch_curriculum_certificate.v1`
artifacts showing that past branch receipts can certify a monotone easy-to-hard
target sequence before final verification under a matched three-call budget.
The branch-contingency command adds
`trwm.branch_contingency_certificate.v1` artifacts showing that a target
context can select the source branch with the matching regime tag when stale
unconditional reuse fails under the same one-call budget.
The branch-hindsight-relabel command adds
`trwm.branch_hindsight_relabel_certificate.v1` artifacts showing that rejected
source branches can suggest an achieved target goal, but the relabeled target
branch commits only after fresh hard verification.
The branch-intervention command adds
`trwm.branch_intervention_certificate.v1` artifacts showing that a source
reject/commit pair can identify a typed verifier-field edit for a target
candidate, but the intervened target branch commits only after fresh hard
verification.
The branch-diagnostic-probe command adds
`trwm.branch_diagnostic_probe_certificate.v1` artifacts showing that source
probe receipts can identify which target diagnostic to run before final-action
verification under a matched verifier-call budget.
The branch-residual-template command adds
`trwm.branch_residual_template_certificate.v1` artifacts showing that a source
reject plus committed repair can identify a named repair template, while the
target repair still commits only after fresh hard verification.
The branch-boundary-bracket command adds
`trwm.branch_boundary_bracket_certificate.v1` artifacts showing that source
reject/commit endpoints can prioritize a target boundary candidate, while the
target candidate still commits only after fresh hard verification.
The branch-consensus command adds `trwm.branch_consensus_certificate.v1`
artifacts showing that two source branches can outvote a singleton source
family before target proposal ranking, while the target candidate still commits
only after fresh hard verification.
The branch-invariant command adds `trwm.branch_invariant_certificate.v1`
artifacts showing that positive and negative source branch receipts can define
a contrastive target proposal signature, while the target candidate still
commits only after fresh hard verification.
The branch-trust-region command adds
`trwm.branch_trust_region_certificate.v1` artifacts showing that a source
reject/commit radius can cap target proposal size, while the bounded target
candidate still commits only after fresh hard verification.
The analogical branch
command adds an `analogical_certificate` that binds explicit ancestor-context
reuse and misleading-ancestor rejection. The context-selection command adds
descriptor-level `trwm.ancestral_context_selection_certificate.v1` artifacts
before branch-memory reuse. The context-refinement command adds
`trwm.ancestral_context_refinement_certificate.v1` artifacts that bind a failed
coarse retrieval to a stricter refined retrieval. The context-query-policy
command adds `trwm.context_query_policy_certificate.v1` artifacts showing that
the refined retrieval policy improves held-out sibling exploration against a
stale-query baseline under the same one-call verifier budget, plus
`trwm.context_branch_conflict_certificate.v1` artifacts that bind the committed
but misleading source evidence the refined policy overrides. The context-drift
command adds `trwm.context_drift_quarantine_certificate.v1` artifacts that bind
old-epoch branch evidence quarantine before target reuse. The
branch-recency command adds `trwm.branch_recency_certificate.v1` artifacts that
bind old stale commits, recent stale rejects, recent adapted commits, and the
same one-call target budget before freshness overrides cumulative history. The
branch-restart command adds `trwm.branch_restart_certificate.v1` artifacts that
bind source local dead-end rejects, restart-anchor commits, static target
rejects, and same-budget restart target commits before abandoning local
continuation. The branch-symmetry command adds
`trwm.branch_symmetry_certificate.v1` artifacts that bind a typed symmetry
transform, source commit, failed exact target replay, and same-budget
symmetry-mapped target commit. The branch-constraint command adds
`trwm.branch_constraint_certificate.v1` artifacts that bind an incompatible
pair, compatible pair, source reject/commit receipts, failed static target
pair, and same-budget constraint-guided target commit. The branch-confidence
command adds `trwm.branch_confidence_certificate.v1` artifacts that bind thin
optimistic support, stronger source support, Wilson-style lower bounds, failed
static target replay, and same-budget confidence-guided target commit. The
branch-pareto command adds `trwm.branch_pareto_certificate.v1` artifacts that
bind dominated and nondominated objective vectors, source reject/commit
receipts, failed scalar target replay, and same-budget Pareto-guided target
commit. The
branch-outlier-filter command adds
`trwm.branch_outlier_filter_certificate.v1` artifacts that bind source inlier
feature values, anomalous source-valid outlier receipts, failed outlier target
replay, and same-budget inlier-filtered target commit. The
branch-provenance-guard command adds
`trwm.branch_provenance_guard_certificate.v1` artifacts that bind trusted
source ids, a quarantined source-valid branch, failed quarantined-source target
replay, and same-budget provenance-guarded target commit. The
branch-credit-assignment command adds
`trwm.branch_credit_assignment_certificate.v1` artifacts that bind marginal
credit values, one credited source fragment, source-valid distractors, failed
low-credit target replay, and same-budget credit-guided target commit. The
branch-propensity-match command adds
`trwm.branch_propensity_match_certificate.v1` artifacts that bind target and
source covariates, scalar propensity-style scores, caliper distance,
covariate-balance distance, failed mismatched target replay, and same-budget
matched target commit. The
branch-robustness command adds
`trwm.branch_robustness_certificate.v1` artifacts that bind uncertainty-set
variant ids, brittle source receipts, robust source variant receipts,
positive source margins, failed brittle target replay, and same-budget robust
target commit. The
branch-calibration command adds
`trwm.branch_calibration_certificate.v1` artifacts that bind confidence-bin
ids, predicted confidence values, empirical accept rates, calibration gaps,
overconfident source rejects, calibrated source receipts, failed
overconfident target replay, and same-budget calibrated target commit. The
branch-conformal command adds
`trwm.branch_conformal_certificate.v1` artifacts that bind source calibration
receipts, nonconformity scores, alpha, quantile rank, out-of-envelope source
reject, failed out-of-envelope target replay, and same-budget in-envelope
target commit. The
branch-active-subspace command adds
`trwm.branch_active_subspace_certificate.v1` artifacts that bind active and
orthogonal basis vectors, projection threshold, source active-direction
commits, source orthogonal reject, failed orthogonal target replay, and
same-budget active-direction target commit. The
branch-sensitivity command adds
`trwm.branch_sensitivity_certificate.v1` artifacts that bind one-factor
negative and positive perturbation receipts, failed wrong-direction target
replay, and same-budget sensitivity-guided target commit. The
branch-shield-fallback command adds
`trwm.branch_shield_fallback_certificate.v1` artifacts that bind unsafe-family
source rejects, fallback-family source commits, failed unsafe target replay,
and same-budget shield-fallback target commit. The
branch-potential-heuristic command adds
`trwm.branch_potential_heuristic_certificate.v1` artifacts that bind
high-potential source rejects, low-potential source commits, failed
high-potential target replay, and same-budget low-potential target commit. The
branch-continuation command adds
`trwm.branch_continuation_certificate.v1` artifacts that bind lambda schedules,
max path step, source continuation commits, source direct-jump reject, failed
same-budget direct target jumps, and verified continuation target commits. The
branch-commutativity command adds `trwm.branch_commutativity_certificate.v1`
artifacts that bind two source orders with a shared canonical key, a rejected
conflict order, a failed static target order, and a same-budget canonical
target commit. The
branch-switch command adds `trwm.branch_switch_certificate.v1` artifacts that
bind switch parameter, stale and switched branch ids, source pre-switch
commit, source stale reject, source switched commit, failed stale target branch,
and same-budget switched target commit. The
branch-transposition command adds `trwm.branch_transposition_certificate.v1`
artifacts that bind canonical state keys, duplicate source rejects,
non-duplicate source commits, failed duplicate target branches, and
same-budget non-duplicate target commits. The
branch-pruning command adds `trwm.branch_pruning_certificate.v1` artifacts
showing that rejected source branch receipts can prune known-dead target
candidates before scarce verifier budget is spent. The
branch-diversity command adds `trwm.branch_diversity_certificate.v1` artifacts
showing that same-family rejects can force coverage of distinct candidate
families under the same verifier budget. The
branch-budget command adds `trwm.branch_budget_certificate.v1` artifacts
showing that past receipt costs can allocate a fixed verifier budget toward a
higher-cost repair after a cheap reject probe. The
branch-stop-rule command adds `trwm.branch_stop_rule_certificate.v1` artifacts
showing that negative source receipts can record target abstentions and avoid
verifier calls on a matched no-good family. The
branch-composition command adds `trwm.branch_composition_certificate.v1`
artifacts showing that two receipt-bound source fragments can be combined into
a target proposal only after static and single-fragment branches fail under the
same budget. The context-retention command adds
`trwm.ancestral_branch_retention_certificate.v1`
artifacts that bind committed target branches into a hash-checked future-memory
update, plus
`trwm.ancestral_branch_influence_certificate.v1` artifacts that bind the later
sibling proposal order to the exact memory snapshot and retained context. The
context-retention report also emits
`trwm.context_retention_influence_ablation_certificate.v1` artifacts comparing
the static sibling baseline with the influence-ranked sibling branch under the
same one-call verifier budget. The branch-history frontier command aggregates
the forty-six branch-memory stages into one bounded G1 report. The physical
frontier command aggregates the three physical certified examples into a
cross-domain report and bounded G1 claim certificate.

## Experiments

### Robotic Safety Envelope

`examples.robotic_safety_envelope` runs a 2D point-robot trajectory gate. A
short-path proposal collides with the obstacle and is rejected despite a high
soft score. The residual repair proposes a detour that commits only after the
signed-distance clearance and max-step checks pass.

Learning: the proposer can optimize for path length, but signed-distance
barriers and step bounds should remain transactional hard gates.

### Molecular Dynamics Verlet

`examples.molecular_dynamics_verlet` runs a two-particle Lennard-Jones step. A
forward-Euler proposal is rejected because it does not match the verified
velocity-Verlet update. The residual carries the repaired state, which commits
only after integrator, contact, energy-drift, momentum-drift, replay, and
rollback checks pass.

Learning: a cheap dynamics proposer can explore, but the transaction should bind
the integrator identity and physical invariants before committing state.

### Material Lattice Metropolis

`examples.material_lattice_metropolis` runs a periodic 2D Ising spin-lattice
step. A high-energy spin flip is rejected by the Metropolis acceptance rule. The
residual proposes an energy-lowering flip, and the committed energy change
matches the exact Ising delta.

Learning: material-science proposal systems need receipts that bind the
Hamiltonian, delta-energy arithmetic, acceptance randomness, and replayable
configuration update.

### Ancestral Branch Exploration

`examples.ancestral_branch_exploration` runs three toy domains: robot replanning,
molecule repair, and material-process selection. Each domain first records past
branches with one hard reject, one accepted-but-rolled-back loser, and one
committed winner. A budget-one static exploration pass tries the old first
proposal and fails in all three domains; the past-branch-guided pass replays the
receipt evidence, ranks the committed branch first, and commits in all three
domains after hard verification.

Learning: branches of the past can improve exploration by changing which
candidate gets scarce verifier budget first. They do not become authority: the
candidate still has to pass the domain hard gate, branch-selection certificate,
ledger audit, replay audit, and rollback audit.

### Branch Counterfactual Transfer

`examples.branch_counterfactual_transfer` tests accepted-but-rolled-back
branch losers. Each domain records a source branch with one hard reject, one
committed winner, and one accepted loser that is rolled back because it was not
selected. The target then makes the old winner stale: the one-call stale-winner
baseline fails, while the one-call counterfactual branch commits the previously
rolled-back accepted action after hard verification.

Learning: counterfactual branch evidence should be reusable only through its
own certificate. `trwm.branch_counterfactual_certificate.v1` binds source
winner receipts, rolled-back accepted loser receipts, stale target rejects,
counterfactual target commits, branch-selection certificates, and the
same-budget comparison before claiming that counterfactual reuse improved
exploration.

### Branch Abstraction Transfer

`examples.branch_abstraction_transfer` tests abstract branch-family reuse. Each
domain records a source branch where a concrete action commits inside an
abstract option family. The target makes that exact source action stale, so
exact one-call replay fails. A different target-specific action in the same
abstract family then commits under the same one-call budget after hard
verification.

Learning: branches of the past sometimes transfer as certified abstractions,
not exact action replays. `trwm.branch_abstraction_certificate.v1` binds the
source family, source commit receipts, stale exact target rejects,
same-family target commits, branch-selection certificates, and same-budget
comparison before claiming abstraction-level exploration lift.

### Branch Prerequisite Transfer

`examples.branch_prerequisite_transfer` tests stateful prerequisite ordering.
Each domain records source receipts where a prerequisite action commits before
the final action. The target static branch spends two verifier calls on the
final action and a distractor without first satisfying the target prerequisite,
so it commits nothing. The guided target spends the same two calls on the
target prerequisite and then the final action; both commit through the hard
verifier and replay/rollback audit.

Learning: past branches can improve exploration by certifying order, not only
which candidate to try. `trwm.branch_prerequisite_certificate.v1` binds source
prerequisite/final receipts, static target rejects, guided prerequisite/final
commits, branch-selection certificates, and the same-budget comparison before
claiming prerequisite-order lift.

### Branch Curriculum Transfer

`examples.branch_curriculum_transfer` tests easy-to-hard continuation. Each
domain records a source sequence with two curriculum steps and one final
commit. The static target spends the same three verifier calls on direct final,
skipped-level, and bad early-level candidates and commits nothing. The guided
target spends those three calls on level 1, level 2, and final target actions;
all three commit only after fresh hard verification and replay/rollback audit.

Learning: branches of the past can improve exploration by certifying a
curriculum sequence, not only a single prerequisite. `trwm.branch_curriculum_certificate.v1`
binds source curriculum receipts, static target rejects, guided curriculum
commits, guided final commits, branch-selection certificates, and the matched
three-call budget before claiming curriculum-guided exploration lift.

### Branch Contingency Transfer

`examples.branch_contingency_transfer` tests regime-conditioned branch reuse.
Each domain records one source branch for a stale/default regime and one source
branch for the target regime. The target static pass spends one verifier call
on the stale-regime action and fails. The contingent pass spends the same one
verifier call on the matching-regime branch and commits after hard
verification.

Learning: useful branch history may depend on a context feature, not only on an
action score. `trwm.branch_contingency_certificate.v1` binds stale and matched
source receipts, static target rejects, contingent target commits,
branch-selection certificates, the selected source context, the rejected source
context, and the same-budget comparison before claiming that regime-conditioned
reuse improved exploration.

### Branch Hindsight Relabel Transfer

`examples.branch_hindsight_relabel_transfer` tests goal relabeling from a
rejected branch. Each domain records a source branch that is physically valid
but misses its intended goal while exposing a different achieved goal. The
target static pass spends one verifier call on a bad direct proposal and fails.
The hindsight-relabeled pass spends the same one verifier call on the achieved
goal branch and commits only after the target hard verifier accepts it.

Learning: rejected receipts can improve exploration without becoming authority.
`trwm.branch_hindsight_relabel_certificate.v1` binds the source reject receipt,
intended goal, achieved/relabeled goal, static target reject, relabeled target
commit, branch-selection certificates, and same-budget comparison before
claiming that hindsight relabeling improved exploration.

### Branch Intervention Transfer

`examples.branch_intervention_transfer` tests receipt-bound field intervention.
Each domain records a source branch with one hard reject and one committed
repair that differs in a single verifier field: robot clearance, molecular
strain, or material thermal gradient. The target static pass spends one
verifier call on the unedited target candidate and fails. The intervention pass
spends the same one verifier call on the field-edited target candidate and
commits only after fresh hard verification.

Learning: branches of the past can suggest which typed field to edit, but that
edit is proposal evidence rather than a causal claim or commit authority.
`trwm.branch_intervention_certificate.v1` binds the source reject/commit
receipts, source and target before/after field values, static target reject,
intervened target commit, branch-selection certificates, and same-budget
comparison before claiming intervention-guided exploration lift.

### Branch Diagnostic Probe Transfer

`examples.branch_diagnostic_probe_transfer` tests active diagnostic probing.
Each domain records a source branch where a cheap prior probe is rejected and a
diagnostic probe commits an observation: robot corridor regime, molecular site
regime, or material thermal regime. The target static pass spends the same two
verifier calls on unprobed final actions and fails. The guided pass spends one
call on the diagnostic probe and one on the now-observation-bound final action;
both commit only after fresh hard verification.

Learning: branches of the past can improve exploration by selecting what to
measure before acting. `trwm.branch_diagnostic_probe_certificate.v1` binds the
source probe reject/commit receipts, static unprobed target rejects, guided
probe commit, guided final commit, branch-selection certificates, and matched
two-call budget before claiming probe-guided exploration lift.

### Branch Residual Template Transfer

`examples.branch_residual_template_transfer` tests residual-to-repair-template
reuse. Each domain records a source branch with one rejected proposal and one
committed repair: a robot detour, molecular valence relaxation, or tempered
material phase repair. The target static pass spends one verifier call on the
bad target proposal and fails. The template-guided pass spends the same one
verifier call on the target action produced from the named repair template and
commits only after fresh hard verification.

Learning: residual repair templates can improve exploration only as certified
proposal evidence. `trwm.branch_residual_template_certificate.v1` binds the
source reject/repair receipts, static target reject, templated target commit,
template fields, branch-selection certificates, and matched one-call budget
before claiming template-guided exploration lift.

### Branch Boundary Bracket Transfer

`examples.branch_boundary_bracket_transfer` tests receipt-bound boundary
bracketing. Each domain records a source branch with one unsafe endpoint and
one safe endpoint: robot clearance/turn-rate, molecular strain, or material
thermal/purity bounds. The target static pass spends one verifier call on the
unsafe target endpoint and fails. The bracket-guided pass spends the same one
verifier call on a target candidate near the hard-gate boundary and commits
only after fresh hard verification.

Learning: boundary brackets can make exploration more sample-efficient only as
proposal-order evidence. `trwm.branch_boundary_bracket_certificate.v1` binds
the source reject/safe receipts, static target reject, bracketed target commit,
bracket fields, branch-selection certificates, and matched one-call budget
before claiming boundary-guided exploration lift.

### Branch Consensus Transfer

`examples.branch_consensus_transfer` tests multi-source agreement over past
branch families. Each domain records two source branches supporting a safe
proposal family and one singleton source branch supporting a tempting family.
The target static pass spends one verifier call on the singleton-family target
proposal and fails. The consensus-guided pass spends the same one verifier call
on the majority-family target proposal and commits only after fresh hard
verification.

Learning: source agreement can make branch reuse less brittle, but it is still
proposal-order evidence. `trwm.branch_consensus_certificate.v1` binds the
majority source receipts, singleton source receipt, static target reject,
consensus target commit, branch-selection certificates, support counts, and
matched one-call budget before claiming consensus-guided exploration lift.

### Branch Invariant Transfer

`examples.branch_invariant_transfer` tests contrastive invariant transfer. Each
domain records two positive source branches that commit and two negative source
branches that reject on distinct hard-gate violations. The target static pass
spends one verifier call on a tempting proposal that violates the learned
contrast. The invariant-guided pass spends the same one verifier call on a
candidate matching the positive/negative signature and commits only after fresh
hard verification.

Learning: contrastive invariants can rank target proposals, but they are still
proposal filters. `trwm.branch_invariant_certificate.v1` binds the positive
source receipts, negative source receipts, invariant field keys, static target
reject, invariant target commit, branch-selection certificates, and matched
one-call budget before claiming invariant-guided exploration lift.

### Branch Trust-Region Transfer

`examples.branch_trust_region_transfer` tests receipt-bound proposal-radius
control. Each domain records one source branch outside a radius cap that
rejects and one bounded source branch that commits. The target static pass
spends one verifier call on an oversized proposal and fails. The trust-region
pass spends the same one verifier call on a bounded target proposal and commits
only after fresh hard verification.

Learning: branches of the past can improve exploration by sizing target
proposal steps before verification, not only by ranking whole actions.
`trwm.branch_trust_region_certificate.v1` binds source reject/commit receipts,
source and target proposal radii, the trusted radius cap, static target reject,
trust-region target commit, branch-selection certificates, and matched
one-call budget before claiming trust-region-guided exploration lift.

### Analogical Branch Transfer

`examples.analogical_branch_transfer` runs the same three toy domains with two
positive ancestor contexts and one misleading ancestor context per domain. The
static target pass spends its only verifier call on the old first proposal and
fails. The explicit ancestor-context pass ranks the previously committed action
first and commits. The misleading-context pass ranks a context-local winner that
is unsafe in the target context; the target hard verifier rejects it.

Learning: branch history can transfer across explicitly named related contexts,
but context choice is itself a future verifier surface. Misleading ancestors are
allowed to propose; they are not allowed to commit.

### Context Selection Transfer

`examples.context_selection_transfer` adds certified ancestor selection. Each
domain publishes context descriptors for the target, two compatible ancestors,
and one misleading ancestor. The selection certificate admits the compatible
contexts and rejects the misleading one because its required `regime` tag does
not match. The selected ancestors improve target budget-one exploration; a
bypass pass using the rejected context is still blocked by the target hard
verifier.

Learning: "find branches of the past" needs a certified retrieval surface. A
branch-memory snapshot is not enough; the target also needs an auditable reason
why those ancestor contexts are admissible for reuse.

### Context Refinement Transfer

`examples.context_refinement_transfer` starts from a coarse selector that does
not require the discriminating `regime` tag. The coarse selector admits two
misleading ancestors, ranks their unsafe action first, and the target hard
verifier rejects that branch. The rejected receipt becomes a counterexample for
a refinement certificate. Adding `regime` narrows the selected ancestors and
the next budget-one target pass commits.

Learning: failed branches of the past should not only train proposal order; they
should also refine the retrieval policy that decides which past branches are
allowed to influence exploration.

### Context Query Policy Transfer

`examples.context_query_policy_transfer` keeps the refinement setup but splits
it into a calibration target and two held-out sibling targets. The calibration
target records the coarse-query counterexample and emits the refinement
certificate. Each sibling target then compares the stale coarse query with the
refined query policy under the same one-call verifier budget. The stale sibling
queries fail in all six held-out transfers; the refined query policy commits in
all six.

Learning: a failed branch can improve the exploration policy itself only when
the policy update is explicit and replayable. The new
`trwm.context_query_policy_certificate.v1` binds the counterexample receipt,
base and refined selection certificates, each held-out sibling selection, top
actions, receipt hashes, and same-budget comparison before promoting the claim.
The companion `trwm.context_branch_conflict_certificate.v1` binds the conflict:
source receipts committed the stale unsafe action, the calibration and sibling
targets rejected it, and the refined policy committed the target action at the
same budget.

### Context Drift Quarantine

`examples.context_drift_quarantine` tests stale branch memory. Each domain first
records an old-epoch source branch where an action committed, then applies that
stale memory to a current target and fails under one verifier call. After a
current-epoch source branch is recorded, an epoch-aware selection certificate
quarantines the old context and the target commits under the same one-call
budget.

Learning: past branches need validity scope. A committed receipt is useful
evidence only when its context tags still match the target; otherwise the
transactional world model needs a quarantine certificate before memory can
influence exploration.

### Branch Recency Weight Transfer

`examples.branch_recency_weight_transfer` tests receipt freshness. Each domain
records two old source commits for a now-stale action, then a recent source
branch where that stale action is rejected and an adapted action commits. The
cumulative-history target spends one verifier call on the stale action and
fails. The recency-window target spends the same one verifier call on the
adapted action and commits only after fresh hard verification.

Learning: branches of the past need freshness policy, not only validity scope.
`trwm.branch_recency_certificate.v1` binds the old stale commit receipts,
recent stale reject receipt, recent adapted commit receipt, static target
reject, recency target commit, branch-selection certificates, and same-budget
comparison before claiming recency-guided exploration lift.

### Branch Restart Transfer

`examples.branch_restart_transfer` tests restart-anchor evidence. Each domain
records a source branch where a local continuation is rejected and a restart
anchor commits. The static target spends one verifier call on the matching
local continuation and fails. The restart-guided target spends the same one
verifier call on the restart anchor and commits only after fresh hard
verification.

Learning: branches of the past can improve exploration by choosing where to
restart, not just which local candidate to rank first.
`trwm.branch_restart_certificate.v1` binds the source local-dead-end reject,
source restart-anchor commit, static target reject, restart target commit,
branch-selection certificates, and same-budget comparison before claiming
restart-guided exploration lift.

### Branch Symmetry Transfer

`examples.branch_symmetry_transfer` tests typed transform evidence. Each domain
records a source branch where one side of a mirrored or reflected structure
commits. Exact replay of the same source action in the target spends one
verifier call and fails. The symmetry-guided target spends the same one
verifier call on the transformed action and commits only after fresh hard
verification.

Learning: branches of the past can improve exploration by carrying a typed
transform, not just a reusable action token. `trwm.branch_symmetry_certificate.v1`
binds the transform id, source commit, failed exact replay, transformed target
commit, branch-selection certificates, and same-budget comparison before
claiming symmetry-guided exploration lift. Group-equivariant networks are only
the symmetry/equivariance analogy here; this is not a neural-network or
automatic symmetry-search claim: https://arxiv.org/abs/1602.07576

### Branch Constraint Transfer

`examples.branch_constraint_transfer` tests pairwise constraint evidence. Each
domain records a source branch where one pair is rejected and one compatible
pair commits. The static target spends one verifier call replaying the
incompatible pair and fails. The constraint-guided target spends the same one
verifier call on the compatible pair and commits only after fresh hard
verification.

Learning: branches of the past can improve combinatorial exploration by
certifying relations between choices, not only individual action quality.
`trwm.branch_constraint_certificate.v1` binds the incompatible pair, compatible
pair, source reject/commit receipts, target baseline reject, target compatible
commit, branch-selection certificates, and same-budget comparison before
claiming pairwise-constraint-guided exploration lift. Network consistency is
only the constraint-propagation analogy here; this is not a CSP solver or
arc-consistency algorithm: https://doi.org/10.1016/0004-3702(77)90007-8

### Branch Confidence Transfer

`examples.branch_confidence_transfer` tests support-strength evidence. Each
domain records one thin optimistic source commit and three better-supported
source commits. The static target spends one verifier call replaying the thin
optimistic action and fails. The confidence-guided target spends the same one
verifier call on the better-supported action and commits only after fresh hard
verification.

Learning: branches of the past can improve exploration by binding evidence
strength, not only action identity. `trwm.branch_confidence_certificate.v1`
binds source commit counts, source receipt hashes, a fixed Wilson-style lower
bound, static target reject, confidence-guided target commit, branch-selection
certificates, and same-budget comparison before claiming confidence-guided
exploration lift. The Wilson interval is only the support-bound analogy here;
this is not statistical validation or production calibration:
https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm

### Branch Pareto Transfer

`examples.branch_pareto_transfer` tests multi-objective dominance evidence.
Each domain records a source branch where a scalar-favored action is rejected
and a nondominated balanced action commits. The static target spends one
verifier call replaying the scalar action and fails. The Pareto-guided target
spends the same one verifier call on the nondominated action and commits only
after fresh hard verification.

Learning: branches of the past can improve exploration by binding objective
tradeoffs, not only scalar action scores. `trwm.branch_pareto_certificate.v1`
binds dominated and Pareto objective vectors, source reject/commit receipts,
target scalar replay reject, target Pareto commit, branch-selection
certificates, and same-budget comparison before claiming Pareto-guided
exploration lift. NSGA-II is only the non-dominated sorting analogy here; this
is not a multiobjective optimizer or Pareto-front approximation guarantee:
https://doi.org/10.1109/4235.996017

### Branch Outlier-Filter Transfer

`examples.branch_outlier_filter_transfer` tests source-valid anomalous branch
evidence. Each domain records two inlier source commits and one source outlier
commit. The static target spends one verifier call replaying the anomalous
source branch and fails. The inlier-filtered target spends the same one
verifier call on a target action near the source inlier cluster and commits
only after fresh hard verification.

Learning: branches of the past can improve exploration by binding source
provenance in feature space, not only by counting source commits. The new
`trwm.branch_outlier_filter_certificate.v1` binds inlier feature values, source
outlier distance, distance threshold, source inlier/outlier receipts, static
target reject, filtered target commit, branch-selection certificates, and
same-budget comparison before claiming outlier-filtered exploration lift.
RANSAC is only the robust-inlier analogy here; this is not a RANSAC
implementation, robust estimator, or outlier-detection guarantee:
https://doi.org/10.1145/358669.358692

### Branch Provenance-Guard Transfer

`examples.branch_provenance_guard_transfer` tests source-id provenance
admission. Each domain records two trusted source commits and one source-valid
quarantined commit. The static target spends one verifier call replaying the
quarantined-source branch and fails. The provenance-guarded target spends the
same one verifier call on a trusted-source branch and commits only after fresh
hard verification.

Learning: branches of the past can improve exploration only when source
validity is separated from target admissibility. The new
`trwm.branch_provenance_guard_certificate.v1` binds trusted source ids,
quarantined source id, trusted/quarantined source receipts, static target
reject, guarded target commit, branch-selection certificates, and same-budget
comparison before claiming provenance-guarded exploration lift. Byzantine
Generals is only the faulty-source analogy here; this is not a Byzantine
fault-tolerant protocol, consensus algorithm, or security proof:
https://doi.org/10.1145/357172.357176

### Branch Credit-Assignment Transfer

`examples.branch_credit_assignment_transfer` tests marginal-credit evidence for
source branch fragments. Each domain records three source commits: one
high-credit fragment and two source-valid distractors. The static target spends
one verifier call replaying a low-credit distractor and fails. The
credit-guided target spends the same verifier call on the high-credit fragment
and commits only after fresh hard verification.

Learning: branches of the past can improve exploration by binding which source
fragment actually carried useful marginal evidence, not only which source
branch committed. `trwm.branch_credit_assignment_certificate.v1` binds source
actions, credit values, credited and distractor source receipts, failed static
target replay, credit-guided target commit, branch-selection certificates, and
same-budget comparison before claiming credit-guided exploration lift. Shapley
value is only the marginal-contribution analogy here; this is not a
Shapley-value computation, causal inference result, or reinforcement-learning
credit-assignment result: https://doi.org/10.1515/9781400881970-018

### Branch Propensity-Match Transfer

`examples.branch_propensity_match_transfer` tests source-context comparability.
Each domain records one source-valid but covariate-mismatched branch and one
source-valid matched branch. The static target spends one verifier call replaying
the mismatched-context proposal and fails. The matched target spends the same
one verifier call on the covariate-balanced proposal and commits only after
fresh hard verification.

Learning: branches of the past can improve exploration only when source
validity is separated from target comparability. The new
`trwm.branch_propensity_match_certificate.v1` binds target/source covariates,
propensity-style scalar scores, caliper distance, covariate L1 distance,
source receipts, failed static target replay, matched target commit,
branch-selection certificates, and same-budget comparison before claiming
matching-guided exploration lift. Propensity score matching is only the
covariate-balance analogy here; this is not a propensity-score estimator,
causal-inference result, covariate-balance proof, or treatment-effect estimate:
https://doi.org/10.1093/biomet/70.1.41

### Branch Robustness Transfer

`examples.branch_robustness_transfer` tests uncertainty-set coverage for source
branch reuse. Each domain records one brittle nominal source commit and three
robust source commits across perturbation variants. The static target spends one
verifier call replaying the brittle nominal source and fails. The robust target
spends the same one verifier call on the uncertainty-set-covered action and
commits only after fresh hard verification.

Learning: branches of the past can improve exploration only when nominal source
validity is separated from uncertainty-set coverage.
`trwm.branch_robustness_certificate.v1` binds variant ids, source/target
contexts, brittle and robust source receipts, robust source margins, failed
static target replay, robust target commit, branch-selection certificates, and
same-budget comparison before claiming robustness-guided exploration lift.
Robust optimization is only the uncertainty-set analogy here; this is not robust
optimization, a worst-case guarantee, or distributional robustness:
https://doi.org/10.1287/moor.23.4.769

### Branch Calibration Transfer

`examples.branch_calibration_transfer` tests confidence-bin calibration for
source branch reuse. Each domain records one overconfident source reject and
three lower-confidence calibrated source receipts whose empirical accept rate
matches the predicted confidence bin. The static target spends one verifier call
replaying the overconfident source family and fails. The calibrated target
spends the same one verifier call on the confidence-bin-supported action and
commits only after fresh hard verification.

Learning: branches of the past can improve exploration only when proposer
confidence is separated from verified reliability.
`trwm.branch_calibration_certificate.v1` binds confidence-bin ids, predicted
confidence values, empirical accept rates, calibration gaps, source receipts,
failed static target replay, calibrated target commit, branch-selection
certificates, and same-budget comparison before claiming calibration-guided
exploration lift. Neural-network calibration is only the reliability-diagram
analogy here; this is not neural-network calibration, statistical calibration,
probability estimation, or model reliability assurance:
https://arxiv.org/abs/1706.04599

### Branch Conformal Transfer

`examples.branch_conformal_transfer` tests receipt-bound nonconformity
envelopes for source branch reuse. Each domain records three in-envelope source
calibration commits and one out-of-envelope source reject. The static target
spends one verifier call replaying an out-of-envelope source-like action and
fails. The conformal target spends the same one verifier call on an
in-envelope action and commits only after fresh hard verification.

Learning: branches of the past can improve exploration only when source replay
admission is separated from raw similarity.
`trwm.branch_conformal_certificate.v1` binds calibration action ids,
nonconformity scores, alpha, quantile rank, quantile value, out-of-envelope
source reject, failed static target replay, conformal target commit,
branch-selection certificates, and same-budget comparison before claiming
nonconformity-guided exploration lift. Conformal prediction is only the
nonconformity-envelope analogy here; this is not conformal prediction,
distribution-free coverage, conditional coverage, or uncertainty
quantification: https://arxiv.org/abs/1604.04173

### Branch Active-Subspace Transfer

`examples.branch_active_subspace_transfer` tests receipt-bound low-rank
proposal filtering for source branch reuse. Each domain records two committed
source proposals whose direction vectors project strongly onto a one-dimensional
active axis, plus one rejected source proposal on the orthogonal axis. The
static target spends one verifier call on an orthogonal replay and fails. The
active-subspace target spends the same one verifier call on an in-subspace
proposal and commits only after fresh hard verification.

Learning: branches of the past can improve exploration only when reusable
search directions are certificate-bound and remain separate from commit
authority. `trwm.branch_active_subspace_certificate.v1` binds the active and
orthogonal basis vectors, exact dot-product projection scores, projection
threshold, source active receipts, source orthogonal reject, failed static
target replay, active-subspace target commit, branch-selection certificates,
and same-budget comparison before claiming low-rank direction-guided
exploration lift. Active subspaces are only the dimension-reduction analogy
here; this is not active-subspace discovery, dimensionality-reduction
performance, optimization, or uncertainty quantification:
https://doi.org/10.1137/1.9781611973860

### Branch Sensitivity Transfer

`examples.branch_sensitivity_transfer` tests receipt-bound one-factor
perturbation evidence for source branch reuse. Each domain records a source
negative perturbation that rejects and a source positive perturbation that
commits. The static target spends one verifier call on the wrong perturbation
direction and fails. The sensitivity-guided target spends the same one verifier
call on the useful perturbation direction and commits only after fresh hard
verification.

Learning: branches of the past can improve exploration only when parameter
direction evidence is certificate-bound and remains separate from commit
authority. `trwm.branch_sensitivity_certificate.v1` binds the parameter id,
baseline value, perturbation delta, source negative and positive receipts,
failed wrong-direction target receipt, sensitivity-guided target commit,
branch-selection certificates, and same-budget comparison before claiming
sensitivity-guided exploration lift. Morris elementary effects and SPSA are
only sensitivity and perturbation analogies here; this is not a sensitivity
analysis algorithm, elementary-effects screening result, SPSA implementation,
finite-difference accuracy claim, derivative estimate, or gradient-estimation
guarantee: https://doi.org/10.1080/00401706.1991.10484804 and
https://doi.org/10.1109/9.119632

### Branch Shield-Fallback Transfer

`examples.branch_shield_fallback_transfer` tests receipt-bound guard/fallback
evidence for source branch reuse. Each domain records a source unsafe-family
proposal that rejects and a source fallback-family proposal that commits. The
static target spends one verifier call on the unsafe family and fails. The
shield-guided target spends the same one verifier call on the fallback family
and commits only after fresh hard verification.

Learning: branches of the past can improve exploration only when runtime guard
evidence is certificate-bound and remains separate from commit authority.
`trwm.branch_shield_fallback_certificate.v1` binds the shield spec id, unsafe
family, fallback family, source unsafe reject, source fallback commit, failed
unsafe target receipt, shield-fallback target commit, branch-selection
certificates, and same-budget comparison before claiming shield-guided
exploration lift. Shielded reinforcement learning and shield synthesis are
only guard/fallback analogies here; this is not shield synthesis, runtime
assurance, safe reinforcement learning, temporal-logic enforcement, controller
switching, or a safety case: https://doi.org/10.1609/aaai.v32i1.11797 and
https://pmc.ncbi.nlm.nih.gov/articles/PMC6959420/

### Branch Potential-Heuristic Transfer

`examples.branch_potential_heuristic_transfer` tests receipt-bound potential
values for source branch reuse. Each domain records a high-potential proposal
that rejects and a low-potential proposal that commits. The static target
spends one verifier call on the high-potential branch and fails. The
potential-guided target spends the same one verifier call on the low-potential
branch and commits only after fresh hard verification.

Learning: branches of the past can improve exploration only when heuristic
priority is certificate-bound and remains separate from commit authority.
`trwm.branch_potential_heuristic_certificate.v1` binds the potential id,
threshold, high-potential source reject, low-potential source commit, failed
high-potential target receipt, low-potential target commit, branch-selection
certificates, and same-budget comparison before claiming heuristic-guided
exploration lift. A* and potential-based reward shaping are only search-priority
analogies here; this is not A* search, an admissible heuristic proof,
shortest-path optimality, potential-based reward shaping, policy invariance,
reinforcement learning, or pattern-database search:
https://doi.org/10.1109/TSSC.1968.300136 and
https://ai.stanford.edu/~ang/papers/shaping-icml99.pdf

### Branch Continuation Transfer

`examples.branch_continuation_transfer` tests receipt-bound continuation paths
for source branch reuse. Each domain records three committed source
continuation steps along a lambda schedule and one rejected source direct jump.
The static target spends the same three verifier calls on direct jump proposals
and commits nothing. The continuation target spends three verifier calls on the
receipt-bound intermediate path and commits each step after fresh hard
verification.

Learning: branches of the past can improve exploration by shaping the path to a
hard target, not only by selecting one proposal. `trwm.branch_continuation_certificate.v1`
binds lambda values, max lambda step, source path receipts, source direct-jump
reject, static direct-jump target rejects, continuation target commits,
branch-selection certificates, and same-budget comparison before claiming
continuation-guided exploration lift. Numerical continuation is only the
path-following analogy here; this is not numerical continuation, homotopy
continuation, nonlinear root finding, or path-following performance:
https://doi.org/10.1137/1.9780898719154

### Branch Commutativity Transfer

`examples.branch_commutativity_transfer` tests receipt-bound partial-order
commutativity for source branch reuse. Each domain records two committed source
orders that share a canonical key and one rejected source conflict order. The
static target spends one verifier call on the non-canonical conflict order and
fails. The commutativity-guided target spends the same one verifier call on the
canonical independent order and commits only after fresh hard verification.

Learning: branches of the past can improve exploration when the substrate can
prove which orders are independent and which order is a known conflict.
`trwm.branch_commutativity_certificate.v1` binds the canonical order key,
conflict order key, source AB commit, source BA commit, source conflict reject,
failed static target order, commutative target commit, branch-selection
certificates, and same-budget comparison before claiming commutativity-guided
exploration lift. Partial-order reduction is only the independence analogy
here; this is not a partial-order reduction algorithm, model-checking
correctness proof, dynamic partial-order reduction result, concurrency
verification result, or state-space reduction guarantee:
https://lics.siglog.org/1996/WillemsWolper-PartialOrderMethods.html and
https://patricegodefroid.github.io/public_psfiles/popl2005.pdf

### Branch Switch Transfer

`examples.branch_switch_transfer` tests receipt-bound switchpoint admission for
source branch reuse. Each domain records a source pre-switch commit, then a
stale post-switch source reject and a switched post-switch source commit. The
static target spends one verifier call on the stale post-switch branch and
fails. The switched target spends the same one verifier call on the switched
branch and commits only after fresh hard verification.

Learning: branches of the past can improve exploration only when switchpoint
evidence is certificate-bound and stale post-switch reuse fails closed.
`trwm.branch_switch_certificate.v1` binds the switch parameter, stale and
switched branch ids, source pre-switch commit, source stale reject, source
switched commit, failed static target branch, switched target commit,
branch-selection certificates, and same-budget comparison before claiming
switchpoint-guided exploration lift. Branch switching and bifurcation analysis
are only the switchpoint analogy here; this is not bifurcation analysis,
branch-switching algorithm performance, numerical continuation, or homotopy
continuation: https://eudml.org/doc/132842 and
https://research.ibm.com/publications/multiparameter-parallel-search-branch-switching--1

### Branch Transposition Transfer

`examples.branch_transposition_transfer` tests receipt-bound canonical-state
transposition for source branch reuse. Each domain records a source branch that
reaches a rejected canonical state and a non-duplicate source branch that
commits. The static target spends one verifier call on a different action that
reaches the same rejected canonical state and fails. The transposition-guided
target spends the same one verifier call on a non-duplicate candidate and
commits only after fresh hard verification.

Learning: branches of the past can improve exploration when the substrate can
prove two differently named branches hit the same canonical state. The
`trwm.branch_transposition_certificate.v1` artifact binds canonical state key,
source duplicate reject, source alternative commit, static duplicate target
reject, transposition target commit, branch-selection certificates, and
same-budget comparison before claiming transposition-guided exploration lift.
Transposition tables, Zobrist hashing, and duplicate detection are only the
analogy here; this is not a transposition-table performance result,
Zobrist-hashing implementation, duplicate-detection algorithm, or graph-search
scalability result: https://journals.sagepub.com/doi/10.3233/ICG-1990-13203
and https://aaai.org/Papers/AAAI/2004/AAAI04-108.pdf

### Branch Pruning Transfer

`examples.branch_pruning_transfer` tests negative branch evidence. Each domain
records a source branch with two hard-rejected actions and one committed
winner. The unpruned target spends the same two-call verifier budget on the
known-dead actions and commits nothing. The pruning certificate removes those
actions from the target candidate set, and the pruned target commits under the
same two-call budget.

Learning: rejection receipts can improve exploration by changing what the next
search is allowed to spend verifier budget on. This is still only an admission
filter: `trwm.branch_pruning_certificate.v1` binds source rejects, target
baseline rejects, pruned target receipts, branch-selection certificates, and
same-budget comparison, but the surviving candidate still needs hard
verification before commit.

### Branch Diversity Transfer

`examples.branch_diversity_transfer` tests coverage pressure. Each domain first
records two same-family source rejects and one committed repair. The repeated
family target baseline spends two verifier calls on the same saturated failure
family and commits nothing. The diversity-certified target spends the same two
verifier calls across a distinct failure family and the repair family, then
commits after hard verification.

Learning: past failures can improve exploration by shaping coverage, not only
by pruning or ranking. `trwm.branch_diversity_certificate.v1` binds source
reject families, target baseline families, diverse target families, receipt
hashes, branch-selection certificates, and same-budget comparison before
claiming that diversity pressure improved exploration.

### Branch Budget Transfer

`examples.branch_budget_transfer` tests receipt-guided verifier-budget
allocation. Each domain records past branch receipts that identify a cheap
reject probe and a higher-cost repair. The static target spends the same
three-unit verifier budget on two cheap rejects, then abstains the repair
because the remaining budget is insufficient. The receipt-guided target spends
one cheap probe plus the repair, and commits under the same total budget after
hard verification.

Learning: branches of the past can improve exploration by shaping how scarce
verifier cost is allocated, not only by choosing an order or pruning actions.
`trwm.branch_budget_certificate.v1` binds the memory receipts, static and
allocated receipt hashes, abstain counts, exact spent verifier cost, and
same-budget comparison before claiming budget-allocation lift.

### Branch Stop-Rule Transfer

`examples.branch_stop_rule_transfer` tests no-good abstention. Each domain
records source receipts with two hard rejects from the same failure family and
one committed repair as a positive control. The static target spends two
verifier calls on the matched failure family and commits nothing. The
stop-rule target sees the same candidate surface, records two abstain receipts,
spends zero verifier calls, and promotes no target commit.

Learning: branches of the past can improve exploration by certifying when not
to explore. `trwm.branch_stop_rule_certificate.v1` binds source rejects,
source commits, static target rejects, stop-rule abstentions, branch-selection
certificates, unused verifier budget, and the same-budget comparison before
claiming that no-good stop evidence avoided verifier spend.

### Branch Composition Transfer

`examples.branch_composition_transfer` tests whether branches of the past can
improve proposal construction, not only proposal ordering. Each domain records
two source branches whose committed receipts represent distinct hard-gate
fragments. Static target proposals fail under one verifier call, and each
single-fragment target proposal also fails under one verifier call. The composed
target proposal combines both source fragments and commits under the same
one-call budget after hard verification.

Learning: composition needs its own certificate boundary. Source branch receipts
can justify constructing a composed candidate, but they cannot promote it. The
new `trwm.branch_composition_certificate.v1` binds source contexts, fragment
keys, source receipts, target receipts, branch-selection certificates, and the
same-budget comparison before claiming branch-composition lift.

### Context Retention Transfer

`examples.context_retention_transfer` extends the refinement loop. After each
domain records a failed coarse target branch, it refines ancestor retrieval,
commits the refined target branch, and emits an
`trwm.ancestral_branch_retention_certificate.v1` certificate for adding that
committed target receipt to memory. Before the sibling target spends verifier
budget, a `trwm.ancestral_branch_influence_certificate.v1` certificate binds
the memory snapshot, retained target context, candidate action set, ranked
order, top action, and supporting retained receipt hashes. The sibling target
then commits under the same hard verifier. The report also records a
same-budget ablation certificate: the static sibling pass spends one verifier
call on the old first proposal and fails, while the influence-ranked sibling
pass spends one verifier call and commits.

Learning: the closed loop is now retrieve, fail, refine, commit, retain, then
certify influence for the next exploration, with a matched static baseline.
Retention and influence are still evidence, not authority: the sibling branch
must pass verification, branch-selection audit, ledger audit, replay audit, and
rollback audit before commit.

### Branch History Frontier

`examples.branch_history_frontier` runs the forty-six branch-history experiments and
validates their evidence certificates, primary experiment certificates, and
claim certificates. It emits `trwm.example.branch_history_frontier.v1`, a
bounded aggregate report for the staged path from receipt-bound proposal
ordering through accepted-loser counterfactual reuse, option-family
abstraction, prerequisite ordering, curriculum sequencing, regime-conditioned contingency reuse,
hindsight goal relabeling, receipt-bound field intervention, receipt-bound
diagnostic probing, residual-template repair, boundary bracketing, source
consensus, contrastive invariant transfer, trust-region radius transfer, analogical ancestor reuse, certified context selection,
counterexample refinement,
conflict-aware query-policy transfer,
drift quarantine, recency-weighted source freshness, restart-anchor backtracking, typed symmetry transfer, pairwise constraint transfer, confidence-bound support, Pareto-front transfer, outlier-filter transfer, provenance-guard transfer, credit-assignment transfer, propensity-match transfer, robustness transfer, confidence calibration, conformal transfer, active-subspace transfer, sensitivity transfer, shield-fallback transfer, potential-heuristic transfer, continuation transfer, commutativity transfer, branch-switch transfer, transposition transfer, receipt-bound branch pruning, diversity-certified family
coverage, branch budget allocation, no-good stop-rule abstention, branch composition, and retained-memory
influence.

Learning: the current branch-history direction is only coherent when every
stage validates: raw past branches reorder proposals, explicit ancestor reuse is
bounded, accepted losers are reused only through a counterfactual certificate,
option families adapt exact actions only through an abstraction certificate,
prerequisite order is admitted only through a stateful prerequisite certificate,
regime-conditioned reuse is admitted only through a contingency certificate,
hindsight relabeling is admitted only through a goal/reverification
certificate, field intervention is admitted only through a reject/commit
certificate and fresh target verification, diagnostic probing is admitted only
through probe/final receipts under a matched budget, residual templates are
admitted only through source reject/repair receipts and fresh target
verification, boundary brackets are admitted only through source reject/safe
receipts and fresh target verification, source consensus is admitted only
through majority receipts plus fresh target verification, contrastive invariants
are admitted only through positive/negative source receipts plus fresh target
verification, context selection is certified, failed branches refine retrieval,
conflicts are certificate-bound, drift is quarantined, recency is certificate-bound, restart anchors are certificate-bound, typed symmetry transforms are certificate-bound, pairwise constraints are certificate-bound, confidence support is certificate-bound, Pareto dominance is certificate-bound, outlier filtering is certificate-bound, source provenance is certificate-bound, source-fragment credit is certificate-bound, source-context matching is certificate-bound, uncertainty-set coverage is certificate-bound, confidence-bin calibration is certificate-bound, nonconformity quantiles are certificate-bound, active-subspace directions are certificate-bound, sensitivity axes are certificate-bound, shield fallbacks are certificate-bound, heuristic potentials are certificate-bound, continuation paths are certificate-bound, commutative orders are certificate-bound, switchpoints are certificate-bound, canonical transpositions are certificate-bound, rejected branches prune
known-dead target candidates, same-family failures force coverage only through
a certificate, verifier budget is allocated only through a cost-bound
certificate, branch fragments compose
only through a certificate, and retained memory is compared against a
same-budget baseline.

### Programmable World Model Frontier

`examples.programmable_world_model_frontier` runs all three certified examples,
validates their evidence and claim certificates, and emits
`trwm.example.programmable_world_model_frontier.v1`. The report compares the
verifier law, rejected proposal type, residual kind, committed repair, and next
substrate requirement for each domain.

Learning: the shared path toward a programmable transactional world model is
typed physical state plus hard domain-law verification, receipt-bound parameters
or randomness, replay/rollback adapters, residual repair surfaces, and evidence
certificates before claim promotion.

## Source Math Pointers

- Control-barrier-function-style safety sets are the design analogy for the
  robotics signed-distance gate: https://arxiv.org/abs/1903.11199
- Velocity-Verlet integration is the molecular-dynamics gate used in the
  Lennard-Jones example; a classic source is Swope, Andersen, Berens, and
  Wilson, J. Chem. Phys. 76, 637-649 (1982), doi:10.1063/1.442716.
- Metropolis acceptance for statistical mechanics proposals traces to
  Metropolis, Rosenbluth, Rosenbluth, Teller, and Teller, J. Chem. Phys. 21,
  1087 (1953), doi:10.1063/1.1699114.
- Experience replay and planning as speedup mechanisms are discussed in Lin,
  Machine Learning 8, 293-321 (1992), doi:10.1007/BF00992699.
- Counterfactual regret is the design analogy for separating "what could have
  happened" evidence from committed outcomes:
  https://papers.nips.cc/paper/3306-regret-minimization-in-games-with-incomplete-information
- Shapley value is the marginal-contribution analogy for source-fragment credit
  assignment, not a computed game-theoretic value:
  https://doi.org/10.1515/9781400881970-018
- Propensity score matching is the covariate-balance analogy for target/source
  context comparability, not a causal estimate:
  https://doi.org/10.1093/biomet/70.1.41
- Robust optimization is the uncertainty-set analogy for branch robustness
  coverage, not a worst-case or distributional guarantee:
  https://doi.org/10.1287/moor.23.4.769
- Reliability diagrams and expected calibration error are the confidence-bin
  analogy for branch calibration, not a model calibration guarantee:
  https://arxiv.org/abs/1706.04599
- Conformal prediction/nonconformity quantiles are the envelope analogy for
  branch-conformal transfer, not a coverage guarantee:
  https://arxiv.org/abs/1604.04173
- Active subspaces are the low-rank direction analogy for branch-active-subspace
  transfer, not an optimization or dimension-reduction guarantee:
  https://doi.org/10.1137/1.9781611973860
- Morris elementary effects and SPSA are the one-factor perturbation analogies
  for branch-sensitivity transfer, not sensitivity-analysis or gradient
  guarantees:
  https://doi.org/10.1080/00401706.1991.10484804 and
  https://doi.org/10.1109/9.119632
- Shielded reinforcement learning and shield synthesis are the guard/fallback
  analogies for branch-shield-fallback transfer, not runtime assurance or
  safety-case guarantees:
  https://doi.org/10.1609/aaai.v32i1.11797 and
  https://pmc.ncbi.nlm.nih.gov/articles/PMC6959420/
- A* and potential-based reward shaping are the search-priority analogies for
  branch-potential-heuristic transfer, not admissible-heuristic or policy
  invariance guarantees:
  https://doi.org/10.1109/TSSC.1968.300136 and
  https://ai.stanford.edu/~ang/papers/shaping-icml99.pdf
- Numerical continuation is the path-following analogy for branch-continuation
  transfer, not a continuation-method guarantee:
  https://doi.org/10.1137/1.9780898719154
- Partial-order methods are the independence analogy for branch-commutativity
  transfer, not a model-checking correctness or state-space reduction
  guarantee:
  https://lics.siglog.org/1996/WillemsWolper-PartialOrderMethods.html and
  https://patricegodefroid.github.io/public_psfiles/popl2005.pdf
- Branch switching and bifurcation points are the switchpoint analogy for
  branch-switch transfer, not a bifurcation or branch-switching performance
  guarantee:
  https://eudml.org/doc/132842 and
  https://research.ibm.com/publications/multiparameter-parallel-search-branch-switching--1
- Zobrist-style transposition tables and structured duplicate detection are
  the canonical-state analogy for branch-transposition transfer, not a
  graph-search scalability guarantee:
  https://journals.sagepub.com/doi/10.3233/ICG-1990-13203 and
  https://aaai.org/Papers/AAAI/2004/AAAI04-108.pdf
- UCT/MCTS is the planning analogy for spending samples selectively:
  https://doi.org/10.1007/11871842_29
- Case-based reasoning is the retrieval/reuse/revision analogy for solving a
  new problem from prior cases: Aamodt and Plaza, AI Communications 7(1),
  39-59 (1994), doi:10.3233/AIC-1994-7104.
- The options framework is the temporal-abstraction analogy for treating a
  reusable branch family separately from an exact primitive action:
  https://doi.org/10.1016/S0004-3702(99)00052-1
- Pearl's intervention language is the analogy for explicit variable edits in
  the branch-intervention example; this repo does not claim causal inference:
  https://pmc.ncbi.nlm.nih.gov/articles/PMC2836213/
- Lindley's information-provided-by-an-experiment paper is the analogy for
  choosing a useful diagnostic probe; this repo does not claim Bayesian
  experimental design:
  https://doi.org/10.1214/aoms/1177728069
- SafeOpt is the safe-exploration analogy for expanding toward useful
  candidates while respecting safety constraints; this repo does not claim
  safe Bayesian optimization:
  https://proceedings.mlr.press/v37/sui15.html
- Query by committee is the active-learning analogy for using disagreement
  between models or sources as evidence; this repo does not claim statistical
  active-learning performance:
  https://doi.org/10.1145/130385.130417
- Version-space candidate elimination is the analogy for using positive and
  negative examples to constrain a concept; this repo does not claim concept
  learning or classifier performance:
  https://www.ijcai.org/Proceedings/77-1/Papers/048.pdf
- Contextual bandits with side information are the analogy for conditioning a
  branch choice on observable target context:
  https://papers.nips.cc/paper/3178-the-epoch-greedy-algorithm-for-multi-armed-bandits-with-side-information
- Discounted and sliding-window UCB for non-stationary bandits are the analogy
  for letting recent receipt evidence override stale cumulative history; this
  repo does not claim bandit regret guarantees:
  https://arxiv.org/abs/0805.3415
- Heavy-tailed SAT/CSP search and random restarts are the analogy for
  abandoning local continuation in favor of a restart anchor; this repo does
  not claim SAT/CSP restart performance:
  https://doi.org/10.1023/A:1006314320276
- Hindsight Experience Replay is the goal-relabeling analogy for learning from
  outcomes that missed the originally intended goal:
  https://papers.neurips.cc/paper/7090-hindsight-experience-replay
- Holland's adaptive-system work is the design analogy for treating useful
  past branch fragments as recombinable proposal building blocks:
  https://direct.mit.edu/books/monograph/2574/Adaptation-in-Natural-and-Artificial-SystemsAn
- Negative-transfer surveys motivate explicit rejection of misleading sources:
  https://arxiv.org/abs/2009.00909
- Counterexample-guided abstraction refinement is the analogy for refining a
  coarse selection after a failed counterexample:
  https://doi.org/10.1007/10722167_15
- Active learning is the analogy for spending verifier feedback to improve the
  next query policy: https://minds.wisconsin.edu/handle/1793/60660
- Branch-and-bound pruning is the optimization analogy for avoiding
  subproblems that cannot improve the search:
  https://www.sciencedirect.com/science/article/pii/S1572528616000062
- Nogood learning and CDCL are the constraint-search analogies for reusing
  conflicts to avoid repeating failed branches:
  https://digitalcommons.unl.edu/csetechreports/158/ and
  https://users.aalto.fi/~tjunttil/2020-DP-AUT/notes-sat/cdcl.html
- Novelty search and MAP-Elites are the diversity-search analogies for using
  behavior or feature coverage as an exploration pressure:
  https://pubmed.ncbi.nlm.nih.gov/20868264/ and
  https://arxiv.org/abs/1504.04909
- Hyperband and successive resource allocation are the budget-search analogies
  for spending limited verifier cost on promising branches while early-stopping
  weak branches: https://jmlr.org/papers/v18/16-558.html and
  https://arxiv.org/abs/1603.06560

## Receipt-Trained Reversible Proposer Benchmark

Run:

```bash
python3 -m examples.receipt_trained_reversible_proposer_benchmark
```

This emits JSON with top-level `report`, `evidence_certificate`,
`learning_certificate`, and `claim_certificate`.

The example is the first explicit benchmark gate for the current proof target:
a receipt-trained reversible proposer must reduce hard-verifier calls while
preserving zero invalid commits on held-out task families. It covers four local
canaries:

- robotics: signed-distance/collision-free proposal repair,
- hardware: RVFI-style formal assertion repair,
- program: triggering-test patch repair,
- quantum: equivalence-preserving circuit rewrite repair.

The held-out comparison is matched by task family. The static baseline tries a
known rejected proposal before the repair and spends eight hard-verifier calls
across four domains. The receipt-trained reversible proposer ranks the repair
first and spends four hard-verifier calls, while both arms commit all four
held-out tasks and the ledger records zero invalid commits.

This is still G1 local evidence. The real-task adapter path should now execute
MotionBenchMaker/MoveIt/OMPL robotics tasks, `riscv-formal` RVFI instruction
checks, Defects4J active bug IDs, and MQT Bench/RevLib circuits checked through
MQT QCEC.

## Real-Task Benchmark Readiness Gate

Run:

```bash
python3 -m examples.real_task_benchmark_manifest
```

This emits JSON with top-level `manifest`, `preflight_report`,
`manifest_certificate`, and `claim_certificate`.

The readiness gate names the concrete external benchmark adapters needed before
the local canary can become real-task evidence:

- robotics: MotionBenchMaker/OMPL manipulation problem sets,
- hardware: task-root-backed `riscv-formal` RVFI checks through SymbiYosys/Yosys,
- program: Defects4J active bug ids with triggering/relevant tests,
- quantum: MQT Bench and RevLib circuits checked by MQT QCEC.

The gate is intentionally fail-closed. If a required tool, Python module, or
environment variable is missing, the readiness claim is `rejected`; this is not
a performance result and cannot support the final receipt-trained proposer
claim. Task-root environment variables must point at existing directories. A
supported readiness claim also requires the expected robotics candidate
`command.json` files and hardware task candidate directories/shared
`genchecks.py` file. Each probe carries an `evidence_hash` over its tool,
module, environment, or task-asset evidence; available task assets are
fingerprinted so task-package drift changes the preflight report hash. A
supported readiness claim only means the adapters are ready to run and produce
benchmark receipts.

## Robotics Motion Benchmark Adapter

Run:

```bash
python3 -m examples.robotics_motion_benchmark_adapter
```

This emits JSON with top-level `report`, `learning_certificate`,
`evidence_certificate`, and `claim_certificate`. The adapter is dependency-free
by default: if `roslaunch` or `TRWM_MOTION_BENCHMARK_TASK_ROOT` is unavailable,
it emits a rejected claim and a G0 adapter evidence certificate with zero
receipts.

When ROS and the task root are available, the adapter expects candidate
directories under `$TRWM_MOTION_BENCHMARK_TASK_ROOT/<task>/<candidate>/`.
Each candidate directory must provide `command.json` with `launch_package`,
`launch_file`, optional `args`, and optional `result_file`. The adapter runs
`roslaunch <launch_package> <launch_file> <candidate_args>` in that directory
and accepts only a benchmark result with `solved=true`, a correct solution flag,
`approximate_solution=false`, and an explicit nonnegative solution clearance.
The baseline tries an unsafe motion candidate before the safe candidate. The
receipt-trained reversible proposer can rank the safe candidate first on
held-out tasks. Training receipts are consumed first, then the baseline and
learned held-out arms start from the same frozen post-training state on
separate ledgers. The claim is supported only if the real backend is available,
held-out arm isolation is certificate-bound, held-out success is preserved,
hard-verifier calls are reduced, replay/rollback audits pass, and invalid
commits remain zero.

This is not a robotics safety proof or a planner-performance claim. It is a
real-benchmark adapter surface for task-root-backed MotionBenchMaker/MoveIt/OMPL
candidate directories; broader scene sets, hardware-in-the-loop checks, and
independent audit-verifier receipts remain future work.

## Hardware RISC-V Formal Adapter

Run:

```bash
python3 -m examples.hardware_riscv_formal_adapter
```

This emits JSON with top-level `report`, `learning_certificate`,
`evidence_certificate`, and `claim_certificate`. The adapter is dependency-free
by default: if `sby`, `yosys`, `make`, `python3`, or
`TRWM_RISCV_FORMAL_TASK_ROOT` are unavailable, it emits a rejected claim and a
G0 adapter evidence certificate with zero receipts.

When the toolchain and task root are available, the adapter expects candidate
directories under `$TRWM_RISCV_FORMAL_TASK_ROOT/<task>/<candidate>/`. It runs
`python3 ../../checks/genchecks.py` when checks have not already been generated,
then runs `make -C checks j1` as the hard RVFI verifier. The baseline tries an
RVFI-violating candidate before the compliant candidate. The receipt-trained
reversible proposer can rank the compliant candidate first on held-out check
families. Training receipts are consumed first, then the baseline and learned
held-out arms start from the same frozen post-training state on separate
ledgers. The claim is supported only if the real backend is available,
held-out arm isolation is certificate-bound, held-out success is preserved,
hard-verifier calls are reduced, replay/rollback audits pass, and invalid
commits remain zero.

This is not a RISC-V core correctness proof. It is a real-benchmark adapter
surface for task-root-backed RVFI candidate directories; larger core suites,
coverage strategy, and independent audit-verifier receipts remain future work.

## Program Defects4J Adapter

Run:

```bash
python3 -m examples.program_defects4j_adapter
```

This emits JSON with top-level `report`, `learning_certificate`,
`evidence_certificate`, and `claim_certificate`. The adapter is dependency-free
by default: if `defects4j` or required host tools such as `java`, `git`, `svn`,
or `perl` are unavailable, it emits a rejected claim and a G0 adapter evidence
certificate with zero receipts.

When the Defects4J CLI is available, the adapter creates train and held-out
version-candidate tasks and checks candidates through Defects4J `checkout`,
`compile`, and relevant-test execution. The baseline tries the buggy-version
candidate before the fixed-version candidate. The receipt-trained reversible
proposer can rank the fixed-version candidate first on held-out bugs. Training
receipts are consumed first, then the baseline and learned held-out arms start
from the same frozen post-training state on separate ledgers. The claim is
supported only if the real backend is available, held-out arm isolation is
certificate-bound, held-out success is preserved, hard-verifier calls are
reduced, replay/rollback audits pass, and invalid commits remain zero.

This is not a general automated-program-repair claim. It is a real-benchmark
adapter surface for Defects4J fixed-version candidates; patch generation and
patch-minimization receipts remain future work.

## Quantum MQT Bench Adapter

Run:

```bash
python3 -m examples.quantum_mqt_bench_adapter
```

This emits JSON with top-level `report`, `learning_certificate`,
`evidence_certificate`, and `claim_certificate`. The adapter is dependency-free
by default: if `mqt.bench` or `mqt.qcec` is unavailable, it emits a rejected
claim and a G0 adapter evidence certificate with zero receipts rather than
treating a missing backend as evidence. If the optional backend is available
but task generation or QCEC execution raises, the adapter also fails closed with
a zero-receipt report and a certificate-bound `backend_error`.

When the optional MQT packages are installed, the adapter generates train and
held-out circuit tasks from MQT Bench and checks candidate rewrites with MQT
QCEC equivalence. Training receipts are consumed first, then the baseline and
learned held-out arms start from the same frozen post-training state on
separate ledgers. The learned arm is allowed to support the single-domain
quantum claim only if the real backend is available, held-out arm isolation is
certificate-bound, the learning certificate validates, held-out success is
preserved, hard-verifier calls are reduced, replay/rollback audits pass, and
invalid commits remain zero.

The deterministic backend used by tests exercises the transaction, receipt,
learning, replay, and claim-boundary mechanics. It cannot support a real
quantum benchmark claim.

## Real-Task Benchmark Suite Gate

Run:

```bash
python3 -m examples.real_task_benchmark_suite
```

This emits JSON with top-level `manifest`, `preflight_report`,
`manifest_certificate`, `report`, `suite_certificate`, and
`claim_certificate`. It runs the four optional real adapters, validates their
adapter evidence certificates, child claim certificates, and learning
certificates, cross-checks each certificate against its child report and
manifest spec, and aggregates the preflight report hash,
manifest spec hashes, adapter evidence certificate hashes, child report hashes,
exact receipt counts, typed-candidate hashes, hard-result hashes,
hard-metadata hashes, receipt artifact hashes, backend execution evidence
hashes, baseline calls, learned calls, held-out successes,
replay/rollback/ledger status, missing requirements, backend errors, and
invalid-commit counts. Those compact hash lanes keep external
command/QCEC/test metadata, task/candidate artifact inputs, and readiness probes
auditable without bloating the aggregate report. The normalized
execution-evidence lane also requires the expected domain shape before any
supported real-backend child claim can promote: robotics binds `roslaunch` plus
benchmark-result evidence, hardware binds riscv-formal command execution,
program repair binds Defects4J checkout/compile/relevant-test commands, and
quantum binds QCEC equivalence metadata. The receipt artifact lane binds the
task/candidate inputs: candidate directories and command configs for robotics,
candidate directories and `genchecks.py` for hardware, project/bug/version and
verifier scope for Defects4J, and original/candidate circuit programs for MQT.
The adapter evidence cross-check binds exact training,
baseline, and learned receipt partitions plus any backend execution error
before the manifest cross-check proves the adapter evidence sources are covered
by the domain's real-task manifest spec. The learning cross-check then binds
the learned receipt partition into the learning certificate. Each child report
also binds `heldout_arm_isolated`: after training, the baseline and learned
held-out arms must start from the same frozen post-training state but run on
separate ledgers, so neither arm inherits state mutations or ledger history from
the other.

The suite claim is intentionally stricter than adapter readiness. It is
supported only when all four domains use real backends, all child claims are
supported, every adapter evidence certificate and child claim matches its
report and real-task manifest spec, all learning certificates support call
reduction, every learning certificate matches its report, all held-out arms are
isolated, held-out success is preserved, hard-verifier calls are reduced in
every domain, replay/rollback and ledger audits pass, receipt and
execution-provenance counts bind exact hash lanes, receipt artifact counts bind
exact receipt counts, backend execution evidence counts bind exact receipt
counts, and invalid commits remain zero. Missing external tools or
deterministic test doubles produce a rejected G0 claim rather than weakening the
final objective.

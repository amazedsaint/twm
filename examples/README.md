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
python3 -m examples.branch_contingency_transfer
python3 -m examples.analogical_branch_transfer
python3 -m examples.context_selection_transfer
python3 -m examples.context_refinement_transfer
python3 -m examples.context_query_policy_transfer
python3 -m examples.context_drift_quarantine
python3 -m examples.branch_pruning_transfer
python3 -m examples.branch_diversity_transfer
python3 -m examples.branch_budget_transfer
python3 -m examples.branch_composition_transfer
python3 -m examples.context_retention_transfer
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
The branch-contingency command adds
`trwm.branch_contingency_certificate.v1` artifacts showing that a target
context can select the source branch with the matching regime tag when stale
unconditional reuse fails under the same one-call budget.
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
branch-pruning command adds `trwm.branch_pruning_certificate.v1` artifacts
showing that rejected source branch receipts can prune known-dead target
candidates before scarce verifier budget is spent. The
branch-diversity command adds `trwm.branch_diversity_certificate.v1` artifacts
showing that same-family rejects can force coverage of distinct candidate
families under the same verifier budget. The
branch-budget command adds `trwm.branch_budget_certificate.v1` artifacts
showing that past receipt costs can allocate a fixed verifier budget toward a
higher-cost repair after a cheap reject probe. The
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
the fifteen branch-memory stages into one bounded G1 report. The physical
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

`examples.branch_history_frontier` runs the fifteen branch-history experiments and
validates their evidence certificates, primary experiment certificates, and
claim certificates. It emits `trwm.example.branch_history_frontier.v1`, a
bounded aggregate report for the staged path from receipt-bound proposal
ordering through accepted-loser counterfactual reuse, option-family
abstraction, prerequisite ordering, regime-conditioned contingency reuse,
conflict-aware query-policy transfer, drift quarantine, receipt-bound branch
pruning, diversity-certified family coverage, branch budget allocation, branch
composition, and retained-memory influence.

Learning: the current branch-history direction is only coherent when every
stage validates: raw past branches reorder proposals, explicit ancestor reuse is
bounded, accepted losers are reused only through a counterfactual certificate,
option families adapt exact actions only through an abstraction certificate,
prerequisite order is admitted only through a stateful prerequisite certificate,
regime-conditioned reuse is admitted only through a contingency certificate,
context selection is certified, failed branches refine retrieval, conflicts are
certificate-bound, drift is quarantined, rejected branches prune known-dead
target candidates, same-family failures force coverage only through a
certificate, verifier budget is allocated only through a cost-bound certificate,
branch fragments compose only through a certificate, and retained memory is
compared against a same-budget baseline.

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
- UCT/MCTS is the planning analogy for spending samples selectively:
  https://doi.org/10.1007/11871842_29
- Case-based reasoning is the retrieval/reuse/revision analogy for solving a
  new problem from prior cases: Aamodt and Plaza, AI Communications 7(1),
  39-59 (1994), doi:10.3233/AIC-1994-7104.
- The options framework is the temporal-abstraction analogy for treating a
  reusable branch family separately from an exact primitive action:
  https://doi.org/10.1016/S0004-3702(99)00052-1
- Contextual bandits with side information are the analogy for conditioning a
  branch choice on observable target context:
  https://papers.nips.cc/paper/3178-the-epoch-greedy-algorithm-for-multi-armed-bandits-with-side-information
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

# Research Hypothesis

The proposal is consistent with the recent world-model literature, but it
targets a different layer of the system.

World Models, DreamerV3, TD-MPC2, JEPA-style representation prediction, and
Genie all strengthen learned latent or generative dynamics. RevNets establish
that neural blocks can reconstruct activations exactly under deterministic
reversible structure. NICE and RealNVP establish additive/invertible coupling
families with exact inverse maps. TRWM does not replace those mechanisms. It
wraps proposal dynamics in a transaction substrate:

```text
propose -> type/project -> hard verify -> commit or roll back -> receipt -> learn
```

## Hypothesis

TRWM should improve verifier-call efficiency on low-rank, localized,
repair-structured tasks where:

- candidate objects are typed and deterministic,
- hard verifiers are cheap enough to call repeatedly,
- accepted traces reveal reusable macros,
- rejections expose local residuals,
- replay and rollback bundles are compact.
- domain adapters expose typed projectors and hard verifiers behind a stable
  SDK boundary.

TRWM should show little or no advantage on high-rank random tasks where each
target is independent and terminal-only verification gives no reusable local
structure.

## Implementation Boundary

This repository currently targets `G1` evidence:

- hash-chain ledger and tamper audit,
- hard-verifier-gated transaction commits,
- exact replay and rollback tests,
- integer reversible additive coupling,
- read/write token conflict scheduling with hash-checked parallel replay
  certificates,
- bounded circular token-log compaction with compacted prefix replay plus
  retained suffix replay,
- Game of Life predecessor search as a typed hard-checker domain,
- Sokoban reverse search with forward push-certificate verification,
- small CNF-SAT/CSP residual repair with unsatisfied-clause feedback,
- operations/database-style inventory transaction repair with accounting
  invariants,
- formal proof-kernel canary with typed Horn-rule scripts, residual-guided
  script repair, and premise-checked commits,
- combinational circuit repair canary with exact Boolean op masks, complete
  truth-table verification, and single-gate residual repair,
- organic-subset molecule graph repair canary with explicit bond orders,
  valence/formula checking, and atom/bond residual repair,
- bounded code patch repair canary with base file hashes, a tiny expression
  grammar, full test-suite verification, and operator residual repair,
- 2D point-robot trajectory shield canary with exact segment-circle clearance,
  speed bounds, and residual detour repair,
- bounded chess ancestry canary with king/rook-only last-move certificates,
  rule-subset checking, forward replay, and ambiguity entropy,
- HDC receipt memory with no-memory and exact-match baselines, noisy-query
  retrieval, and tamper detection,
- counterfactual rollback ranking from branch receipts where accepted losers
  are distinguishable from committed winners,
- distributed worker receipts with parent-head anchoring, stale rejection, and
  deterministic equivalence to local branch selection,
- branch-selection certificates that bind receipt hashes, accepted/rejected/
  abstained index sets, selected and committed indices, and loser rollback to
  prove local rank-after-hard-filter,
- branch-counterfactual certificates that bind accepted-but-rolled-back source
  losers, stale target-winner rejects, counterfactual target commits, and
  same-budget verifier-call evidence before rollback losers can guide target
  proposal order,
- branch-abstraction certificates that bind source option-family evidence,
  stale exact-action target rejects, same-family target commits, and
  same-budget verifier-call evidence before abstract branch families can adapt
  exact actions across target contexts,
- branch-prerequisite certificates that bind source prerequisite/final receipts,
  static target rejects, guided prerequisite/final commits, and same-budget
  verifier-call evidence before past branches can impose stateful target
  exploration order,
- branch-curriculum certificates that bind source easy-to-hard sequences,
  static direct-target rejects, guided curriculum commits, guided final commits,
  and same-budget verifier-call evidence before past branches can prescribe
  target difficulty order,
- branch-contingency certificates that bind stale and matched source regimes,
  static target rejects, contingent target commits, selected/rejected source
  contexts, and same-budget verifier-call evidence before past branches can be
  reused through a context-feature switchpoint,
- branch-hindsight-relabel certificates that bind rejected source receipts,
  intended goals, achieved/relabeled goals, static target rejects, relabeled
  target commits, and same-budget verifier-call evidence before rejected
  branches can guide a new target-goal proposal,
- branch-intervention certificates that bind source reject/commit receipts,
  typed verifier-field before/after values, static target rejects, intervened
  target commits, and same-budget verifier-call evidence before past branches
  can suggest target field edits,
- branch-diagnostic-probe certificates that bind source probe reject/commit
  receipts, static unprobed target rejects, guided probe commits, guided final
  commits, and same-budget verifier-call evidence before past branches can
  suggest what target diagnostic to run before acting,
- branch-residual-template certificates that bind source reject/repair
  receipts, static target rejects, templated target commits, template fields,
  and same-budget verifier-call evidence before residual repair templates can
  guide target proposals,
- branch-boundary-bracket certificates that bind source unsafe/safe endpoint
  receipts, static target rejects, bracketed target commits, bracket fields,
  and same-budget verifier-call evidence before target threshold candidates can
  be prioritized,
- branch-consensus certificates that bind majority source receipts, singleton
  source receipts, support counts, static target rejects, consensus target
  commits, and same-budget verifier-call evidence before multi-source agreement
  can prioritize target proposal families,
- branch-invariant certificates that bind positive source receipts, negative
  source receipts, invariant field keys, static target rejects, invariant target
  commits, and same-budget verifier-call evidence before contrastive source
  signatures can prioritize target proposals,
- branch-trust-region certificates that bind source reject/commit receipts,
  proposal-radius fields, trusted radius caps, static target rejects,
  trust-region target commits, and same-budget verifier-call evidence before
  past branches can size target proposal steps,
- branch-recency certificates that bind older stale source commits, recent
  stale source rejects, recent adapted source commits, static target rejects,
  recency target commits, and same-budget verifier-call evidence before
  receipt freshness can override cumulative branch-history support,
- branch-restart certificates that bind source local-dead-end rejects, source
  restart-anchor commits, static target rejects, restart target commits, and
  same-budget verifier-call evidence before past branches can tell target
  exploration to backtrack or restart,
- branch-symmetry certificates that bind typed transform ids, source commits,
  failed exact target replay, transformed target commits, and same-budget
  verifier-call evidence before past branches can map source actions across a
  mirrored target,
- branch-constraint certificates that bind incompatible and compatible choice
  pairs, source reject/commit receipts, static and constraint-guided target
  receipts, and same-budget verifier-call evidence before past branches can
  shape combinatorial target exploration,
- branch-confidence certificates that bind source support counts, source
  receipt hashes, fixed lower-bound calculations, static and confidence-guided
  target receipts, and same-budget verifier-call evidence before sparse past
  successes can influence target exploration,
- branch-pareto certificates that bind dominated and nondominated objective
  vectors, source reject/commit receipts, static scalar-replay target rejects,
  Pareto-guided target commits, and same-budget verifier-call evidence before
  scalar source preferences can influence target exploration,
- branch-outlier-filter certificates that bind source inlier feature values,
  source-valid outlier receipts, feature-distance thresholds, static outlier
  replay target rejects, filtered target commits, and same-budget verifier-call
  evidence before anomalous committed source branches can influence target
  exploration,
- branch-provenance-guard certificates that bind trusted source ids,
  quarantined source-valid receipts, static quarantined-source target rejects,
  guarded target commits, and same-budget verifier-call evidence before
  source-valid but target-untrusted branches can influence target exploration,
- branch-credit-assignment certificates that bind source actions,
  marginal-credit values, credited and distractor source receipts, static
  low-credit target rejects, credit-guided target commits, and same-budget
  verifier-call evidence before correlated source-valid branch fragments can
  influence target exploration,
- branch-propensity-match certificates that bind target/source covariates,
  propensity-style scores, caliper distances, covariate-balance distances,
  mismatched and matched source receipts, static mismatched target rejects,
  matched target commits, and same-budget verifier-call evidence before
  context-mismatched source-valid branches can influence target exploration,
- branch-robustness certificates that bind uncertainty-set variant ids,
  brittle source receipts, robust source variant receipts, source margins,
  static brittle target rejects, robust target commits, and same-budget
  verifier-call evidence before nominal source-valid branches can influence
  target exploration,
- branch-calibration certificates that bind confidence-bin ids, predicted
  confidence values, empirical accept rates, calibration gaps, overconfident
  source rejects, calibrated source receipts, static overconfident target
  rejects, calibrated target commits, and same-budget verifier-call evidence
  before soft proposer scores can influence target exploration,
- branch-conformal certificates that bind alpha, quantile rank, calibration
  receipt hashes, nonconformity scores, out-of-envelope source rejects, static
  target rejects, conformal target commits, and same-budget verifier-call
  evidence before source replay is admitted by a nonconformity envelope,
- branch-active-subspace certificates that bind active and orthogonal basis
  vectors, dot-product projection scores, projection thresholds, source active
  receipts, source orthogonal rejects, static target rejects, active-subspace
  target commits, and same-budget verifier-call evidence before low-rank source
  directions can filter target proposals,
- branch-sensitivity certificates that bind parameter ids, baseline values,
  perturbation deltas, negative and positive source perturbation receipts,
  static wrong-direction target rejects, sensitivity-guided target commits,
  and same-budget verifier-call evidence before one-factor direction evidence
  can filter target proposals,
- branch-shield-fallback certificates that bind shield spec ids, unsafe
  families, fallback families, unsafe source rejects, fallback source commits,
  static unsafe target rejects, shield-guided target commits, and same-budget
  verifier-call evidence before guard/fallback evidence can filter target
  proposals,
- branch-potential-heuristic certificates that bind potential ids, potential
  thresholds, high-potential source rejects, low-potential source commits,
  static high-potential target rejects, low-potential target commits, and
  same-budget verifier-call evidence before estimated cost-to-feasible-state
  evidence can rank target proposals,
- branch-continuation certificates that bind lambda schedules, max path steps,
  source continuation receipts, source direct-jump rejects, static direct-jump
  target rejects, continuation target commits, and same-budget verifier-call
  evidence before path schedules can filter direct target jumps,
- branch-commutativity certificates that bind canonical order keys, conflict
  order keys, source AB commits, source BA commits, source conflict rejects,
  static non-canonical target rejects, commutative target commits, and
  same-budget verifier-call evidence before independent orders can be
  canonicalized,
- branch-switch certificates that bind switch parameter, stale and switched
  branch ids, source pre-switch receipt, source stale reject, source switched
  commit, static stale reject, switched target commit, and same-budget
  verifier-call evidence before stale post-switch branches can be replaced,
- branch-transposition certificates that bind canonical state keys, duplicate
  source rejects, non-duplicate source commits, static duplicate target
  rejects, transposition target commits, and same-budget verifier-call
  evidence before duplicate target branches can be skipped or demoted,
- branch-pruning certificates that bind rejected source branch receipts,
  pruned target action ids, unpruned/pruned target receipt hashes, and
  same-budget verifier-call evidence before negative branch evidence can
  shape verifier-budget allocation,
- branch-diversity certificates that bind saturated failure families,
  candidate family ids, source and target receipt hashes, and same-budget
  verifier-call evidence before past same-family failures can force coverage
  of distinct candidate families,
- branch-budget certificates that bind receipt-derived verifier-cost memory,
  static and allocated target receipts, abstain counts, exact spent verifier
  cost, and same-budget evidence before past branches can shape scarce
  verifier-resource allocation,
- branch-stop-rule certificates that bind source no-good reject receipts,
  source positive-control commits, static target rejects, stop-rule target
  abstentions, unused verifier budget, and same-budget evidence before past
  branches can avoid target verifier calls without promoting a commit,
- branch-composition certificates that bind two source branch fragments,
  source and target receipt hashes, static/component/composed target
  comparisons, and same-budget verifier-call evidence before a composed
  proposal can be treated as supported G1 exploration lift,
- replay checkpoint certificates that compact audited receipt prefixes while
  preserving suffix parent-head replay and final state/head validation,
- projection contracts that require safety-critical typed-projector fields,
  hash covered source values, and reject omitted or stale verifier inputs,
- verifier-cost-aware receipt routing that ranks committed successes per
  explicit verifier-cost unit instead of treating all hard checks as equal,
- verifier-budget branch execution that records over-budget candidates as
  zero-spend hard-abstain receipts and commits only verified accepted branches,
- receipt-trained verifier-budget planning that selects an exact integer-cost
  candidate subset from conservative success lower bounds,
- hash-checked claim certificates that bind benchmark metrics to explicit
  requirements, evidence grade, and claim boundary,
- trace-disjoint learning-evaluation certificates that bind learner snapshots,
  training receipt hashes, held-out evaluation receipt hashes, same-case
  baseline metrics, and exact verifier-call gain ratios before claim promotion,
- transfer-evaluation certificates that bind source domains, held-out target
  receipts, same-case target baselines, and negative-transfer conclusions
  before any positive cross-domain transfer claim can be promoted,
- transfer-guard snapshots that consume validated transfer certificates and
  block source-domain proposal reuse after observed negative transfer,
- verifier-agreement guarding that requires an independent audit verifier to
  agree with primary accepts before branch-runtime commit admission,
- receipt-trained verifier reliability memory that turns audited agreement and
  false-positive receipts into audit-priority scores and hash-checked snapshots,
- residual standardization that wraps heterogeneous hard-verifier residuals in
  a typed `trwm.residual.v1` envelope for cross-domain learning features,
- residual top-k submission that uses learned residual hints to rank repair
  candidates before spending scarce hard-verifier calls,
- redacted receipt views that replace selected replay/rollback-sensitive fields
  with salted path commitments while preserving the original receipt hash and
  visible verifier decision,
- shape-rank preflight that estimates `r90` and budget fit before running the
  receipt learner,
- prefix-safe macro benchmark with macro-memory reuse,
- shape-conditionality simulator with same-case random baseline,
- browser shape-conditionality demo with receipt-count and HDC-memory
  verifier-call metrics,
- residual program repair benchmark with same-case static baseline,
- bounded macro-memory consolidation that merges duplicate receipt evidence,
  retains high-priority positive and negative rows, forgets weak stale rows, and
  emits a hash-checked snapshot,
- reversible receipt-learned macro proposer with exact cycle canary, matched
  non-reversible baseline, and reversible-only ablation,
- programmable multi-domain SDK benchmark across scalar program repair, Game of
  Life predecessor search, grid macro verification, Sokoban reverse planning,
  operations transactions, proof-kernel checking, circuit verification, and
  molecule graph checking, code-patch checking, robot trajectory checking, and
  chess ancestry checking,
- SDK domain manifest certificates that bind domain adapter type, verifier
  identity, candidate/schema surface, model versions, receipt hashes, ledger
  head, verifier-call accounting, and zero-invalid-commit status,
- SDK transfer-guard route certificates that let validated negative-transfer
  evidence reorder proposal domains before target hard verification,
- transactional world-model step certificates, learner snapshots, and
  learner-update, learner-delta, learner-lineage, and learner-merge
  certificates that bind proposer/projector/learner versions, receipt hashes,
  pre/post/rollback state hashes, verifier identity, ledger head, learner
  update count, learned state, replayable learner-state deltas, source
  receipts, ordered receipt-to-learner transitions, and deterministic evidence
  joins including delta-certified common-prefix partial-overlap joins,
- RRLM-backed world-loop proposal certificates that bind reversible proposal
  snapshots, proposal-certificate hashes, and transport-certificate hashes into
  typed candidate and receipt artifacts while hard verification still owns
  commit authority,
- world-program manifests and certificates that bind executable component
  identities, input/candidate schemas, dependencies, step certificate hashes,
  receipt hashes, final learner snapshot, ledger head, replay/rollback audit
  rate, and RRLM artifact hash groups for an executed world-runtime program,
  plus admission policies/certificates that reject executions missing expected
  components, schemas, dependencies, artifacts, commit counts, invalid-commit
  bounds, or replay/rollback guarantees, plus evidence bundles, bundle
  verification certificates, replay packages, and replay verification
  certificates that package those attestations and validate the underlying
  trace/candidate/receipt/learner body evidence,
- an optional Defects4J program adapter that checks buggy-version and
  fixed-version candidates through Defects4J checkout, compile, and relevant
  tests, fails closed when required CLI tools are missing, and supports a
  program call-reduction claim only on the real backend,
- an optional MQT Bench/QCEC quantum adapter that generates train/held-out
  circuit-equivalence tasks, fails closed when `mqt.bench` or `mqt.qcec` is
  missing, and supports a quantum call-reduction claim only on the real backend,
- browser ESM demos using `trwm.browser.receipt.v1` receipts that are not
  byte-compatible with Python `trwm.receipt.v1` ledger rows.

No learned-model lift, public benchmark lift, or real-world safety claim is made.
The current RRLM result is intentionally bounded: receipt learning reduces macro
attempts versus reversible-only static ordering, but the matched non-reversible
receipt ranker ties it. This is evidence for a reversible auditable proposal
substrate, not evidence that reversibility alone improves the held-out metric.
The current RRLM proposal artifacts make that substrate inspectable: the
snapshot hashes accepted/rejected macro evidence and the proposal certificate
recomputes exact integer transport, ranking order, and cycle count. The
transport certificate separately recomputes forward/inverse roundtrips and
signed-i32 WebGPU admission before the claim audit can use RRLM evidence.
The current SDK result proves shared transaction semantics across eleven domains;
it is not evidence of broad transfer learning. The receipt-domain router learns
domain ordering from accept/reject receipts, but every routed candidate still
passes through its domain hard verifier and ledger audit.
The current SDK transfer-guard result composes routing with the transfer
admission layer: a base route ranks source evidence first, a
`trwm.transfer_guarded_domain_route.v1` certificate blocks that source after
validated negative transfer, and the target-local proposal commits only through
the target verifier. This is a programmable admission primitive, not domain
adaptation.

The branch-selection certificate follows the same architectural boundary as
runtime-assurance systems: untrusted proposal/ranking components may suggest
control, but a trusted monitor must gate authority when safety properties are at
risk. NASA's runtime-assurance formalization describes Simplex/RTA as a trusted
component taking control when an untrusted component violates a safety property:
https://ntrs.nasa.gov/citations/20230017350. The current implementation uses
that as a design analogy only; it is a hash-checked local receipt certificate,
not a theorem-proved controller.

The SDK manifest certificate follows the provenance boundary that domain
artifacts should identify what entities, activities, versions, procedures, and
derivations produced an auditable result. The W3C PROV overview describes
provenance as information useful for assessing quality, reliability, or
trustworthiness in heterogeneous environments:
https://www.w3.org/TR/prov-overview/. The current implementation uses that as a
shape constraint for local SDK manifests only; it is not remote attestation,
package signing, or a sandbox guarantee.
The current transactional world-loop result closes one local proposal-learning
cycle: a scalar proposer is rejected, the hard-verifier residual trains the next
proposal, and the second typed candidate commits only after hard accept,
replay, rollback, manifest, and ledger checks. The step certificate binds the
untrusted proposer/projector/learner components to the receipt, ledger head,
learner-state hash, and learner snapshot hash; the snapshot records the learned
repair and source receipt hashes. The learner-update certificate binds each
receipt hash to the pre-update and post-update learner snapshot hashes, so a
claimed learned-state transition can be audited before it is merged or
promoted. The learner-delta certificate stores a deterministic patch that
replays the pre-update learner state into the post-update learner state. The
learner-lineage certificate binds the ordered update certificate hashes from
the initial learner snapshot to the final learner snapshot, making the
event-sourced learner history explicit. The learner-merge certificate adds the
distributed learning boundary:
duplicate/subset snapshots are idempotent, disjoint receipt evidence can join
deterministic counter-like state, partial-overlap snapshots can join only when
a base snapshot plus per-receipt learner-delta certificates replay both
branches from a common prefix, and conflicting learned repairs are rejected.
This makes learner state auditable and mergeable without making the learner an
authority and without claiming learned-model, cross-domain, or public-benchmark
lift.
The same benchmark now runs an RRLM proposal lane inside the transactional
world runtime: the first reversible macro is rejected, the receipt penalty is
recorded in the RRLM snapshot, the next proposal certificate ranks the repair
macro first, and the commit still happens only through hard verification. The
candidate and receipt artifact hashes bind the RRLM snapshot,
proposal-certificate, and transport-certificate hashes, so tampered RRLM scores
fail validation without giving RRLM commit authority. A separate world-program
manifest and execution certificate wrap that lane, binding the
proposer/projector/learner/verifier identities, schemas, dependencies, step
certificates, receipt hashes, final learner snapshot, ledger head,
replay/rollback result, and grouped RRLM artifact hashes. This makes the
programmed world-loop execution auditable as a unit, not just as disconnected
receipts. A policy admission certificate then checks that this audited
execution matches the expected program identity, component IDs, schemas,
dependencies, required RRLM artifacts, minimum commit/reject counts, zero
invalid commits, and full replay/rollback rate; a missing-artifact policy probe
is rejected as a first-class certificate. The admitted execution is then packed
into a world-program evidence bundle and verified by a bundle certificate that
binds the manifest, execution certificate, admission policy, admission
certificate, step hashes, receipt hashes, final learner snapshot hash, and
artifact groups. A replay package then binds the actual step bodies and a replay
verification certificate checks trace and candidate hashes, receipt bodies,
step certificates, learner-update certificates, learner-delta replay, and
ledger-head recomputation against the admitted bundle.
The current HDC result is similarly bounded: distributed receipt memory can
retrieve useful precedents under context shift in a synthetic low-rank setting,
but it remains only a proposal/ranking substrate.
The current counterfactual rollback result is bounded to branch-choice receipts:
the ranker learns that a hard-accepted but rolled-back loser is weaker evidence
than a committed winner. It is not CFR, RL, policy-gradient learning, or a
claim that the system can infer outcomes it did not verify.
The current projection-contract result is a typed-projection safety canary:
a partial stopping-distance projection omits `safetyClearance` and is accepted
by an intentionally unguarded verifier, while the contract guard rejects it
before commit. A complete fast projection is then rejected by exact integer
stopping-distance math, and a complete slow projection commits with ledger
audit and replay/rollback passing. This is not a proof that every domain can
discover its required fields automatically; the required field set is declared
by the domain adapter contract.
The current verifier-cost result is a routing-accounting canary: when two
domains each commit one valid result, unit-call routing cannot distinguish a
cost-12 verifier from a cost-3 verifier, while the cost-aware router ranks the
exact ratios `1/12` and `1/3` and picks the cheaper equally successful domain.
This is not a UCB or budgeted-bandit claim; it is the receipt-level accounting
primitive needed before such policies are justified.
The current verifier-budget result is a branch-runtime abstention canary:
with verifier budget `4`, the runtime records an accepted but cost-7 branch as
`hard_abstain` without calling the verifier, pays cost `2` for one rejected
branch, pays cost `2` for one accepted branch, and commits only that verified
accepted branch. This follows the selective-classification/reject-option idea
only at the semantic level of withholding an unsafe decision; it is not an
optimal reject-option classifier, budgeted prediction algorithm, or bandit
policy.
The current receipt budget-policy result is a learned verifier-scheduling
canary: three receipts train one success for `quantity-5` and one failure each
for `quantity-8` and `quantity-7`. Under budget `3`, cheap-first scheduling
submits the two cost-1 failures and does not commit; the receipt-trained policy
uses Wilson lower bounds, selects the exact cost-3 `quantity-5` repair, commits
in one hard-verifier call, validates its policy snapshot, and detects snapshot
tampering. This borrows the question shape of budgeted expert prediction and
variable-cost budgeted bandits, but it is deterministic receipt planning, not
UCB, Thompson sampling, online regret minimization, or permission to skip hard
verification.
The current learning-evaluation certificate result tightens that claim
boundary: the policy snapshot hash, training receipt hashes, held-out evaluation
receipt hash, same-budget cheap-first baseline, hard-commit-only evidence, and
exact verifier-call gain `2/1` are bound into a
`trwm.learning_evaluation_certificate.v1` artifact. Train/eval overlap and
metric tampering fail validation. This is a local G1 promotion gate, not a
statistical generalization test, public benchmark protocol, or external
assurance case.
The current transfer-audit result tightens the cross-domain boundary: a
source-only receipt policy trained on a successful `quantity-5` inventory
receipt is evaluated on a target inventory with only two available units. Under
the same one-call target budget, transfer selects `quantity-5` and receives
`stock_shortage`, while the target-local baseline selects and commits
`quantity-2`. The `trwm.transfer_evaluation_certificate.v1` artifact binds
source/target domain ids, source and target receipt hashes, same-case target
baseline metrics, hard-commit-only evidence, and the conclusion
`negative_transfer`. This follows the negative-transfer warning in transfer
learning: source evidence can hurt the target. It is not a domain-adaptation
benchmark or proof of broad transfer.
The current transfer-guard result turns that negative-transfer certificate into
operational admission memory: `TransferGuardMemory` records the validated
source-target conclusion, blocks source-policy reuse with
`negative_transfer_certificate`, and routes the target inventory back to the
same-case `quantity-2` baseline that commits. The guard is a proposal admission
layer only; it cannot commit, cannot skip hard verification, and is not evidence
of domain adaptation.
The current claim-audit result is an evidence-governance canary: a supported
`trwm.claim_certificate.v1` certificate binds selected learning-canary evidence
to explicit requirements for zero invalid commits, ledger audit,
replay/rollback, trace-disjoint evaluation, same-case budgets, verifier-call
accounting, learning-evaluation certificate support, transfer-overclaim
rejection, transfer-guard blocking, RRLM proposal-certificate validation,
RRLM transport-certificate validation, learner-update validation,
learner-delta validation, learner-lineage validation, learner-merge
validation, partial-overlap learner-merge validation, RRLM-backed world-loop
proposal-certificate validation, world-program certificate validation,
world-program admission policy validation, world-program evidence-bundle
verification, world-program replay-package verification, mechanism ablation,
null-result reporting, and G1 claim boundary.
A separate certificate rejects the overclaim that RRLM reversibility alone
improves over a matched non-reversible receipt ranker because the measured gain
is `1.0`. Certificate hashes validate and tampering is detected. This borrows
the shape of provenance and assurance cases, but it is not an external safety
case, public benchmark proof, signed attestation, or real-world safety claim.
The current parallel-replay result is a conflict-serializability canary at the
token-log layer: `DeltaToken` rows declare read/write sets, the scheduler places
only non-conflicting rows in the same batch, and the certificate records both
sequential and batch replay state hashes. The demo sequence forms two batches,
`0,1,3,5` and `2,4`, reaches the same final state under both replays, validates
inverse roundtrip, detects hash tampering, and reports zero mismatches over 64
deterministic randomized read/write trials. This borrows the database
read/write conflict idea, but it is not a database isolation protocol,
deadlock-prevention scheme, lock manager, consensus protocol, or evidence of
parallel speedup on real workloads.
The current circular-token-log result is a bounded-replay canary at the token
layer: old reversible deltas are compacted into a canonical prefix block while
the most recent suffix remains un-compacted. With capacity `3`, eight demo
tokens compact the first five updates into two prefix deltas, retain three
suffix deltas, reach the same final state as full replay, validate inverse
roundtrip, detect certificate tampering, and report zero mismatches over 64
deterministic randomized trials. This follows the snapshot/rehydration and
per-key compaction shape of event-sourced and log-compacted systems, but it is
not a durable event store, Kafka topic, database log, consensus mechanism, or
claim that discarded intermediate events remain available for third-party
audit.
The current verifier-agreement result is a hard-verifier false-positive canary:
an intentionally flawed primary inventory verifier accepts an over-reservation
that commits `unsafe-large` and leaves stock `-3`; that unguarded ledger still
audits because its local hard verifier authorized the receipt. The guarded
runtime wraps the flawed primary with an independent audit verifier, records
the unsafe branch as `verifier_false_positive` with audit residual
`stock_shortage`, and commits `safe-small` to stock `2` with clean
replay/rollback. This follows runtime-assurance and design-diversity practice
at the transaction boundary: primary accepts are not enough when the verifier
itself may be wrong. It is not a proof of verifier independence, complete
specification coverage, or real-world safety.
The current reliability-audit result is a proxy-reliability learning canary:
six verifier-agreement receipts train reliability rows. The strict primary has
three audited successes and zero audited failures; the flawed primary has one
audited success and two audited false positives. Wilson lower bounds rank the
flawed primary as the higher audit risk (`0.061490315276` vs
`0.438493919551`), so with audit budget `1` the reliability policy audits the
flawed primary first and detects a future `stock_shortage` false positive,
while a naive strict-first audit misses that false-positive probe. The snapshot
is hash-checked and tamper detection passes. This borrows observer-reliability
and binomial confidence-bound ideas, but it is not Dawid-Skene inference,
Thompson sampling, a learned safety certificate, or permission to skip required
hard verification.
The current residual-taxonomy result is a residual-standardization canary:
three existing receipt residuals from operations, projection contracts, and
verifier-budget abstention normalize into resource, coverage, and budget
categories. The raw residual hash remains auditable, while a separate normalized
learning hash makes snake/camel variants equivalent for training features. This
borrows the semantic-convention idea of stable names and attributes, but it is
not an ontology-complete residual language or an automatic repair planner.
The current residual-top-k result is a verifier-call scheduling canary:
after a stock-shortage receipt learns `quantity=5`, a candidate pool ordered as
`8, 7, 5, 4` is evaluated under top-k `2`. Unranked top-k submits
`quantity-8` and `quantity-7`, exhausts its two hard-verifier calls, and does
not commit. Residual-ranked top-k submits `quantity-5` first, commits in one
hard-verifier call, audits cleanly, and rolls back to the seed state. This is
in the spirit of counterexample/residual-guided synthesis, but it is not a full
CEGIS, SyGuS, cross-entropy, or optimal repair-search claim.
The current redacted-receipt result is a privacy/audit canary: one committed
inventory receipt is converted into `trwm.redacted_receipt.v1` by redacting
`order_id`, replay `pre_state`, and rollback `pre_state` behind salted path
commitments. The original receipt hash, commit decision, hard-verifier result,
policy hash, and redacted hash remain visible; selective disclosure of the
correct order id verifies, the wrong order id fails, visible-field tampering is
detected, and the redacted view is marked as not replayable. This borrows the
minimal-disclosure and salted-disclosure shape of SD-JWT/VC systems, but it is
not a signed SD-JWT, W3C verifiable credential, zero-knowledge proof,
unlinkability result, or privacy-compliance claim.
The current checkpoint-compaction result is a replay-compression canary: an
audited six-row inventory ledger is split after three receipt rows, and the
prefix is replaced by a `trwm.checkpoint.v1` certificate containing prefix
receipt hashes, the checkpoint head, the materialized checkpoint state, a state
hash, adapter identity, and certificate hash. Replaying from the checkpoint
requires only two committed suffix replays instead of four full-ledger committed
replays, reaches the same final state hash and ledger head, and rejects both
checkpoint-state tampering and stale suffix parent heads. This follows the
checkpoint/snapshot idea from WAL and event-sourcing systems, but it is not a
consensus checkpoint, external signature, public proof that unavailable receipt
bodies were valid, or permission to discard evidence needed for third-party
audit.
The current distributed result is a deterministic worker-receipt simulation, not
a fault-tolerant network protocol. It proves the local and distributed commit
paths choose the same canonical candidate under the same ranker and that stale
worker receipts fail closed.
The current preflight result is a small-matrix executable canary for the
shape-conditionality law: low-rank motif updates fit the compact budget and
high-rank random updates do not.
The current memory-consolidation result is a bounded-learning canary: ten grid
macro receipts are compressed into two retained memory rows for one context.
Duplicate safe macro receipts merge into one positive row, repeated
unsafe-prefix receipts merge into one negative row, weak stale rows are evicted,
and the retained snapshot validates with a stable hash. This follows the
experience-replay idea that not all experiences are equally useful and the
bounded-stream idea that memory must be finite, but it is not an optimal replay
buffer, learned embedding memory, or continual-learning result.
The current Sokoban result is a tiny state-forensics canary: reverse-pull
search proposes one predecessor, while the hard verifier still checks classic
push-only reachability and forward replay before commit.
The current SAT/CSP result is a tiny residual-learning canary: rejected CNF
assignments expose unsatisfied clauses, a repair proposer flips residual-named
variables, and every repaired assignment still requires hard-verifier commit.
The current operations result is a tiny database-style transaction canary:
inventory reservations carry explicit diffs, stock-shortage residuals repair
over-large plans, and accounting conservation is checked before commit.
The current proof-kernel result is a tiny theorem-proving canary: an untrusted
repairer appends residual-suggested Horn rules, while a small trusted checker
rejects missing premises and only commits once the goal is derived. This follows
the LCF/Coq-style separation between tactic/proposal search and kernel
checking, but it is not a general theorem prover or proof assistant.
The current circuit result is a tiny combinational verification canary:
candidates are acyclic Boolean netlists, the hard verifier exhaustively
compares truth tables, and the repairer may replace one mutable gate only after
a verifier residual identifies a unique truth-table-equivalent operator. It is
not a scalable hardware equivalence checker, SAT/BDD engine, HDL compiler, or
sequential-circuit proof.
The current molecule result is a tiny organic-subset graph canary: candidates
change one atom element and one bond order, the hard verifier checks normal
valence and implicit-hydrogen formula, and residual repair can identify the
unique edit that matches a target formula. It is not a SMILES parser, RDKit
replacement, force-field model, aromaticity model, stereochemistry engine,
synthesis planner, or molecule design claim.
The current code-repair result is a tiny unit-test-guided patch canary:
candidates change one operator in a bounded integer expression grammar, carry a
base source hash, and commit only after the full supplied test suite passes and
the ledger replay/rollback audit succeeds. It is not arbitrary Python execution,
whole-repository automatic program repair, semantic correctness beyond the
tests, security analysis, or code-generation evidence.
The current robotics result is a tiny 2D point-robot trajectory-tube canary:
candidates choose one detour lane, the hard verifier checks exact line-segment
clearance against an inflated circular obstacle and a max-step speed bound, and
residual repair replaces an unsafe direct chunk with a verified detour from the
same bounded action set. It is not MuJoCo fidelity, robot hardware safety,
uncertainty handling, dynamics, contacts, or a general motion planner.
The current chess result is a tiny state-forensics canary: candidates propose a
single king/rook predecessor move, the hard verifier checks the relevant legal
move subset and forward replay, and residual repair jumps from a blocked rook
move to the first verified predecessor. It reports three legal histories across
seven candidates on the default board. It is not full chess legality, a chess
engine, opening-history reconstruction, or a claim about competitive chess
search.

## Sources

- Ha and Schmidhuber, World Models: https://arxiv.org/abs/1803.10122
- Hafner et al., DreamerV3: https://arxiv.org/abs/2301.04104
- Hansen et al., TD-MPC2: https://arxiv.org/abs/2310.16828
- Assran et al., I-JEPA: https://arxiv.org/abs/2301.08243
- Bruce et al., Genie: https://arxiv.org/abs/2402.15391
- Dinh et al., NICE: https://arxiv.org/abs/1410.8516
- Dinh et al., RealNVP: https://arxiv.org/abs/1605.08803
- W3C, WebGPU Shading Language: https://www.w3.org/TR/WGSL/
- Gomez et al., RevNet: https://arxiv.org/abs/1707.04585
- Lattner et al., MLIR: Scaling Compiler Infrastructure for Domain Specific
  Computation: https://research.google/pubs/mlir-scaling-compiler-infrastructure-for-domain-specific-computation/
- Schick et al., Toolformer: https://arxiv.org/abs/2302.04761
- Kanerva, Hyperdimensional Computing: https://redwood.berkeley.edu/wp-content/uploads/2020/08/kanerva09-hyperdimensional.pdf
- Plate, Holographic Reduced Representations: https://doi.org/10.1109/72.377968
- Kleyko et al., HDC/VSA Survey: https://arxiv.org/abs/2111.06077
- Schaul et al., Prioritized Experience Replay:
  https://arxiv.org/abs/1511.05952
- Vitter, Random Sampling with a Reservoir:
  https://doi.org/10.1145/3147.3165
- Deb et al., A Fast and Elitist Multiobjective Genetic Algorithm: NSGA-II:
  https://doi.org/10.1109/4235.996017
- Fischler and Bolles, Random Sample Consensus:
  https://doi.org/10.1145/358669.358692
- Lamport, Shostak, and Pease, The Byzantine Generals Problem:
  https://doi.org/10.1145/357172.357176
- Zinkevich et al., Counterfactual Regret Minimization:
  https://papers.nips.cc/paper/3306-regret-minimization-in-games-with-incomplete-information
- Gray and Lamport, Consensus on Transaction Commit:
  https://arxiv.org/abs/cs/0408036
- Schneider, State Machine Approach:
  https://doi.org/10.1145/98163.98167
- Hu et al., LoRA: https://arxiv.org/abs/2106.09685
- Eckart and Young, The Approximation of One Matrix by Another of Lower Rank:
  https://doi.org/10.1007/BF02288367
- Jha and Seshia, A Theory of Formal Synthesis via Inductive Learning:
  https://people.eecs.berkeley.edu/~sseshia/pubs/b2hd-jha-acta17.html
- Alur et al., Syntax-Guided Synthesis:
  https://www.microsoft.com/en-us/research/publication/syntax-guided-synthesis-2/
- Le Goues et al., GenProg: A Generic Method for Automatic Software Repair:
  https://doi.org/10.1109/TSE.2011.104
- Bloem et al., Shield Synthesis:
  https://pmc.ncbi.nlm.nih.gov/articles/PMC6959420/
- Hart, Nilsson, and Raphael, A Formal Basis for the Heuristic Determination
  of Minimum Cost Paths: https://doi.org/10.1109/TSSC.1968.300136
- Ng, Harada, and Russell, Policy Invariance Under Reward Transformations:
  https://ai.stanford.edu/~ang/papers/shaping-icml99.pdf
- LaValle, Planning Algorithms, configuration-space obstacles:
  https://lavalle.pl/planning/node156.html
- Alshiekh et al., Safe Reinforcement Learning via Shielding:
  https://doi.org/10.1609/aaai.v32i1.11797
- Ames et al., Control Barrier Function Based Quadratic Programs for Safety
  Critical Systems: https://authors.library.caltech.edu/records/jnhr0-1ww05
- FIDE Laws of Chess, Article 3 moves, check, and legal move boundary:
  https://handbook.fide.com/chapter/e012023
- JSON Schema Validation, `required` object keyword:
  https://json-schema.org/draft/2020-12/json-schema-validation
- MLIR Dialect Conversion, conversion targets and dynamic legality:
  https://mlir.llvm.org/docs/DialectConversion/
- Ding et al., Multi-Armed Bandit with Budget Constraint and Variable Costs:
  https://doi.org/10.1609/aaai.v27i1.8637
- Auer et al., Finite-time Analysis of the Multiarmed Bandit Problem:
  https://doi.org/10.1023/A:1013689704352
- Garivier and Moulines, On Upper-Confidence Bound Policies for
  Non-Stationary Bandit Problems:
  https://arxiv.org/abs/0805.3415
- Gomes, Selman, Crato, and Kautz, Heavy-Tailed Phenomena in Satisfiability
  and Constraint Satisfaction Problems:
  https://doi.org/10.1023/A:1006314320276
- Cohen and Welling, Group Equivariant Convolutional Networks:
  https://arxiv.org/abs/1602.07576
- Mackworth, Consistency in Networks of Relations:
  https://doi.org/10.1016/0004-3702(77)90007-8
- NIST/SEMATECH e-Handbook, Wilson confidence intervals for proportions:
  https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm
- El-Yaniv and Wiener, On the Foundations of Noise-free Selective
  Classification: https://jmlr.csail.mit.edu/papers/v11/el-yaniv10a.html
- NASA NTRS, A Formal Verification Framework for Runtime Assurance:
  https://ntrs.nasa.gov/citations/20230017350
- Avizienis, The N-Version Approach to Fault-Tolerant Software:
  https://people.cs.rutgers.edu/~uli/cs673/papers/N-VersionFaultTolerant85.pdf
- NASA NTRS, Hardware and Software Fault Tolerance - A Unified Architectural
  Approach: https://ntrs.nasa.gov/citations/19890057054
- Dawid and Skene, Maximum Likelihood Estimation of Observer Error-Rates Using
  the EM Algorithm: https://doi.org/10.2307/2346806
- NIST/SEMATECH e-Handbook, Wilson confidence intervals for proportions:
  https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm
- Thompson, On the Likelihood that One Unknown Probability Exceeds Another:
  https://doi.org/10.2307/2332286
- Solar-Lezama, Program Synthesis by Sketching:
  https://www2.eecs.berkeley.edu/Pubs/TechRpts/2008/EECS-2008-176.html
- Alur et al., Syntax-Guided Synthesis:
  https://people.eecs.berkeley.edu/~sseshia/pubs/b2hd-alur-fmcad13.html
- Rubinstein, The Cross-Entropy Method for Combinatorial and Continuous
  Optimization: https://doi.org/10.1023/A:1010091220143
- Amin et al., Budgeted Prediction With Expert Advice:
  https://research.google/pubs/budgeted-prediction-with-expert-advice/
- Pan and Yang, A Survey on Transfer Learning:
  https://doi.org/10.1109/TKDE.2009.191
- Zhang et al., A Survey on Negative Transfer:
  https://arxiv.org/abs/2009.00909
- Aamodt and Plaza, Case-Based Reasoning: Foundational Issues, Methodological
  Variations, and System Approaches:
  https://journals.sagepub.com/doi/10.3233/AIC-1994-7104
- Sui et al., Safe Exploration for Optimization with Gaussian Processes:
  https://proceedings.mlr.press/v37/sui15.html
- Seung, Opper, and Sompolinsky, Query by Committee:
  https://doi.org/10.1145/130385.130417
- Mitchell, Version Spaces: A Candidate Elimination Approach to Rule Learning:
  https://www.ijcai.org/Proceedings/77-1/Papers/048.pdf
- W3C PROV Overview:
  https://www.w3.org/TR/prov-overview/
- Shapley, A Value for n-Person Games:
  https://doi.org/10.1515/9781400881970-018
- Rosenbaum and Rubin, The Central Role of the Propensity Score in
  Observational Studies for Causal Effects:
  https://doi.org/10.1093/biomet/70.1.41
- Ben-Tal and Nemirovski, Robust Convex Optimization:
  https://doi.org/10.1287/moor.23.4.769
- Guo et al., On Calibration of Modern Neural Networks:
  https://arxiv.org/abs/1706.04599
- Lei et al., Distribution-Free Predictive Inference for Regression:
  https://arxiv.org/abs/1604.04173
- Constantine, Active Subspaces: Emerging Ideas for Dimension Reduction in
  Parameter Studies: https://doi.org/10.1137/1.9781611973860
- Morris, Factorial Sampling Plans for Preliminary Computational Experiments:
  https://doi.org/10.1080/00401706.1991.10484804
- Spall, Multivariate Stochastic Approximation Using a Simultaneous
  Perturbation Gradient Approximation:
  https://doi.org/10.1109/9.119632
- Allgower and Georg, Introduction to Numerical Continuation Methods:
  https://doi.org/10.1137/1.9780898719154
- Willems and Wolper, Partial-Order Methods for Model Checking:
  https://lics.siglog.org/1996/WillemsWolper-PartialOrderMethods.html
- Flanagan and Godefroid, Dynamic Partial-Order Reduction for Model Checking
  Software: https://patricegodefroid.github.io/public_psfiles/popl2005.pdf
- Seydel, Branch Switching in Bifurcation Problems:
  https://eudml.org/doc/132842
- Henderson, Multiparameter Parallel Search Branch Switching:
  https://research.ibm.com/publications/multiparameter-parallel-search-branch-switching--1
- Zobrist, A New Hashing Method With Application for Game Playing:
  https://journals.sagepub.com/doi/10.3233/ICG-1990-13203
- Zhou and Hansen, Structured Duplicate Detection in External-Memory Graph
  Search: https://aaai.org/Papers/AAAI/2004/AAAI04-108.pdf
- ISO/IEC/IEEE 15026-2 assurance case structure and terminology:
  https://standards.iteh.ai/catalog/standards/iso/4734d411-2bff-428f-8f4a-164859f171b8/iso-iec-ieee-15026-2-2022
- OpenTelemetry Semantic Conventions:
  https://opentelemetry.io/docs/specs/semconv/
- W3C PROV-DM, provenance data model:
  https://www.w3.org/2012/10/prov-dm
- IETF RFC 9901, Selective Disclosure for JSON Web Tokens:
  https://www.ietf.org/ietf-ftp/rfc/rfc9901.html
- W3C Verifiable Credentials Data Model, data minimization:
  https://w3c.github.io/vc-data-model/#the-principle-of-data-minimization
- PostgreSQL WAL checkpoints:
  https://www.postgresql.org/docs/current/wal-configuration.html
- Microsoft Azure Architecture Center, Event Sourcing pattern:
  https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing
- Fowler, Event Sourcing:
  https://www.martinfowler.com/eaaDev/EventSourcing.html
- Shapiro et al., A comprehensive study of Convergent and Commutative
  Replicated Data Types:
  https://dsf.berkeley.edu/cs286/papers/crdt-tr2011.pdf
- Apache Kafka log compaction design:
  https://kafka.apache.org/42/design/design/#compaction
- Dor and Zwick, SOKOBAN and other motion planning problems:
  https://doi.org/10.1016/S0925-7721(99)00017-6
- Junghanns and Schaeffer, Sokoban: improving the search with relevance cuts:
  https://doi.org/10.1016/S0304-3975(00)00080-3
- Davis, Logemann, and Loveland, A machine program for theorem-proving:
  https://doi.org/10.1145/368273.368557
- Marques-Silva and Sakallah, GRASP: A Search Algorithm for Propositional
  Satisfiability: https://doi.org/10.1109/12.769433
- Gray and Reuter, Transaction Processing: Concepts and Techniques:
  https://www.sciencedirect.com/book/9781558601901/transaction-processing
- Papadimitriou, The serializability of concurrent database updates:
  https://doi.org/10.1145/322154.322158
- Eswaran et al., The notions of consistency and predicate locks in a database
  system: https://doi.org/10.1145/360363.360369
- Milner, LCF: A way of doing proofs with a machine:
  https://doi.org/10.1007/3-540-09526-8_11
- Rocq/Coq Reference Manual, Core language and kernel boundary:
  https://rocq-prover.org/doc/V8.20%2Brc1/refman/language/core/index.html
- Coq Reference Manual, proof handling and proof-term rechecking:
  https://docs.rocq-prover.org/v8.9/refman/proof-engine/proof-handling.html
- Bryant, Graph-Based Algorithms for Boolean Function Manipulation:
  https://doi.org/10.1109/TC.1986.1676819
- Kuehlmann and Krohm, Equivalence Checking Using Cuts and Heaps:
  https://research.ibm.com/publications/equivalence-checking-using-cuts-and-heaps
- OpenSMILES specification, organic subset and valence model:
  https://opensmiles.org/opensmiles.html
- RDKit Book, valence calculation and allowed valences:
  https://rdkit.org/docs/RDKit_Book.html

## Current Proof Target

The next narrow result is not "the learned model is correct." The target is:

```text
receipt-trained reversible proposer
  reduces hard-verifier calls
  while preserving held-out success
  and preserving zero invalid commits
```

The first implementation is
`examples.receipt_trained_reversible_proposer_benchmark`. It deliberately uses
local deterministic canaries so the metric is auditable before external suites
are wired in. The learning certificate now supports two evidence modes:

- the learned arm succeeds where the same-case baseline fails,
- or the learned arm preserves the same held-out success count with fewer
  hard-verifier calls.

The second mode is the important one for real systems. The learned proposer is
valuable only if it spends less verifier budget without weakening commit
authority.

## External Benchmark Anchors

The real-task path should attach adapters in this order:

- robotics: OMPL/MotionBenchMaker-style motion-planning problems with explicit
  state-validity and collision-checking receipts,
- hardware: `riscv-formal` RVFI instruction checks over open RISC-V cores,
- program repair: Defects4J active bug ids with triggering/relevant test
  receipts,
- quantum: MQT Bench and RevLib circuits checked with MQT QCEC equivalence
  receipts.

Until those adapters run, the strongest claim remains G1: the repo now has the
certificate schema, reversible proposal tokens, held-out split discipline,
same-case baseline comparison, and zero-invalid-commit gate needed to evaluate
the target. It does not yet prove real robotics safety, hardware correctness,
program repair effectiveness, or quantum compilation correctness.

## Real-Task Readiness Gate

`examples.real_task_benchmark_manifest` is the next substrate gate. It binds a
four-domain external benchmark manifest to a preflight certificate:

- required command-line tools such as `roslaunch`, `sby`, `yosys`, and
  `defects4j`,
- required Python modules such as `mqt.bench` and `mqt.qcec`,
- command templates for generating or running each external benchmark,
- train/held-out split ids for each domain,
- source URLs for every benchmark family.

The gate fails closed when the environment cannot run the real benchmarks. A
supported readiness claim would mean only that the adapters can execute; it is
not evidence for the receipt-trained proposer claim. The final proof still
needs real benchmark receipts, baseline and learned hard-verifier-call counts,
zero invalid commits, and replay/rollback audits across all four domains.

`examples.quantum_mqt_bench_adapter` is the first single-domain adapter after
the readiness gate. It uses MQT Bench as the task source and MQT QCEC as the
hard equivalence verifier when the optional packages are installed. Without
those packages it emits a rejected claim and zero receipts. Its deterministic
test backend validates adapter mechanics only; it cannot promote a quantum
benchmark-performance claim or satisfy the four-domain goal.

`examples.program_defects4j_adapter` adds the same fail-closed shape for
program repair. It uses Defects4J `checkout`, `compile`, and relevant-test
execution as the hard verifier for buggy-version versus fixed-version
candidates. This is real benchmark adapter plumbing, not a full APR result:
the current candidate surface uses known fixed versions, and future work still
needs patch-generation, patch-minimization, and held-out patch receipts before
program-repair effectiveness can be claimed.

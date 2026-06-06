# Transactional Reversible World Model

This repository implements a small, auditable kernel for the proposal in
`transactional_reversible_world_model_full_proposal.md`.

New readers should start with `docs/GETTING_STARTED.md`. It gives the current
scope, verification commands, demo path, and claim boundary without requiring
the full proposal first.

The implementation is deliberately conservative:

- proposals are projected into typed candidates before verification,
- soft scores may rank but may not commit,
- hard verifier accept is required but not sufficient,
- replay, rollback, manifest, and ledger checks gate every commit,
- all receipts are hash chained,
- tampering and stale distributed worker receipts fail closed.

The current evidence grade is `G1`: deterministic unit tests and small local
synthetic experiments. It does not claim learned-model or robotics safety.

## Run

```sh
python3 -m unittest
python3 -m trwm.demo
node --disable-warning=ExperimentalWarning scripts/build.mjs
node --disable-warning=ExperimentalWarning scripts/check-dist-fresh.mjs
node --test test-ts/*.test.mjs
python3 -m http.server 8765
```

Open `http://localhost:8765/html/` for the standalone browser demos.

## Examples

The `examples/` folder contains executable true-substrate experiments for
robotics, molecular dynamics, material lattice dynamics, and branch-history
guided exploration:

```sh
python3 -m examples.robotic_safety_envelope
python3 -m examples.molecular_dynamics_verlet
python3 -m examples.material_lattice_metropolis
python3 -m examples.ancestral_branch_exploration
python3 -m examples.analogical_branch_transfer
python3 -m examples.context_selection_transfer
python3 -m examples.context_refinement_transfer
python3 -m examples.context_query_policy_transfer
python3 -m examples.context_drift_quarantine
python3 -m examples.branch_pruning_transfer
python3 -m examples.branch_diversity_transfer
python3 -m examples.branch_composition_transfer
python3 -m examples.context_retention_transfer
python3 -m examples.branch_history_frontier
python3 -m examples.programmable_world_model_frontier
```

Each example uses transactional hard verification, receipts, replay audit, and
rollback audit. The domain examples now emit `report`, `evidence_certificate`,
and `claim_certificate` JSON; the ancestral branch example adds an
`exploration_certificate` for past-branch-guided proposal ordering; the
analogical branch example tests explicit ancestor-context reuse and misleading
ancestor rejection; the context-selection example certifies which ancestor
contexts may influence target exploration; the context-refinement example uses
a rejected target branch to refine ancestor retrieval; the context-query-policy
example applies that refined retrieval policy to held-out sibling targets
against a stale-query baseline and certifies the conflicting committed source
evidence it overrides; the context-drift example quarantines old-epoch branch
evidence before reuse; the branch-pruning example uses rejected branch receipts
to remove known-dead target candidates before verifier-budget allocation; the
branch-diversity example uses same-family rejects to force coverage of a
distinct candidate family under the same verifier budget; the
branch-composition example combines two receipt-bound past branch fragments only
as a verifier-gated target proposal; the
context-retention example retains the successful target branch as certified
future proposal evidence for a sibling target and
certifies the memory query that ranks the sibling proposals against a
same-budget static sibling baseline; the frontier example aggregates the three
physical certified domains, while the branch-history frontier aggregates the
ten branch-memory stages. See `examples/README.md` and
`docs/experiment_learnings.md`.

## Package Layout

- `trwm.core`: snapshots, typed candidates, verifier results, receipts, ledger,
  transaction engine, and audits.
- `trwm.reversible`: exact integer additive-coupling transport plus reversible
  delta/block tokens.
- `trwm.parallel`: read/write conflict scheduling, sequential/parallel replay,
  and hash-checked parallel replay certificates.
- `trwm.token_log`: bounded circular token logs that compact old reversible
  deltas into a replayable prefix block plus retained suffix.
- `trwm.branch`: sacred-commit branch runtime, branch-selection certificates,
  verifier-budget abstention, and distributed commit manager.
- `trwm.ancestral`: receipt-bound ancestral branch memory, candidate ranking
  from committed/rolled-back/rejected branch history, hash-checked memory
  snapshots, context selection/refinement certificates, and branch-retention
  certificates for audited memory updates plus influence certificates for
  snapshot-bound proposal ordering.
- `trwm.budget_policy`: receipt-trained verifier-budget planning with exact
  integer-cost subset selection and hash-checked policy snapshots.
- `trwm.checkpoint`: replay checkpoint certificates for compacting audited
  receipt prefixes while preserving suffix replay authority.
- `trwm.claims`: hash-checked claim certificates that bind requirements,
  benchmark metrics, evidence grade, and claim boundary.
- `trwm.evaluation`: trace-disjoint learning-evaluation certificates that bind
  train receipts, held-out evaluation receipts, same-case baselines, learner
  snapshots, and exact verifier-call gain ratios.
- `trwm.transfer`: transfer-evaluation certificates that bind source domains,
  held-out target receipts, same-case target baselines, and negative-transfer
  conclusions before any positive transfer claim can be promoted, plus
  transfer-guard snapshots that admit source evidence only after validated
  positive-transfer certificates.
- `trwm.learning`: receipt-derived rankers, counterfactual rollback ranking,
  and hyperdimensional receipt memory.
- `trwm.macro`: prefix-safe macro transactions and macro-memory ranking.
- `trwm.memory`: bounded macro-memory consolidation, deterministic eviction,
  and hash-checked memory snapshots.
- `trwm.preflight`: dependency-free shape-rank preflight for deciding whether
  compact reversible adapters or macro memory are plausible before training.
- `trwm.projection`: typed projection contracts, projection manifests, field
  hashes, and fail-closed coverage audits for verifier inputs.
- `trwm.repair`: residual-driven typed program repair primitives.
- `trwm.redaction`: redacted receipt views, salted path commitments,
  selective-disclosure checks, and audit-handle validation.
- `trwm.reliability`: receipt-trained verifier reliability rows, Wilson lower
  bounds, audit-priority ranking, and hash-checked reliability snapshots.
- `trwm.residuals`: cross-domain residual envelopes, normalized learning
  hashes, taxonomy memory, and signal-hash validation.
- `trwm.topk`: residual-aware top-k repair candidate submission under scarce
  verifier-call budgets.
- `trwm.rrlm`: reversible receipt-learned macro proposer, hash-checked RRLM
  snapshots, proposal certificates, transport certificates, plus matched
  non-reversible baseline.
- `trwm.sdk`: programmable multi-domain substrate with domain registration,
  per-domain ledgers, replay/rollback audits, SDK domain manifests,
  receipt-trained routing, optional verifier-cost-aware domain routing, and
  transfer-guarded route certificates.
- `trwm.verifier_guard`: independent audit-verifier agreement wrapper that
  turns primary-verifier disagreements into non-committing residual receipts.
- `trwm.world`: generic proposer/projector/hard-verifier transaction runtime
  with hash-checked world-model step certificates, learner snapshots,
  learner-update certificates, learner-delta certificates, learner-lineage
  certificates, learner-merge certificates, and receipt learner updates.
- `trwm.world_program`: programmable world-model manifests, execution
  certificates, admission policies/certificates, and evidence bundles that
  bind component identities, schemas, dependencies, step certificate hashes,
  receipt hashes, learner snapshot, ledger head, replay/rollback audit rate,
  artifact hash groups, explicit policy requirements, bundle verification, and
  replay packages/certificates that validate trace, candidate, receipt,
  step-certificate, learner-update, and learner-delta bodies before claim
  promotion.
- `trwm.experiments.game_of_life`: typed hard-checker predecessor search.
- `trwm.experiments.sokoban`: reverse Sokoban pull search with forward push
  certificate verification.
- `trwm.experiments.sat_csp`: small CNF-SAT/CSP hard-checker with
  unsatisfied-clause residual repair.
- `trwm.experiments.operations`: inventory reservation transactions with
  accounting-invariant checks and stock-shortage residual repair.
- `trwm.experiments.proof_kernel`: Horn-rule proof scripts checked by a small
  proof kernel with residual-guided script repair.
- `trwm.experiments.circuit_repair`: combinational Boolean netlist repair with
  exhaustive truth-table verification and single-gate residual repair.
- `trwm.experiments.molecule_repair`: organic-subset molecular graph repair
  with valence/formula checking and atom/bond residual repair.
- `trwm.experiments.code_repair`: bounded unit-test-guided code patch repair
  over a tiny expression grammar with file-hash checks and operator residuals.
- `trwm.experiments.robotics`: 2D point-robot trajectory-tube checking with
  exact segment-circle clearance, speed bounds, and shield residual repair.
- `trwm.experiments.chess_ancestry`: bounded king/rook last-move ancestry
  reconstruction with legal-move replay and ambiguity entropy.
- `trwm.experiments.checkpoint_compaction`: checkpoint benchmark that replaces
  an audited receipt prefix with a replayable state certificate plus suffix.
- `trwm.experiments.parallel_replay`: read/write token benchmark proving
  conflict-free batch replay reaches the same state hash as sequential replay.
- `trwm.experiments.circular_token_log`: circular-log benchmark proving compacted
  prefix replay plus bounded suffix replay equals full token replay.
- `trwm.experiments.branch_selection`: branch-selection certificate benchmark
  proving the selected committed branch is an accepted hard-filter survivor and
  accepted non-winners are rolled back.
- `trwm.experiments.counterfactual_learning`: branch loser rollback benchmark
  for learning from accepted-but-uncommitted counterfactual receipts.
- `trwm.experiments.projection_contract`: projection-coverage guard benchmark
  that rejects safety-critical field omissions before hard verification can be
  fooled by a partial typed view.
- `trwm.experiments.verifier_cost`: cost-normalized routing benchmark for
  ranking successful domains by committed successes per verifier-cost unit.
- `trwm.experiments.verifier_budget`: branch-runtime benchmark for verifier
  compute budgets, abstain receipts, and exact spent-cost accounting.
- `trwm.experiments.budget_policy`: receipt-trained verifier-budget benchmark
  that plans a cost-bounded hard-verifier subset from success lower bounds.
- `trwm.experiments.claim_audit`: promotion-checklist benchmark that supports a
  bounded G1 claim certificate and rejects an RRLM mechanism-lift overclaim.
- `trwm.experiments.learning_evaluation`: learning-evaluation certificate
  benchmark proving a budget-policy learning claim has disjoint train/eval
  receipts, a same-budget baseline, hard-commit-only evidence, and exact
  verifier-call accounting.
- `trwm.experiments.transfer_audit`: transfer-audit benchmark proving a
  source-only receipt policy can be rejected as a positive cross-domain
  transfer claim when the same-case target baseline wins.
- `trwm.experiments.transfer_guard`: transfer-guard benchmark proving a
  negative-transfer certificate blocks source-policy reuse and falls back to a
  target-local baseline before execution.
- `trwm.experiments.verifier_guard`: branch-width benchmark where an
  independent audit verifier blocks a primary inventory-verifier false
  positive before commit.
- `trwm.experiments.reliability_audit`: receipt-trained audit-priority
  benchmark that sends scarce audit budget toward primaries with observed false
  positives.
- `trwm.experiments.redacted_receipt`: receipt-privacy benchmark that redacts
  replay/rollback-sensitive fields while preserving the original receipt hash.
- `trwm.experiments.residual_taxonomy`: residual-schema benchmark that
  normalizes real resource, coverage, and budget residual receipts.
- `trwm.experiments.residual_topk`: residual top-k benchmark that ranks repair
  candidates from learned residual hints before spending verifier calls.
- `trwm.experiments.distributed_counter`: Phase 8 deterministic distributed
  worker benchmark against the local canonical branch result.
- `trwm.experiments.hdc_memory`: Phase 7 HDC receipt-memory benchmark with
  no-memory and exact-match baselines plus noise/tamper probes.
- `trwm.experiments.shape_simulator`: shape-conditionality simulator with
  same-case baselines.
- `trwm.experiments.repair_simulator`: residual repair benchmark with
  same-case static baseline.
- `trwm.experiments.macro_grid`: prefix-safe macro benchmark with macro-memory
  reuse.
- `trwm.experiments.memory_consolidation`: bounded macro-memory benchmark that
  merges duplicate safe receipts, retains strong negative prefix evidence, and
  forgets weak stale rows.
- `trwm.experiments.rrlm_macro`: Phase 5 reversible proposal-field benchmark
  with exact cycle canary, RRLM proposal/transport certificates, and matched
  non-reversible receipt ranker.
- `trwm.experiments.sdk_multi_domain`: Phase 9 SDK benchmark proving one
  transaction kernel across scalar repair, Game of Life, grid macro, Sokoban
  reverse-planning, operations, proof-kernel, circuit, molecule, code-patch,
  robot-trajectory, and chess-ancestry domains.
- `trwm.experiments.sdk_manifest`: SDK manifest benchmark proving registered
  domain verifier IDs, schema surfaces, receipt counts, ledger heads, and audit
  status are hash checked.
- `trwm.experiments.sdk_transfer_guard`: SDK transfer-admission benchmark
  proving a negative-transfer certificate can reorder proposal domains before
  target execution.
- `trwm.experiments.world_loop`: transactional world-model loop benchmark
  proving a rejected residual can train the next proposal while the hard
  verifier still owns the only committed transition and disjoint learner
  snapshots merge only under a validated evidence certificate; it also runs an
  RRLM-backed proposal lane whose snapshot, proposal-certificate, and
  transport-certificate hashes are bound into typed candidate and receipt
  artifact hashes, then wrapped in a world-program manifest/certificate that
  audits the whole executed proposer/projector/learner/verifier stack and a
  policy admission certificate that proves the execution matched the expected
  program, components, schemas, dependencies, artifacts, and safety counters.
- `src/`: TypeScript browser library source.
- `dist/`: generated ESM build imported by the HTML demos.
- `html/`: standalone demos for reversible coupling, transaction ledgers,
  Game of Life predecessor search, Sokoban reverse certificates, SAT/CSP
  residual repair, operations transaction repair, formal proof-kernel repair,
  circuit netlist repair, molecule graph repair, code patch repair,
  robot trajectory shielding, chess ancestry reconstruction,
  parallel replay certificates, branch selection certificates,
  circular token-log compaction,
  counterfactual rollback learning, projection contract guarding,
  verifier cost routing, verifier budget abstention, receipt budget policy,
  claim evidence audit, verifier agreement guarding, reliability audit memory, residual top-k submission,
  residual taxonomy,
  SDK domain manifests, SDK transfer guard routes, transactional world loop, learning evaluation certificates, transfer audit certificates, transfer guard snapshots, redacted receipt disclosure, checkpoint compaction, memory consolidation,
  shape-conditional receipt learning, residual program repair, prefix-safe macro
  search, and RRLM proposal ranking.

## Evidence Boundary

Python receipts use `trwm.receipt.v1`; browser receipts use
`trwm.browser.receipt.v1`. They share the same transaction semantics but are not
cross-runtime portable ledger rows. The browser build also includes receipt
ranking and hyperdimensional memory, but those are proposal/ranking layers only;
hard verifier results still own every commit.

The WebGPU affine coupling path is admitted only when inputs, parameters,
intermediate increments, and outputs are all inside signed i32 bounds. If a
browser exposes `navigator.gpu` but no adapter, the demo reports that and falls
back to the exact CPU path.

The shape-conditionality browser demo reports same-case calls-per-success for
static search, receipt-count ranking, and HDC receipt memory. It is a synthetic
G1 verifier-call experiment; it is not evidence of learned-model or public
benchmark lift.

The shape-rank preflight computes cumulative output-visible energy from target
updates and a declared output map. It reports `r90`, `energy_at_budget`, and
whether a compact rank budget fits before running receipt learning.

The Sokoban reverse demo is a G1 state-forensics canary: reverse-pull search
proposes a predecessor and a push certificate, but the hard verifier replays
classic push-only Sokoban reachability forward before any commit. It does not
claim a competitive Sokoban solver or deadlock-learning result.

The chess ancestry benchmark is a G1 state-forensics canary: candidates are
king/rook-only last-move certificates, the hard verifier checks same-color
occupancy, rook path blocking, side-to-move, king attack constraints, and
forward replay to the target board, then reports legal history count and
ambiguity entropy. It does not implement pawns, castling, en passant,
checkmate/stalemate, move counters, opening legality, or a competitive chess
engine.

The counterfactual rollback benchmark is a G1 trace-learning canary: branch
runtime evaluates multiple hard-accepted candidates, commits the lowest-cost
winner, records other accepted candidates as `rolled_back_loser`, and trains a
ranker that treats those losers differently from committed winners. It is not
counterfactual regret minimization, reinforcement learning, policy optimality,
or a claim about unobserved outcomes.

The projection contract benchmark is a G1 typed-projection safety canary:
projection manifests list covered verifier fields and hash their source values.
The guard rejects a partial stop-command projection that omits
`safety_clearance`, even though an unguarded stopping-distance verifier would
accept the same partial view by treating missing clearance as zero. Complete
typed projections still require exact integer safety verification and
replay/rollback before commit. This is not a general schema language,
information-flow proof, perception guarantee, or defense against an unsound
domain verifier.

The verifier-cost benchmark is a G1 routing-accounting canary: two domains each
produce one committed success, but one verifier reports cost `12` and the other
reports cost `3`. The uniform receipt router ties on success count and keeps
registration order; the cost-aware router ranks by the exact ratios `1/12` and
`1/3`, so it selects the cheaper equally successful domain. The router remains
proposal/scheduling policy only and cannot bypass hard verifier commits.

The verifier-budget benchmark is a G1 compute-budget canary: the branch runtime
receives three candidates under budget `4`, records a zero-spend
`hard_abstain` receipt for an accepted branch that would require verifier cost
`7`, pays cost `2` for one rejected branch, pays cost `2` for one accepted
branch, and commits only the verified accepted branch. It is not a budgeted
bandit policy or selective-classification benchmark; it is the transaction
semantics needed before such policies can be trusted.

The receipt budget-policy benchmark is a G1 learned scheduling canary: three
training receipts give `quantity-5` one verified success and `quantity-8` and
`quantity-7` one failure each. Under budget `3`, cheap-first scheduling submits
the two cost-1 failures and does not commit. The receipt-trained planner uses
the Wilson lower bound `0.206543291474`, selects the exact cost-3
`quantity-5` repair, commits in one hard-verifier call, validates its snapshot,
and detects snapshot tampering. This is not UCB, Thompson sampling, regret
optimization, or permission to skip hard verification.

The learning-evaluation certificate benchmark is a G1 claim-promotion canary:
the same budget-policy setting emits a `trwm.learning_evaluation_certificate.v1`
artifact that binds the learner snapshot hash, three training receipt hashes,
one held-out learned-policy evaluation receipt hash, and a same-budget
cheap-first baseline. The certificate records the exact verifier-call gain as
`2/1`, validates hard-commit-only evidence, detects train/eval overlap, and is
now required by the claim-audit benchmark before the bounded learning claim is
supported. This is not a public benchmark protocol, statistical significance
test, or proof of generalization beyond the local deterministic canary.

The transfer-audit certificate benchmark is a G1 negative-transfer canary:
a source inventory receipt trains a source-only policy to prefer `quantity-5`,
but the held-out target inventory has only two available units. Under the same
one-call budget, the source-only transfer attempt is rejected with
`stock_shortage`, while the target-local baseline commits `quantity-2`. The
certificate binds source/target domains, source and target receipt hashes,
same-case target baseline metrics, hard-commit-only evidence, and the
conclusion `negative_transfer`. This follows the transfer-learning warning
that source knowledge can harm target performance; it is not a general
domain-adaptation benchmark or evidence of broad cross-domain transfer.

The transfer-guard benchmark is a G1 admission-memory canary: the validated
negative-transfer certificate is stored in `trwm.transfer_guard_snapshot.v1`
memory, the source policy decision is rejected with
`negative_transfer_certificate`, an unguarded future reuse of `quantity-5`
fails with `stock_shortage`, and the guarded path falls back to the target-local
`quantity-2` baseline and commits. The guard schedules or blocks proposal reuse
only; it cannot commit and does not replace target hard verification.

The claim-audit benchmark is a G1 evidence-governance canary: a supported
certificate binds selected learning-canary metrics to explicit requirements
for zero invalid commits, ledger audit, replay/rollback, trace-disjoint
evaluation, same-case baselines, verifier-call accounting, learning-evaluation
certificate support, transfer-overclaim rejection, transfer-guard blocking,
RRLM proposal-certificate validation, RRLM transport-certificate validation,
learner-update validation, learner-delta validation, learner-lineage
validation, learner-merge validation, partial-overlap learner-merge
validation, RRLM-backed world-loop proposal-certificate validation,
world-program certificate validation, world-program admission policy
validation, world-program evidence-bundle verification, world-program replay
verification, mechanism ablation, null-result reporting, and claim boundary. A
second certificate rejects the
overclaim that RRLM reversibility alone beats the matched non-reversible
receipt ranker because the measured gain is exactly `1.0`. Certificate hashes
validate and metric tampering is detected. This is an assurance-case-shaped
audit artifact, not an external safety case, public benchmark proof, or signed
third-party attestation.

The parallel replay benchmark is a G1 replay-scheduling canary: six reversible
delta tokens over keys `a`, `b`, `c`, and `d` are partitioned into two
read/write conflict-free batches, `0,1,3,5` and `2,4`. Sequential replay and
batch replay reach the same state `{"a":3,"b":5,"c":4,"d":6}`, inverse
roundtrip returns to the seed state, certificate hashes validate, tampering is
detected, and 64 deterministic randomized read/write trials report zero
mismatches. This uses conservative conflict conditions over declared read/write
sets; it is not a concurrent database, isolation-level implementation,
lock manager, consensus protocol, or distributed durability claim.

The circular token-log benchmark is a G1 bounded-replay canary: eight reversible
delta tokens are stored with suffix capacity `3`. The first five tokens compact
to two prefix deltas, `b:0->2` and `c:0->4`, while the suffix ring retains
`b:2->5`, `d:0->6`, and `a:0->7`. Full replay and compacted replay both reach
`{"a":7,"b":5,"c":4,"d":6}`, inverse replay returns to the seed state,
certificate hashes validate, tampering is detected, and 64 deterministic
randomized trials report zero mismatches. This borrows event-sourcing snapshot
and log-compaction ideas, but it is only a local reversible-token replay
certificate, not a durable event store, message broker, database log, or Kafka
topic implementation.

The branch-selection certificate benchmark is a G1 runtime-assurance canary:
three branches include a rejected branch with a deliberately attractive soft
rank, an accepted loser, and an accepted winner. The certificate records
accepted indices `(1, 2)`, rejected index `(0)`, selected and committed index
`2`, loser index `(1)`, valid receipt hashes, and tamper detection. This proves
the local receipt set obeyed rank-after-hard-filter and loser rollback. It does
not prove a ranker is optimal, a verifier is complete, or a distributed
consensus protocol is implemented.

The verifier-agreement guard benchmark is a G1 false-positive canary: a flawed
primary inventory verifier accepts `unsafe-large`, which drives stock from `5`
to `-3` while the unguarded ledger still audits because the flawed verifier
authorized the receipt. Wrapping that primary with an independent audit verifier
records the unsafe branch as `verifier_false_positive` with audit residual
`stock_shortage`, then commits `safe-small` to stock `2`. This is not a proof
that two verifiers are independent or complete; shared specification bugs,
collusion, or an unsound audit verifier remain outside the claim.

The reliability-audit benchmark is a G1 audit-priority learning canary: six
verifier-agreement receipts train reliability rows for a strict primary and a
flawed primary. The flawed primary has one audited success and two audited
false positives, giving Wilson lower bound `0.061490315276`; the strict primary
has three audited successes and zero failures, giving lower bound
`0.438493919551`. With audit budget `1`, reliability ranking audits
`flawed_inventory_primary` first and detects a future `stock_shortage` false
positive, while a naive strict-first audit does not. This ranks scarce audit
attention only; it does not let reliability memory commit, skip required hard
verification, or prove verifier independence.

The residual taxonomy benchmark is a G1 residual-standardization canary: it
wraps three real receipt residuals, `stock_shortage`,
`projection_contract_violation`, and `verifier_budget_exhausted`, into
`trwm.residual.v1` envelopes with resource, coverage, and budget categories.
The raw residual hash remains part of the audit signal, while a separate
learning hash lets snake/camel variants normalize to the same training feature.
It is not an ontology-complete error language or automatic repair synthesis.

The residual top-k benchmark is a G1 verifier-call scheduling canary: a
stock-shortage receipt teaches `quantity=5` as the top repair hint. Under the
same top-k limit `2`, unranked submission spends both verifier calls on
`quantity-8` and `quantity-7` and fails to commit; residual-ranked submission
tries `quantity-5` first, commits after one hard-verifier call, audits cleanly,
and rolls back to the seed state. This is not a general CEGIS/SyGuS/CEM
algorithm or a proof of optimal repair ranking; it is a transaction-safe
submitter for spending scarce verifier calls on learned repair candidates.

The redacted receipt benchmark is a G1 privacy/audit canary: a committed
inventory receipt is converted into `trwm.redacted_receipt.v1` by replacing
selected replay/rollback fields with salted path commitments. The original
receipt hash, commit decision, hard-verifier result, policy hash, and
redacted-view hash remain visible and tamper-checked. A holder can selectively
prove one redacted path with the original value and salt, while wrong
disclosures fail. The redacted view is deliberately not replay authority and is
not a signed SD-JWT, VC, zero-knowledge proof, unlinkability guarantee, or
privacy law compliance claim.

The checkpoint compaction benchmark is a G1 replay-compression canary: an
audited inventory ledger with six receipts and four committed transitions is
split after the first three rows. The prefix becomes a `trwm.checkpoint.v1`
certificate containing the prefix receipt hashes, checkpoint head, checkpoint
state, state hash, adapter identity, and certificate hash. Replaying from that
checkpoint uses only the suffix committed receipts, saves two prefix replay
calls, reaches the same final state hash and ledger head, rejects checkpoint
state tampering, and rejects stale suffix parent heads. It is not a consensus
checkpoint, external signature, public proof that missing receipt bodies were
valid, or a replacement for retaining full evidence when third-party audit is
required.

The SAT/CSP benchmark is a G1 residual-learning canary: CNF assignments are
typed candidates, the hard verifier returns unsatisfied clauses, and the repair
proposer flips one residual-indicated variable at a time. It is not a DPLL,
CDCL, or competitive SAT solver claim.

The operations benchmark is a G1 database-style transaction canary: inventory
reservation candidates carry explicit stock/reserved deltas, and the hard
verifier checks duplicate orders, stock sufficiency, exact diff shape, and
accounting conservation. It is not a concurrent database, isolation, or
durability implementation.

The formal proof-kernel benchmark is a G1 theorem-proving canary: proof scripts
are typed Horn-rule sequences, residuals suggest the next applicable rule, and
the hard verifier checks every premise before a theorem receipt can commit. It
is not a general proof assistant, dependent type checker, tactic language, or
claim about mathematical discovery.

The circuit repair benchmark is a G1 hardware-verification canary: candidates
are small acyclic Boolean netlists over exact 4-bit binary operator masks, the
hard verifier compares the complete combinational truth table, and residuals
may suggest one mutable gate replacement. It is not a scalable equivalence
checker, SAT/BDD engine, HDL compiler, timing model, or sequential-circuit
verification claim.

The molecule repair benchmark is a G1 chemistry-graph canary: candidates are
small organic-subset molecular graphs over C, N, O, F, and Cl with explicit
single/double/triple bonds, implicit hydrogens from normal valence, and exact
formula checks. It is not a SMILES parser, RDKit replacement, force-field model,
aromaticity model, stereochemistry engine, synthesis planner, or molecular
design claim.

The code repair benchmark is a G1 unit-test-guided patch canary: candidates
carry a base file hash, one mutable operator patch, and a canonical rendered
source string for a tiny integer expression grammar. The hard verifier evaluates
the full supplied test suite and residuals can identify the unique operator that
satisfies those tests. It is not arbitrary code execution, whole-repository
repair, semantic correctness beyond the tests, security analysis, or LLM
code-generation evidence.

The robot trajectory benchmark is a G1 robotics safety-shield canary:
candidates are canonical 2D waypoint corridors for a point robot in a unit
square. The hard verifier checks exact segment-circle clearance against
inflated circular obstacles and checks max-step speed bounds; residual repair
may replace an unsafe direct chunk with a verified detour from the same bounded
action set. It is not MuJoCo fidelity, robot hardware safety, uncertainty
handling, dynamics, contacts, or a general motion planner.

The HDC memory benchmark reports verifier-call efficiency under context shift:
no-memory static ordering and exact full-context matching are compared against
HDC retrieval by partial receipt context. It also checks noisy-query retrieval,
ledger tamper detection, and invalid commits equal to zero.

The residual program repair demo reports same-case calls-per-success for static
integer-program search versus verifier-residual repair. The repairer proposes
typed patches only; repaired programs still require hard verifier acceptance
before commit.

The macro-grid demo reports terminal hard-verifier calls avoided by prefix
safety, plus macro-attempt reduction after receipt-grounded macro memory ranks a
previously accepted macro ahead of an unsafe prefix.

The memory-consolidation benchmark is a G1 bounded-learning canary: ten macro
receipts are merged into a capacity-two memory for one context. Duplicate safe
macro receipts merge into one positive row, repeated unsafe-prefix receipts
merge into one negative row, weak stale terminal/prefix rows are evicted, and a
hash-checked snapshot records the retained evidence. The resulting rank places
the safe macro first and the unsafe macro last, while hard verifiers still own
every commit. It is not a learned embedding memory, optimal replay buffer,
continual-learning result, or proof that this eviction rule is globally best.

The RRLM macro demo reports reversible-only, matched non-reversible, and
reversible receipt-learned proposal ordering on the same prefix-safe grid task.
Current G1 results show receipt learning reduces macro attempts, while RRLM and
the matched non-reversible receipt ranker tie on this toy metric. Therefore the
demo does not claim reversible mechanism lift; it verifies exact reversible
transport, hash-checked `trwm.rrlm_macro_snapshot.v1` and
`trwm.rrlm_proposal_certificate.v1` artifacts, a
`trwm.rrlm_transport_certificate.v1` artifact that recomputes forward/inverse
cycles plus signed-i32 WebGPU admission, hard-verifier authority, ledger audit,
and invalid commits equal to zero.

The multi-domain SDK benchmark registers scalar-program repair, Game of Life,
grid-macro, Sokoban reverse-planning, operations, proof-kernel, circuit,
molecule, code-patch, robot-trajectory, and chess-ancestry adapters in the same
programmable substrate. Each domain keeps a separate hash-chained ledger, the
SDK audits replay and rollback per domain, and the receipt router may rank
domains but cannot bypass domain hard verifiers.

The SDK manifest benchmark is a G1 programmable-substrate canary: scalar and
Life domains publish `trwm.sdk_domain_manifest.v1` manifests binding adapter
type, verifier ID/version, candidate type, projection schema, model versions,
receipt hashes, ledger head, verifier-call count, verifier-cost fallback units,
and zero invalid commits. Manifest hashes validate, live-runtime audits pass,
and tampering with a verifier ID is detected. This follows provenance ideas for
identifying entities, activities, processing steps, versions, and derivations,
but it is not a package manager, plugin sandbox, remote attestation, or
cross-runtime ABI contract.

The SDK transfer-guard route benchmark is a G1 admission-routing canary: a
receipt router first ranks `source_policy` above `target_policy`, then a
validated negative-transfer certificate produces a
`trwm.transfer_guarded_domain_route.v1` artifact that blocks the source policy
and moves `target_policy` first. Unguarded target execution of `quantity-5`
fails with `stock_shortage`; guarded execution selects `quantity-2` and commits
through the target hard verifier. This is SDK proposal routing, not evidence of
broad transfer learning or permission to bypass target verification.

The transactional world-loop benchmark is a G1 runtime-learning canary: one
generic runtime step calls a proposer, projector, transaction engine, and
receipt learner, then emits a `trwm.world_model_step_certificate.v1` binding the
component versions, receipt hash, pre/post/rollback state hashes, verifier
identity, ledger head, learner update count, and current learner snapshot hash.
The corresponding `trwm.world_learner_update_certificate.v1` artifact binds
the source receipt hash to the pre-update learner snapshot, post-update learner
snapshot hashes, update counts, and learned-state hash transition. The
`trwm.world_learner_delta_certificate.v1` artifact stores a deterministic
learner-state patch and proves replay from the pre-update learner state to the
post-update learner state. The
`trwm.world_learner_snapshot.v1` artifact records the learner state and the
receipt hashes that trained it. The
`trwm.world_learner_lineage_certificate.v1` artifact binds the ordered update
certificate hashes from the initial learner snapshot to the final learner
snapshot, making the learner's event-sourced history auditable before claim
promotion or merging. The first scalar proposal is hard-rejected with a
residual, the learner stores that residual repair, and the second proposal
commits only after hard acceptance plus replay/rollback checks.
The same benchmark includes an RRLM-backed scalar proposal lane: the first RRLM
macro `set0` is hard-rejected, that receipt penalizes the macro in the RRLM
snapshot, the next proposal certificate ranks `set0-add-target` first, and the
repaired candidate commits only through the hard verifier. The typed candidate
and receipt artifacts bind the RRLM snapshot, proposal-certificate, and
transport-certificate hashes, and a recomputed-score tamper probe fails
validation.
The RRLM lane is wrapped by a world-program manifest, execution certificate,
admission certificate, evidence bundle, bundle verification certificate, replay
package, and replay verification certificate.
The admission policy pins the expected program, component IDs, schemas,
dependencies, RRLM artifact keys, commit/reject counts, zero-invalid-commit
bound, and replay/rollback threshold; a missing-artifact policy probe is
rejected as an auditable certificate. The bundle packages the manifest,
execution certificate, admission policy, admission certificate, step hashes,
receipt hashes, final learner snapshot hash, and artifact groups into a single
hash-checked handoff artifact. The replay package adds the actual step bodies
and fails closed if recomputed trace/candidate hashes, receipt bodies,
learner-update certificates, learner-delta replay, or ledger-head recomputation
disagree with that handoff artifact.
The `trwm.world_learner_merge_certificate.v1` artifact adds a conservative
merge boundary for the learnable substrate: exact duplicate or subset snapshots
are idempotent, trace-disjoint snapshots join counter-like evidence and equal
learned repairs deterministically, partial-overlap snapshots merge only when a
base learner snapshot plus per-receipt learner-delta certificates replay both
branches from a common prefix, and conflicting learned repairs fail closed.
This proves a local auditable proposal-learning and learner-merge loop shape;
it is not learned-model lift, policy optimality, or evidence that residual
repair generalizes across domains.

The distributed counter benchmark compares local branch execution with
distributed worker receipts under deterministic seeds. The distributed commit
manager uses the same ranker as the local branch runtime, rejects stale parent
heads, records rejected workers and rolled-back losers, and audits replay and
rollback after commit.

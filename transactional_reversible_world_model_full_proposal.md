# Transactional Reversible World Models

## A full mathematical and algorithmic proposal for a multidimensional learnable state substrate

**Date:** 2026-06-06  
**Status:** Research proposal with formalized primitives, algorithms, evidence boundaries, and falsification plan

---

## Abstract

This proposal formalizes a research direction that emerged from a sequence of experiments on reversible state accounting, reversible latent dynamics, certified neural memory, verifier-gated transaction systems, and robotics/world-model execution loops. The central claim is that a useful world model should not merely predict future observations. It should maintain a multidimensional state substrate in which candidate futures are proposed, projected into typed checkable objects, verified by hard authorities, committed or rolled back with receipts, and then used as training data for better proposal, ranking, repair, and routing policies.

The resulting object is a **Transactional Reversible World Model**, abbreviated **TRWM**:

```text
reversible latent transport
+ typed projection
+ branch/macro search
+ hard verifier selection
+ ledgered commit/rollback
+ trace learning
+ distributed execution
= transactional reversible world model
```

The proposal deliberately separates four roles that many AI systems entangle:

1. **Transport:** learned reversible or replayable latent dynamics move state through possible futures and pasts.
2. **Grounding:** typed projection maps latent proposals into checkable objects.
3. **Authority:** hard verifiers decide what may be committed.
4. **Memory:** receipts and ledgers preserve enough information to replay, audit, roll back, and learn.

The critical correction is that **reversibility alone is not a solver**. A pure reversible map can transport and replay information, but it cannot by itself create an absorbing solution basin without external selection or visible-state contraction. Solver behavior requires hard verification, typed projection, branch deletion, external stopping, or ledgered entropy export. The ledger is therefore not bookkeeping; it is the mechanism that allows irreversible visible progress while preserving recoverability in the augmented state.

The proposal defines the mathematical substrate, gives core theorems, specifies algorithms, gives an evaluation protocol, and outlines a path toward a general SDK for code, proof, robotics, simulation, circuits, molecules, operations, and scientific search.

---

## 1. Motivation

Most deployed machine learning systems are forward predictors. Given an input, they produce a distribution over outputs. This is powerful, but it is structurally weak for autonomous systems that must act, recover, audit, and improve:

```text
input -> hidden activations -> output
```

This pipeline has no native notion of:

- reversible state evolution,
- legal histories of a state,
- branch-local speculative execution,
- exact rollback,
- typed commit authority,
- verifier-call accounting,
- receipt-grounded learning,
- or causal provenance.

World models improve this by learning dynamics:

```text
state, action -> next state
```

But a predictive world model is still incomplete. It can hallucinate plausible futures, drift out of distribution, or rank unsafe futures highly. It needs a transaction layer.

A transactional world model asks a stronger question:

```text
Which proposed state transition can be verified, committed, audited, reversed, and learned from?
```

The architecture in this report treats intelligence as **state evolution under constraints**, not as unconstrained generation. The primitive operation is not "produce an answer." The primitive is:

```text
propose a transition -> verify it -> commit or roll back -> record receipt -> learn from the trace
```

This makes the world model closer to a **distributed operating system for state evolution** than to a single neural network.

---

## 2. Research lineage and synthesis

The current proposal synthesizes several research streams.

### 2.1 Reversible state accounting

The first stream established a reversible state substrate: state transitions can be represented as explicit tokens with read sets, write lists, inverse operations, and block composition. This gives the basis for deterministic replay, commutativity checks, bounded logs, compaction, and parallel reconstruction.

The key lesson:

```text
Every state transition should be a first-class object.
```

A transition is not merely an update to a dictionary or tensor. It is a token with:

```text
primitive operation
arguments
read set
ordered write list
inverse
receipt
```

This makes state evolution auditable and invertible at the symbolic/runtime layer.

### 2.2 Reversible learned latent dynamics

The second stream established learned reversible dynamics through additive coupling. A hidden state is split into two halves. Each half is updated using a function of the other half, and the inverse subtracts the same deterministic increment. The update functions may be arbitrary neural networks; they do not need to be invertible individually.

This provides a learned proposal field:

```text
z_t -> z_{t+1}
```

with an inverse:

```text
z_{t+1} -> z_t
```

The key lesson:

```text
A learned model can act as a reversible state transport operator.
```

This is useful for counterfactual reasoning, bidirectional planning, auditability, reversible simulation, and repair.

### 2.3 Geometric reversible world models

The third stream framed world models as controlled latent dynamical systems:

```text
x_t -> encode -> z_t
z_{t+1} = F(z_t, a_t)
z_{t+1} -> decode -> x_{t+1}
```

When `F` is invertible for each action, the world model can run forward and backward in latent space. This enables history reconstruction, backward planning, counterfactual rollback, and state estimation.

The key lesson:

```text
A world model should not only imagine futures; it should reconstruct possible pasts.
```

### 2.4 Certified memory and shape conditionality

The fourth stream studied neural memory, transaction admission, quantization, typed operators, and the conditions under which reversible iteration helps.

The central finding is the **shape-conditionality law**:

```text
Reversible/certified substrates are most useful on low-rank, repair-structured, slot-structured, typed-operation tasks.
They are weak or decorative on high-rank unstructured tasks.
```

This prevents overgeneralization. The substrate is not a universal improvement for all tasks. It is a mechanism with a domain of advantage.

The key lesson:

```text
The right benchmark is not clean next-token prediction. The right benchmark is structured repair under verification.
```

### 2.5 Transaction machines and hard verifier authority

The fifth stream introduced the core correction: learned reversible maps are proposal fields, not authorities. A hard verifier must own commits.

This produces the transaction machine abstraction:

```text
reversible proposal dynamics
+ stochastic branch search
+ typed projection
+ hard verifier selection
+ rollback receipts
+ hash-chain ledger
```

The key lesson:

```text
A branch is cheap. A commit is sacred.
```

### 2.6 Robotics and embodied verifier-committed execution

The sixth stream moved the idea into embodied loops. A simulator or robot environment receives candidate action chunks. A safety verifier rejects unsafe chunks. The commit layer executes accepted chunks one at a time. The ledger records predicted state, actual state, verifier result, and postcheck result.

The key lesson:

```text
A world model becomes operationally meaningful when its proposals are mediated by a commit ledger and hard safety checks.
```

---

## 3. Relation to broader world-model research

The broader world-model literature already demonstrates powerful learned dynamics. Ha and Schmidhuber's World Models trained compressed spatial/temporal representations and compact controllers inside learned rollouts. DreamerV3 learns environment models and improves behavior by imagining future scenarios, reporting broad task coverage under a single configuration. TD-MPC2 performs local trajectory optimization in the latent space of a learned implicit world model. JEPA-style approaches predict in representation space rather than reconstructing every pixel. Genie-style generative world models learn action-controllable interactive environments from video.

The TRWM proposal is complementary to these. Its contribution is not another dynamics model alone. Its contribution is a transaction layer around world models:

```text
prediction becomes proposal
latent state becomes reversible transport
projection makes proposals checkable
hard verification supplies authority
ledger receipts preserve audit and rollback
trace learning improves future proposals
```

A conventional world model optimizes predictive accuracy. TRWM additionally optimizes:

```text
success_per_hard_verifier_call
invalid_commit_count
rollback_replay_rate
ledger_audit_rate
macro_reuse_gain
history_reconstruction_accuracy
```

This shifts world-model research from "Can the model predict?" to "Can the system safely evolve state under verification and improve from evidence?"

---

## 4. Design principles

### 4.1 Hard authority over soft belief

A learned score may rank candidates. It may not commit state.

```text
hard verifier may commit
soft verifier may rank only
```

### 4.2 Typed projection before verification

Latent vectors are not directly verifiable. A latent proposal must be projected into a typed object:

```text
robot trajectory tube
code patch
proof tactic
molecular graph edit
circuit netlist diff
database transaction
```

Verification happens on the typed object, not on an uninterpreted embedding.

### 4.3 Reversibility or receipt-backed replay

Every transition must be either:

1. exactly reversible under a declared arithmetic/runtime boundary, or
2. replayable/rollbackable using sufficient receipts.

Approximate reversibility is not enough for promoted audit claims.

### 4.4 Refuse instead of unsafe commit

If no candidate passes the hard verifier, the system must refuse, expand compute, change representation, or request external input. It must not commit using a proxy score.

### 4.5 Learning from receipts, not hidden state

Training data must come from logged receipts:

```text
pre-state
proposal trace
typed candidate
verifier result
commit decision
rollback/replay evidence
runtime manifest
```

Unlogged hidden state cannot be claim authority.

### 4.6 Evidence grade discipline

A toy theorem can support a math claim. A public benchmark can support a task claim. A simulator can support simulator-bound claims. Real-world safety requires real-world safety evidence. Null results remain binding.

---

## 5. Formal model

### 5.1 Spaces

Let:

```text
X          visible world/task state space
Z          latent state space
A          action/proposal space
C          context space
Omega      stochastic seed/noise space
Lambda     typed checkable object space
Y          verifier result space
L          ledger space
M          macro/receipt memory space
Theta      proposal-model parameter space
Phi        ranking/repair parameter space
Rho        runtime manifest/context space
```

A full runtime state is:

```text
S_t = (x_t, z_t, L_t, M_t, theta_t, phi_t, rho_t, omega_t)
```

where:

- `x_t in X` is visible state,
- `z_t in Z` is latent state,
- `L_t in L` is the append-only ledger,
- `M_t in M` is macro/receipt memory,
- `theta_t` parameterizes proposal dynamics,
- `phi_t` parameterizes ranking/repair/routing,
- `rho_t` stores runtime metadata,
- `omega_t` stores branch randomness and deterministic seeds.

### 5.2 Observation, encoding, and decoding

The system observes:

```text
o_t = observe(environment)
```

An encoder maps observations or visible state into latent state:

```text
Enc: X -> Z
z_t = Enc(x_t)
```

A decoder maps latent state back to an observable prediction:

```text
Dec: Z -> X_hat
x_hat_t = Dec(z_t)
```

For partially observed domains, `z_t` may represent a belief state inferred from observation history:

```text
z_t = Enc(o_0, a_0, o_1, ..., o_t)
```

### 5.3 Reversible proposal dynamics

A proposal transition is:

```text
T_theta: Z x A x C x Omega -> Z
z_{t+1} = T_theta(z_t, a_t, c_t, omega_t)
```

Exact reversibility requires:

```text
T_theta^{-1}(T_theta(z, a, c, omega), a, c, omega) = z
```

If exact reversibility cannot be guaranteed, the transition must emit a receipt `r_t` sufficient for replay or rollback:

```text
Replay(r_t, z_t) = z_{t+1}
Rollback(r_t, z_{t+1}) = z_t
```

### 5.4 Typed projection

A latent proposal is not directly checkable. It is projected into a typed object:

```text
Pi: X x Z x C -> Lambda
lambda_t = Pi(x_t, z'_t, c_t)
```

Examples:

```text
code:       AST patch + file hashes + test command
proof:      tactic or proof term + proof-state hash
robotics:   trajectory tube + joint limits + collision envelope
molecule:   typed graph + coordinates + valence/force constraints
circuit:    netlist diff + simulation harness
database:   transaction diff + constraint bindings
chess:      legal move history candidate + board-state metadata
```

### 5.5 Verification

The hard verifier is:

```text
V_h: Lambda -> {1, 0, bottom}
```

where:

```text
1       accept
0       reject
bottom  abstain / fail closed
```

The soft verifier or scorer is:

```text
V_s: Lambda -> R
```

A calibrated proxy may help order calls to expensive verifiers, but it cannot commit.

### 5.6 Transaction

A transaction is:

```text
tau_t = (
  S_pre,
  proposal_id,
  action_or_macro,
  latent_trace,
  typed_candidate,
  hard_result,
  soft_scores,
  commit_decision,
  receipt,
  S_post_or_rollback
)
```

The commit rule is:

```text
Commit(tau_t) = 1 iff
  V_h(typed_candidate) = 1
  and ReplayCheck(tau_t) = 1
  and RollbackCheck(tau_t) = 1
  and ManifestValid(tau_t) = 1
```

If the typed candidate is rejected or abstained:

```text
Commit(tau_t) = 0
Rollback(tau_t)
LearnLocalReject(tau_t)
```

### 5.7 Macro transaction

A macro branch of depth `K` is:

```text
tau_i = (S_t, S_{i,1}, S_{i,2}, ..., S_{i,K})
```

Prefix safety requires:

```text
for all k in {1,...,K}: V_safety(S_{i,k}) = 1
```

Terminal acceptance requires either:

```text
V_h(Pi(S_{i,K})) = 1
```

or a stronger domain proof:

```text
all tests pass
proof checker accepts
collision-free trajectory
KKT residual below threshold
constraint satisfaction certified
```

### 5.8 Branch search

For branch width `B`, the system generates:

```text
{tau_1, tau_2, ..., tau_B}
```

The admissible branch set is:

```text
A_t = { i : V_h(Pi(tau_i)) = 1
            and ReplayCheck(tau_i) = 1
            and RollbackCheck(tau_i) = 1
            and ManifestValid(tau_i) = 1 }
```

If `A_t` is empty:

```text
refuse_or_expand_compute(S_t)
```

Otherwise choose:

```text
i* = argmin_{i in A_t} [ Cost(tau_i) + Energy(S_{i,K}) - beta Score_phi(tau_i) ]
```

and commit only `tau_{i*}`.

---

## 6. Mathematical primitives and theorems

### 6.1 Additive coupling invertibility

Let `z = (u, v)` with `u, v` in a vector space or dyadic lattice. Let `F_theta` and `G_theta` be deterministic functions. They need not be invertible.

Forward update:

```text
u' = u + Q_delta(alpha F_theta(v, c))
v' = v + Q_delta(alpha G_theta(u', c))
```

Inverse update:

```text
v = v' - Q_delta(alpha G_theta(u', c))
u = u' - Q_delta(alpha F_theta(v, c))
```

**Theorem 1: Exact inverse under deterministic replay.**  
If arithmetic is exact on the chosen lattice, `F_theta` and `G_theta` are deterministic, the same context `c` is replayed, and quantization is deterministic, then:

```text
T_theta^{-1}(T_theta(u, v, c), c) = (u, v)
```

**Proof.**  
From the forward update:

```text
v' = v + Q_delta(alpha G_theta(u', c))
```

During inverse, the same `u'` and `c` recompute the same increment. Therefore:

```text
v' - Q_delta(alpha G_theta(u', c)) = v
```

Now `v` is recovered. The inverse recomputes the same increment:

```text
Q_delta(alpha F_theta(v, c))
```

so:

```text
u' - Q_delta(alpha F_theta(v, c)) = u
```

Thus the original pair is exactly recovered.

### 6.2 Dyadic lattice exactness

Let the dyadic lattice be:

```text
L_delta = { n delta : n in Z }, delta = 2^{-q}
```

Quantization is:

```text
Q_delta(r) = round(r / delta) delta
```

Dyadic spacing is useful because powers of two are exactly representable in binary floating-point within mantissa limits. For promoted exactness claims, integer ticks are preferred:

```text
z_int = z / delta
```

The dynamics operates over integers:

```text
u'_int = u_int + round(alpha F(v, c) / delta)
v'_int = v_int + round(alpha G(u', c) / delta)
```

This avoids claiming more exactness than floating-point kernels can support.

### 6.3 Quantization cancellation

Consider a coupling block:

```text
y_a = x_a
y_b = x_b + Q(f(x_a))
```

The inverse is:

```text
x_a = y_a
x_b = y_b - Q(f(y_a))
```

Since `y_a = x_a`, the same quantized function is evaluated on the same input:

```text
Q(f(y_a)) = Q(f(x_a))
```

Therefore quantization error cancels in the inverse:

```text
y_b - Q(f(y_a)) = x_b + Q(f(x_a)) - Q(f(x_a)) = x_b
```

This means quantization may reduce predictive quality, but it need not break invertibility if replay is deterministic.

### 6.4 No reversible autonomous attractor

Let `X` be a finite state space. Let `A subset X` be the accepted solution set. Let:

```text
T: X -> X
```

be a bijection. Assume accepted states are stable:

```text
T(A) subseteq A
```

**Theorem 2: Pure reversibility cannot create a stable absorbing solver basin.**  
If `x notin A`, then `T^k(x) notin A` for all `k >= 0`.

**Proof.**  
Because `T` is injective on finite `X`:

```text
|T(A)| = |A|
```

Since `T(A) subseteq A` and both sets have equal cardinality:

```text
T(A) = A
```

Thus:

```text
T^{-1}(A) = A
```

If `x notin A` but `T(x) in A`, then:

```text
x in T^{-1}(A) = A
```

contradiction. Therefore no outside state enters `A` under `T`.

**Consequence.**  
A pure reversible map can transport, permute, cycle, branch, and roll back. It cannot by itself create absorbing convergence into a solution set. Solver behavior requires at least one of:

```text
hard verifier selection
external halting
irreversible visible projection
branch deletion
typed contraction
ledgered entropy export
```

### 6.5 Transactional lift

Let:

```text
f: X -> Y
```

be an irreversible visible operation, such as candidate elimination, code patch commit, robot action execution, or database update. Let `L` be ledger state. Let `r(x)` be a receipt sufficient to recover or audit `x`.

Define the lifted operation:

```text
f_tilde(x, L) = (f(x), L append r(x))
```

**Theorem 3: Invertibility on the augmented state.**  
If `r(x)` is sufficient to reconstruct `x`, then `f_tilde` is invertible on its image:

```text
f_tilde^{-1}(f(x), L append r(x)) = (x, L)
```

**Consequence.**  
Visible state may contract:

```text
H(x_{t+1}) < H(x_t)
```

while augmented state preserves recoverability:

```text
H(x_{t+1}, L_{t+1}) >= H(x_t, L_t)
```

The ledger is an entropy sink. It makes visible selection compatible with rollback and audit.

### 6.6 Hard verifier authority theorem

Let:

```text
V_h(lambda) in {1, 0, bottom}
```

The runtime rule is:

```text
commit(lambda) only if V_h(lambda) = 1
```

Assume verifier soundness:

```text
V_h(lambda) = 1 => lambda is valid
```

Then:

```text
commit(lambda) => lambda is valid
```

Unsafe commits are impossible unless the hard verifier is unsound, the projection is dishonest, the receipt is corrupted, or the runtime violates the commit rule.

### 6.7 Branch width and false-accept exposure

Suppose each branch independently succeeds with probability `p`. Then best-of-`B` success probability is:

```text
P_success(B) = 1 - (1 - p)^B
```

If invalid branches have false-accept probability `q`, then false exposure scales as:

```text
P_false_exposure(B) = 1 - (1 - q(1-p))^B
```

This gives the Goodhart boundary:

```text
More branch width helps only when the hard verifier is actually hard.
```

If `q > 0`, increasing branch width amplifies verifier errors.

### 6.8 Prefix trace ranking convergence

Suppose a task decomposes into stages:

```text
y = (y_1, ..., y_S)
```

At stage `s`, the correct macro is sampled from a stationary distribution:

```text
y_s ~ p_s(m)
```

A prefix verifier accepts a stage macro iff the prefix remains valid. A learned ranker maintains counts:

```text
N_s(m)
```

Every accepted prefix supplies one sample from `p_s`. By the law of large numbers:

```text
N_s(m) / sum_j N_s(j) -> p_s(m)
```

Therefore ranking macros by empirical accepted-prefix counts converges to ranking by true macro probability under stationarity. The expected verifier calls per solved task approach the oracle prefix policy:

```text
E[calls] = sum_s E[rank_s(y_s)]
```

This theorem explains why structured trace learning can reduce hard-verifier calls.

### 6.9 Low-rank adapter theorem

Let an ideal task update be a matrix or linearized operator `Delta W*` with singular values:

```text
s_1 >= s_2 >= ... >= s_n
```

Define cumulative energy:

```text
E(k) = (sum_{i=1}^k s_i^2) / (sum_{i=1}^n s_i^2)
```

If:

```text
E(k) >= 1 - epsilon
```

then the best rank-`k` approximation satisfies:

```text
||Delta W* - Delta W_k||_F^2 <= epsilon ||Delta W*||_F^2
```

**Interpretation.**  
If a task update is low-rank, a small adapter or compact macro memory can work. If the update is high-rank, the system should refuse, search for a better coordinate system, or use a larger mechanism.

This is the executable preflight behind the shape law. Before promoting a compact
adapter, reversible macro memory, or HDC memory claim, compute the output-visible
energy spectrum under the declared output map. The logic is the same low-rank
approximation principle formalized by
[Eckart-Young](https://doi.org/10.1007/BF02288367) and used operationally by
adapter methods such as [LoRA](https://arxiv.org/abs/2106.09685): compact
mechanisms are plausible only when most task-visible update energy is
concentrated in a small number of directions.

### 6.10 Shape-conditionality law

Define a task's intrinsic output rank `rho` as the rank needed to capture most of the target update's output-visible energy. Then:

```text
value_of_reversible_certified_substrate decreases as rho increases
```

The substrate is strongest when the task has:

```text
localized defect
low-rank update
reusable macro
typed constraint
external verifier
structured residual
```

It is weak when the task is:

```text
high-rank
unstructured
arbitrary
only terminally judged
without localized residuals
```

This is a design law, not just an empirical observation. It guides domain selection.

### 6.11 Hyperdimensional receipt memory

Let hypervectors live in `H = {-1,+1}^D` or `{0,1}^D` for large `D`. Define operations:

```text
bind(a,b)       role-value binding
bundle(a,b,...) superposition / memory sum
permute(a,k)    position/order encoding
sim(a,b)        cosine or Hamming similarity
cleanup(q,M)    retrieve nearest stored item
```

A transaction receipt can be encoded as:

```text
h_tau = bind(ROLE_context, h_context)
      + bind(ROLE_action, h_action)
      + bind(ROLE_result, h_result)
      + bind(ROLE_residual, h_residual)
      + bind(ROLE_verifier, h_verifier)
      + bind(ROLE_time, permute(h_time, t))
```

The memory stores accepted and rejected receipts:

```text
M = bundle(h_tau_1, ..., h_tau_n)
```

For a new context `h_q`, retrieve similar receipts:

```text
neighbors = top_k(sim(h_q, h_tau_i))
```

Use them to rank macros or repairs before expensive hard-verifier calls. HDC memory is not commit authority; it is an associative proposal/ranking layer.

---

## 7. Algorithmic specification

### 7.1 Verified action transaction

```python
def verified_action_transaction(state, proposer, projector, hard_verifier, ledger, learner):
    """
    One proposal -> one typed candidate -> one hard verifier decision -> commit or rollback.
    """
    pre = snapshot(state)

    proposal_trace = proposer.propose(pre)
    candidate = projector.project(pre, proposal_trace)
    hard_result = hard_verifier.check(candidate)

    receipt = make_receipt(
        pre_state_hash=hash_state(pre),
        proposal_trace=proposal_trace,
        typed_candidate=candidate,
        hard_result=hard_result,
        runtime_manifest=current_manifest(),
        parent_head=ledger.head,
    )

    ledger.append(receipt)

    if (
        hard_result.accepted
        and replay_ok(receipt)
        and rollback_ok(receipt)
        and manifest_valid(receipt)
    ):
        post = commit(pre, candidate, receipt)
        learner.update_positive(receipt)
        return post

    rollback(pre, proposal_trace, receipt)
    learner.update_local_reject(receipt)
    return pre
```

Invariant:

```text
no hard verifier accept => no commit
```

Current executable boundary:

```text
TransactionalWorldModelRuntime.step(state)
WorldModelStepCertificate(schema=trwm.world_model_step_certificate.v1)
WorldLearnerSnapshot(schema=trwm.world_learner_snapshot.v1)
WorldLearnerUpdateCertificate(schema=trwm.world_learner_update_certificate.v1)
WorldLearnerDeltaCertificate(schema=trwm.world_learner_delta_certificate.v1)
WorldLearnerLineageCertificate(schema=trwm.world_learner_lineage_certificate.v1)
WorldLearnerMergeCertificate(schema=trwm.world_learner_merge_certificate.v1)
WorldProgramManifest(schema=trwm.world_program_manifest.v1)
WorldProgramCertificate(schema=trwm.world_program_certificate.v1)
WorldProgramAdmissionPolicy(schema=trwm.world_program_admission_policy.v1)
WorldProgramAdmissionCertificate(schema=trwm.world_program_admission_certificate.v1)
WorldProgramEvidenceBundle(schema=trwm.world_program_evidence_bundle.v1)
WorldProgramBundleVerificationCertificate(schema=trwm.world_program_bundle_verification_certificate.v1)
WorldProgramReplayStep(schema=trwm.world_program_replay_step.v1)
WorldProgramReplayPackage(schema=trwm.world_program_replay_package.v1)
WorldProgramReplayVerificationCertificate(schema=trwm.world_program_replay_verification_certificate.v1)
validate_world_model_step_certificate(certificate)
validate_world_learner_snapshot(snapshot)
validate_world_learner_update_certificate(certificate)
validate_world_learner_delta_certificate(certificate)
validate_world_learner_lineage_certificate(certificate)
validate_world_learner_merge_certificate(certificate)
validate_world_program_manifest(manifest)
validate_world_program_certificate(certificate, manifest)
validate_world_program_admission_policy(policy)
validate_world_program_admission_certificate(certificate, policy, manifest, execution_certificate)
validate_world_program_evidence_bundle(bundle)
validate_world_program_bundle_verification_certificate(certificate, bundle)
validate_world_program_replay_step(step)
validate_world_program_replay_package(package)
validate_world_program_replay_verification_certificate(certificate, package)
audit_world_model_step(receipt, certificate)
audit_world_learner_update(receipt, pre_snapshot, post_snapshot, certificate)
audit_world_learner_delta(pre_snapshot, post_snapshot, update_certificate, delta_certificate)
audit_world_learner_lineage(initial_snapshot, final_snapshot, update_certificates, certificate)
audit_world_program_replay_package(bundle, steps, package)
audit_world_program_replay_verification(package, certificate)
audit_world_learner_merge(
  left_snapshot,
  right_snapshot,
  merged_snapshot,
  certificate,
  base_snapshot=None,
  left_delta_certificates=(),
  right_delta_certificates=(),
)
audit_world_program_certificate(manifest, steps, certificate, ledger_head, invalid_commit_count, replay_rollback_rate)
audit_world_program_admission(policy, manifest, execution_certificate, admission_certificate)
audit_world_program_evidence_bundle(manifest, execution_certificate, admission_policy, admission_certificate, bundle)
audit_world_program_bundle_verification(bundle, certificate)
RRLM world lane:
  RrlmMacroSnapshot(schema=trwm.rrlm_macro_snapshot.v1)
  RrlmProposalCertificate(schema=trwm.rrlm_proposal_certificate.v1)
  RrlmTransportCertificate(schema=trwm.rrlm_transport_certificate.v1)
  candidate.hashes["rrlm_snapshot_hash"] == snapshot.snapshot_hash
  candidate.hashes["rrlm_proposal_certificate_hash"] == proposal_certificate.certificate_hash
  candidate.hashes["rrlm_transport_certificate_hash"] == transport_certificate.certificate_hash
Python: trwm.experiments.world_loop.run_world_loop_benchmark
TypeScript: runWorldLoopBenchmark
HTML: html/world-loop.html
```

The shipped canary implements the full local loop for a typed scalar program:
the first proposal `set(0)` is hard-rejected against target `5`, the residual
teaches the learner the repair `add(5)`, and the second proposal
`set(0), add(5)` commits only after hard accept, replay, rollback, manifest,
and ledger checks. The step certificate binds proposer/projector identity and
version, learner identity and version, verifier identity, receipt hash, trace
hash, candidate hash, state hashes, ledger head, commit decision, learner update
count, learner-state hash, learner-snapshot hash, and learner-update
certificate hash. The learner-update certificate binds the source receipt hash
to the pre-update and post-update learner snapshot hashes, update counts, and
learned-state hash transition. The learner snapshot records the learned repair
state and the receipt hashes that trained it. The learner-delta certificate
stores a deterministic learner-state patch and proves replay from the pre-update
learner state to the post-update learner state. The learner-lineage certificate
binds the ordered update certificate hashes from the initial learner snapshot to
the final learner snapshot, so the event-sourced learner history is inspectable
before promotion or merging. This is a G1 runtime-learning canary. The learner
merge certificate adds a conservative distributed-learning
boundary: exact duplicate or subset snapshots are idempotent, trace-disjoint
snapshots join counter-like evidence and equal learned repairs deterministically,
partial-overlap snapshots merge only when a base learner snapshot and
per-receipt learner-delta certificates replay both branches from a common
prefix, and conflicting learned repairs fail closed. It does not claim neural
world-model lift, policy optimality, or cross-domain
generalization.

The benchmark also embeds the RRLM proposer into the same transactional runtime.
The first reversible scalar macro `set0` is hard-rejected, the receipt penalty
is recorded in the RRLM snapshot, the next RRLM proposal certificate ranks
`set0-add-target` first, and the repaired candidate commits only after hard
acceptance plus replay/rollback checks. The typed candidate and receipt
artifact hashes bind the RRLM snapshot, proposal certificate, and transport
certificate, and a recomputed-score tamper probe fails validation. RRLM remains
a proposal substrate, not a commit authority.

The same lane is now wrapped by a `trwm.world_program_manifest.v1` and
`trwm.world_program_certificate.v1`. The manifest records the executable
program identity, proposer/projector/learner/verifier identities, input and
candidate schemas, external parameters, and resolved dependency surfaces. The
certificate binds the manifest hash to the ordered step-certificate hashes,
receipt hashes, final learner snapshot hash, ledger head, invalid-commit
count, replay/rollback audit rate, and grouped RRLM artifact hashes. This makes
a programmed world-loop execution auditable as a unit while preserving the
receipt-level hard-verifier authority boundary.

A `trwm.world_program_admission_policy.v1` and
`trwm.world_program_admission_certificate.v1` now add the programmable
admission layer. The policy names the expected build type, program ID/version,
component IDs, schemas, dependencies, required artifact keys, minimum
step/commit/reject counts, zero-invalid-commit bound, and replay/rollback
threshold. The admission certificate records passed and failed requirement
keys. The shipped RRLM world policy admits the expected execution and a
missing-artifact probe is rejected, making policy failure an auditable artifact
instead of an implicit caveat.

A `trwm.world_program_evidence_bundle.v1` and
`trwm.world_program_bundle_verification_certificate.v1` now add the portable
handoff layer. The bundle packages the manifest, execution certificate,
admission policy, admission certificate, step certificate hashes, receipt
hashes, final learner snapshot hash, artifact groups, and optional source
bundle links. The bundle verification certificate records the verifier
identity, input attestation hashes, passed/failed requirement keys, and whether
the bundle is verified. This mirrors the provenance-bundle and verification
summary pattern without claiming an external signature or third-party trust
root.

A `trwm.world_program_replay_package.v1` closes the gap between attestation
summaries and executable evidence by carrying the actual trace, typed
candidate, receipt, world-step certificate, pre/post learner snapshots,
learner-update certificate, and learner-delta certificate for each step. Its
verification certificate recomputes trace and candidate hashes, checks receipt
static validity, audits each world-step certificate, replays learner deltas,
recomputes the receipt ledger head, and verifies that all body hashes agree
with the admitted evidence bundle. It is still local deterministic replay
evidence, not a remote attestation or external signature.

### 7.2 Reversible dyadic proposal step

```python
def q(x, delta):
    return round(x / delta) * delta


def reversible_forward(u, v, context, F, G, alpha, delta):
    du = q(alpha * F(v, context), delta)
    u_next = u + du

    dv = q(alpha * G(u_next, context), delta)
    v_next = v + dv

    return u_next, v_next


def reversible_inverse(u_next, v_next, context, F, G, alpha, delta):
    dv = q(alpha * G(u_next, context), delta)
    v = v_next - dv

    du = q(alpha * F(v, context), delta)
    u = u_next - du

    return u, v
```

Admission gate:

```python
assert reversible_inverse(*reversible_forward(u, v, c, F, G, alpha, delta), c, F, G, alpha, delta) == (u, v)
```

### 7.3 Branch search with sacred commit

```python
def branch_step(state, branch_width, macro_depth, proposer, projector, hard_verifier, ledger, ranker):
    parent = snapshot(state)
    branches = []

    for i in range(branch_width):
        trace = fork_state(parent, branch_id=i)
        for k in range(macro_depth):
            action = proposer.sample_action(trace.current, seed=(ledger.head, i, k))
            trace.forward(action)

            if violates_prefix_safety(trace.current):
                trace.mark_rejected(reason="prefix_safety")
                break

        branches.append(trace)

    verified = []

    for trace in branches:
        candidate = projector.project(parent, trace)
        result = hard_verifier.check(candidate)
        receipt = make_branch_receipt(parent, trace, candidate, result, ledger.head)
        ledger.append(receipt)

        if result.accepted and replay_ok(receipt) and rollback_ok(receipt):
            verified.append((trace, candidate, receipt))

    if not verified:
        rollback_all(branches)
        return refuse_or_expand_compute(parent)

    winner = ranker.choose_after_hard_filter(verified)
    next_state = commit(parent, winner.candidate, winner.receipt)

    rollback_losers(branches, winner.trace)
    ranker.learn_from_outcome(winner, branches)

    return next_state
```

Rules:

```text
workers may propose
hard verifier filters
ranker chooses among admissible candidates
commit manager commits one canonical transition
```

### 7.4 Prefix-safe macro transaction

```python
def macro_transaction(state, macro, verifier, ledger):
    pre = snapshot(state)
    trace = [pre]
    s = pre

    for step in macro.steps:
        s = apply_step(s, step)
        trace.append(s)

        if not verifier.prefix_safe(s):
            receipt = write_reject_receipt(pre, trace, reason="prefix_unsafe")
            ledger.append(receipt)
            rollback_trace(trace)
            return pre

    candidate = macro.project(pre, trace)
    terminal = verifier.terminal_check(candidate)

    receipt = write_macro_receipt(pre, trace, candidate, terminal)
    ledger.append(receipt)

    if terminal.accepted and rollback_ok(receipt) and replay_ok(receipt):
        return commit(pre, candidate, receipt)

    rollback_trace(trace)
    return pre
```

Macro transactions are needed because atomic commits can get stuck behind local barriers. Prefix safety prevents unsafe barrier crossing.

### 7.5 Receipt and hash-chain ledger

A receipt should contain at minimum:

```text
receipt_id
parent_head
pre_state_hash
post_state_hash or rollback_state_hash
proposal_trace_hash
typed_candidate_hash
verifier_id
verifier_version
verifier_result
runtime_manifest
random_seed
model_version
projection_schema_version
replay_instructions
rollback_instructions
artifact_hashes
timestamp
signature optional
```

Hash chain update:

```python
def append_receipt(ledger, receipt):
    receipt.parent_head = ledger.head
    receipt.hash = H(canonical_json(receipt.without_hash()))
    ledger.head = H(ledger.head + receipt.hash)
    ledger.rows.append(receipt)
```

Tamper detection:

```python
def audit_ledger(ledger):
    head = GENESIS
    for receipt in ledger.rows:
        assert receipt.parent_head == head
        assert receipt.hash == H(canonical_json(receipt.without_hash()))
        head = H(head + receipt.hash)
    assert head == ledger.head
```

### 7.6 Replay and rollback audit

```python
def replay_audit(seed_state, ledger):
    s = seed_state
    for receipt in ledger.rows:
        if receipt.committed:
            s2 = replay_transition(s, receipt)
            assert hash_state(s2) == receipt.post_state_hash
            s = s2
    return s


def rollback_audit(seed_state, ledger):
    states = [seed_state]
    s = seed_state

    for receipt in ledger.rows:
        if receipt.committed:
            s = replay_transition(s, receipt)
            states.append(s)

    for receipt in reversed([r for r in ledger.rows if r.committed]):
        s = rollback_transition(s, receipt)
        expected = states.pop()
        assert hash_state(s) == hash_state(states[-1])
```

### 7.7 Trace learning

```python
def update_from_receipt(receipt, proposal_model, ranker, repair_model, macro_library):
    if receipt.committed and receipt.hard_result.accepted:
        proposal_model.add_positive(receipt.context, receipt.trace)
        ranker.add_pairwise_positive(receipt)
        macro_library.mine_subtraces(receipt)
        return

    if receipt.hard_result.accepted and receipt.commit_decision == "rolled_back_loser":
        ranker.add_counterfactual_loser(receipt.context, receipt.candidate)
        return

    if receipt.hard_result.rejected:
        residual = extract_residual(receipt)
        ranker.add_local_reject(receipt.context, receipt.candidate)
        repair_model.add_example(receipt.candidate, residual)
        return

    if receipt.hard_result.abstained:
        ranker.add_uncertainty(receipt.context, receipt.candidate)
```

Safe rejection rule:

```text
rejection is local evidence unless the verifier certifies a globally invalid class
accepted-but-rolled-back loser is counterfactual ranking evidence, not verifier failure
```

Current executable boundary:

```text
CounterfactualRollbackRanker.update(receipt)
CounterfactualRollbackRanker.rank(context, candidates)
Python: trwm.experiments.counterfactual_learning.run_counterfactual_rollback_benchmark
TypeScript: runCounterfactualRollbackBenchmark
```

The shipped canary uses a branch set with one committed accepted winner, one
accepted but rolled-back loser, and one hard reject. The legacy receipt-count
ranker treats both accepted candidates as positive and ties back to token order;
the counterfactual rollback ranker distinguishes `commit` from
`rolled_back_loser` and ranks the committed winner first. This is inspired by
counterfactual-regret ideas, but it is not CFR or a policy-optimality claim. It
is a narrow executable check that branch receipts carry useful loser evidence
without granting any learner commit authority.

### 7.8 Residual repair proposer

```python
def repair_loop(state, candidate, verifier, repair_model, max_repairs):
    current = candidate

    for j in range(max_repairs):
        result = verifier.check(current)
        if result.accepted:
            return current, result

        residual = result.residual
        current = repair_model.propose(current, residual)

    return current, verifier.check(current)
```

Examples of residuals:

```text
failed unit test diff
proof checker error
collision segment
constraint residual vector
molecule force violation
state prediction residual
```

### 7.9 Hyperdimensional receipt memory ranker

```python
def encode_receipt(receipt, encoder):
    h = ZERO
    h += bind(ROLE_CONTEXT, encoder.context(receipt.context))
    h += bind(ROLE_ACTION, encoder.action(receipt.action))
    h += bind(ROLE_RESULT, encoder.result(receipt.hard_result))
    h += bind(ROLE_RESIDUAL, encoder.residual(receipt.residual))
    h += bind(ROLE_VERIFIER, encoder.verifier(receipt.verifier_id))
    return normalize(h)


def retrieve_macros(context, memory, encoder, top_k):
    hq = bind(ROLE_CONTEXT, encoder.context(context))
    neighbors = memory.nearest(hq, top_k=top_k)
    return mine_candidate_macros(neighbors)


def rank_candidates_with_hdc(context, candidates, memory, encoder):
    retrieved = retrieve_macros(context, memory, encoder, top_k=32)
    return score_by_similarity_and_outcome(candidates, retrieved)
```

HDC memory is useful when exact symbolic matching is too brittle but full neural retrieval is too expensive or opaque.

### 7.10 Shape-rank preflight

```python
def shape_rank_preflight(target_updates, output_map, rank_budget):
    # output_map can be an unembedding, decoder Jacobian, test residual map, etc.
    A = linearize_output_map(output_map)
    _, S, Vt = svd(A)

    energies = []
    for delta in target_updates:
        coeff = Vt @ delta
        e = (S ** 2) * (coeff ** 2)
        energies.append(e)

    e_total = sort_desc(sum(energies))
    if sum(e_total) == 0:
        return {
            "r90": 0,
            "fits_budget": True,
            "energy_at_budget": 0.0,
            "cumulative_energy": zeros_like(e_total),
            "component_energy": e_total,
        }

    cumulative = cumsum(e_total) / sum(e_total)
    r90 = one_based_first_index(cumulative >= 0.90)
    budget_index = min(rank_budget, len(cumulative)) - 1
    energy_at_budget = cumulative[budget_index] if rank_budget > 0 else 0.0

    return {
        "r90": r90,
        "fits_budget": r90 <= rank_budget,
        "energy_at_budget": energy_at_budget,
        "cumulative_energy": cumulative,
        "component_energy": e_total,
    }
```

Decision rule:

```text
if r90 is small: use compact reversible adapter / macro memory
if r90 is large: refuse compact-adapter claim, search for better coordinates or larger model
```

Current executable boundary:

```text
Python: trwm.preflight.shape_rank_preflight
TypeScript: shapeRankPreflight
Inputs: target update vectors, optional output map, rank budget, energy threshold
Outputs: r90, cumulative_energy, component_energy, total_energy, energy_at_budget, fits_budget
```

The shipped shape-conditionality simulator uses this preflight as a canary:
low-rank motif updates fit the compact budget, while high-rank target updates do
not. This is evidence for a domain-selection diagnostic, not proof that any
specific learned adapter or reversible transport will improve held-out tasks.

### 7.11 Distributed branch worker protocol

Worker input:

```text
parent_ledger_head
state_snapshot_hash
state_snapshot
branch_id
model_version
projection_schema
verifier_version
seed
budget
```

Worker output:

```text
branch_receipt
candidate
verifier_result
replay_bundle
rollback_bundle
cost_metrics
```

Commit manager rule:

```python
def commit_manager(parent_state, branch_receipts):
    admissible = []

    for r in branch_receipts:
        if r.parent_head != ledger.head:
            reject(r, reason="stale_parent")
            continue
        if not replay_ok(r) or not rollback_ok(r):
            reject(r, reason="bad_replay_or_rollback")
            continue
        if not r.hard_result.accepted:
            reject(r, reason="not_hard_accepted")
            continue
        admissible.append(r)

    if not admissible:
        return refuse_or_expand_compute(parent_state)

    winner = choose_by_cost_energy_soft_rank(admissible)
    return commit(parent_state, winner)
```

---

## 8. System architecture

### 8.1 Layered architecture

```text
+-------------------------------------------------------------+
| Evaluation and claim-boundary layer                         |
| baselines, metrics, gates, replay bundles, reports          |
+-------------------------------------------------------------+
| Learning layer                                               |
| proposal learning, ranker, repair model, macro memory, HDC  |
+-------------------------------------------------------------+
| Ledger and transaction layer                                |
| receipts, hash chain, commit/rollback, replay, manifests    |
+-------------------------------------------------------------+
| Verifier layer                                               |
| hard checkers, safety checkers, soft rankers, abstention     |
+-------------------------------------------------------------+
| Typed projection layer                                       |
| AST/proof/trajectory/molecule/circuit/database projections   |
+-------------------------------------------------------------+
| Reversible / replayable world-model layer                    |
| encoders, decoders, reversible latent dynamics, branches     |
+-------------------------------------------------------------+
| Domain/environment layer                                     |
| code, simulator, proof kernel, robot, database, molecule     |
+-------------------------------------------------------------+
```

### 8.2 Canonical runtime cycle

```text
observe
encode
fork branches
roll out reversible proposals
project to typed candidates
hard verify
commit one accepted candidate or refuse
rollback losers
write receipts
learn from accepted/rejected traces
audit replay and rollback
```

### 8.3 Dataflow

```text
x_t
  -> Enc -> z_t
  -> branch proposal T_theta^i -> z_{i,t+K}
  -> Pi(x_t, z_{i,t+K}) -> lambda_i
  -> V_h(lambda_i) -> accept/reject/abstain
  -> receipt_i
  -> commit manager
  -> x_{t+1}, z_{t+1}, L_{t+1}, M_{t+1}
```

### 8.4 Distribution model

Branch workers are parallel. Commit is serialized.

```text
state snapshot + seed + model version + verifier version -> branch receipt
```

A branch worker cannot mutate canonical state. It returns a receipt. The commit manager validates parent head, verifier result, replay, rollback, and manifest before committing.

---

## 9. Domain instantiations

### 9.1 Chess and state forensics

Visible state:

```text
board, side-to-move, castling rights, en-passant square, move counters
```

Typed projection:

```text
legal move predecessor or history sequence
```

Hard verifier:

```text
chess rule engine + forward replay
```

Unique capability:

```text
Given a board, infer possible legal histories and ambiguity entropy.
```

Current executable boundary:

```text
ChessAncestryAdapter.verify(candidate)
reverse_chess_candidates(problem)
enumerate_chess_ancestry(problem)
run_chess_ancestry_benchmark()
```

The current implementation is a bounded G1 king/rook last-move canary. It
checks same-color occupancy, rook path blocking, side-to-move, king attack
constraints, and forward replay, then reports history count and ambiguity
entropy for the legal predecessors. It does not implement pawns, castling,
en-passant, checkmate/stalemate, move counters, opening legality, or a
competitive chess engine.

### 9.2 Sokoban reverse planning

Visible state:

```text
walls, crates, player, goals
```

Typed projection:

```text
push/pull macro sequence
```

Hard verifier:

```text
legal Sokoban transition checker
```

Unique capability:

```text
Search backward from solved crate states, then replay forward for certificate.
```

### 9.3 Code repair

Visible state:

```text
file tree, tests, failing outputs, type errors
```

Typed projection:

```text
patch diff + file hashes + test command
```

Hard verifier:

```text
unit tests, type checker, linter, security policy
```

Unique capability:

```text
Every patch is a reversible transaction with replayable tests and rollback.
```

Current executable boundary:

```text
CodePatchAdapter.verify(candidate)
CodeResidualRepairer.propose(candidate, residual)
run_code_repair_benchmark(seed, episodes)
```

The current implementation is a bounded G1 canary for unit-test-guided repair:
it patches one mutable operator in a tiny integer expression grammar, carries
the base file hash in the candidate, and treats the supplied test suite as hard
verifier authority. This follows the test-suite adequacy boundary of automatic
program repair and the grammar-bounded spirit of syntax-guided synthesis, but it
does not execute arbitrary Python, repair real repositories, prove semantic
correctness beyond the tests, or claim security analysis.

### 9.4 Formal proof

Visible state:

```text
proof context, goals, hypotheses
```

Typed projection:

```text
tactic, proof term, or proof-state transition
```

Hard verifier:

```text
proof kernel
```

Unique capability:

```text
The ledger is an auditable proof search trace.
```

Current executable boundary:

```text
HornProofAdapter.verify(candidate)
ProofResidualRepairer.propose(candidate, residual)
run_proof_kernel_benchmark(seed, episodes, rule_count)
```

The current implementation uses a deliberately small Horn-rule checker rather
than a general theorem prover. Proof search and residual repair are untrusted
proposal mechanisms; only the kernel can accept a script, and accepted scripts
still pass replay, rollback, manifest, and ledger checks before commit. This is
the same architectural boundary as LCF-style and Coq/Rocq-style systems: complex
tactic machinery may propose proof objects, but a small kernel must check the
result.

### 9.5 Robotics

Visible state:

```text
robot pose, object state, contacts, environment map, force estimates
```

Typed projection:

```text
trajectory tube, action chunk, safety envelope
```

Hard verifier:

```text
collision checker, joint limit checker, speed/force bounds, simulator postcheck
```

Unique capability:

```text
World model proposes action chunks; safety shield commits only verified chunks.
```

Current executable boundary:

```text
RobotTrajectoryAdapter.verify(candidate)
RobotResidualRepairer.propose(candidate, residual)
run_robot_trajectory_benchmark(seed, episodes)
```

The current implementation is a bounded 2D point-robot trajectory-tube canary.
Candidates are waypoint corridors in a unit-square configuration space. The hard
verifier checks exact segment-circle clearance against inflated circular
obstacles and checks per-segment speed bounds before any trajectory can commit.
Residual repair is shield-like: an unsafe direct action chunk is replaced by the
first verified detour corridor from a bounded action set. This is evidence for a
geometric safety-shield transaction boundary, not evidence of MuJoCo fidelity,
robot hardware safety, uncertainty handling, dynamics, contacts, or real-world
deployment.

### 9.6 Molecules/materials

Visible state:

```text
graph, coordinates, charges, constraints
```

Typed projection:

```text
molecular edit, conformer proposal, reaction path candidate
```

Hard verifier:

```text
valence rules, energy/force constraints, synthesis constraints, simulator
```

Unique capability:

```text
Retrosynthetic/history search over typed graph transactions.
```

Current executable boundary:

```text
MoleculeGraphAdapter.verify(candidate)
MoleculeResidualRepairer.propose(candidate, residual)
run_molecule_repair_benchmark(seed, episodes)
```

The current implementation uses a small organic-subset molecular graph over C,
N, O, F, and Cl. Bonds are explicit single/double/triple orders; hydrogens are
implicit under normal valence; the hard verifier checks valence and exact
formula before commit. This is a G1 graph-constraint canary inspired by the
OpenSMILES organic subset and common valence-checking practice, not a SMILES
parser, RDKit replacement, aromaticity model, stereochemistry engine,
force-field model, synthesis planner, or molecule-design claim.

### 9.7 Circuits/hardware

Visible state:

```text
netlist, layout, timing, power, area
```

Typed projection:

```text
gate/wire/layout diff
```

Hard verifier:

```text
simulation, equivalence check, design rule check, timing closure
```

Unique capability:

```text
Search circuit edits under verifier-call accounting with replayable provenance.
```

Current executable boundary:

```text
BooleanCircuitAdapter.verify(candidate)
CircuitResidualRepairer.propose(candidate, residual)
run_circuit_repair_benchmark(seed, episodes)
```

The current implementation uses a small acyclic combinational netlist and exact
4-bit truth-table masks for all binary Boolean operators. The hard verifier
compares the complete target truth table and can emit a residual identifying a
unique mutable gate replacement, but the repaired netlist must still be
reverified before commit. This is a G1 canary for transaction-wrapped
combinational equivalence checking, not a SAT/BDD engine, HDL compiler,
timing-closure system, or sequential hardware verifier.

### 9.8 Operations and databases

Visible state:

```text
tables, inventories, orders, capacities, policies
```

Typed projection:

```text
transaction diff or plan
```

Hard verifier:

```text
constraints, policy checks, accounting invariants
```

Unique capability:

```text
Infer plausible transaction histories and commit future plans safely.
```

Current executable boundary:

```text
InventoryReservationAdapter.verify(candidate)
candidate = pre_state + order + stock/reserved diff
hard verifier checks duplicate orders, stock sufficiency, exact diff shape, and
accounting conservation
InventoryResidualRepairer.propose(candidate, stock_shortage_residual)
```

This canary follows the transaction-processing principle that application
updates should preserve declared consistency constraints before commit. It is
inspired by classical transaction-processing and concurrency-control work such
as [Gray-Reuter](https://www.sciencedirect.com/book/9781558601901/transaction-processing)
and predicate-lock/consistency formalization by
[Eswaran et al.](https://doi.org/10.1145/360363.360369). It does not implement
isolation, durability, locking, or a concurrent database engine. It only tests
typed transaction diffs, accounting residuals, replay, rollback, and verifier
authority inside the TRWM substrate.

---

## 10. Evaluation metrics

Primary metric:

```text
success_per_hard_verifier_call = verified_successes / hard_verifier_calls
```

Equivalent:

```text
calls_per_verified_solution = hard_verifier_calls / verified_successes
```

Safety/audit metrics:

```text
invalid_commit_count
unsafe_commit_count
rollback_replay_rate
ledger_audit_rate
postcheck_failure_count
manifest_valid_rate
soft_verifier_commit_count
```

Learning metrics:

```text
macro_reuse_rate
accepted_prefix_rate
repair_success_rate
ranker_auc_against_hard_outcomes
verifier_call_reduction_vs_baseline
held_out_eta_improvement
generation_0_to_final_improvement
```

World-model metrics:

```text
one_step_prediction_error
multi_step_rollout_error
inverse_cycle_error
history_reconstruction_accuracy
counterfactual_consistency
state_estimation_error
uncertainty_calibration
```

Distribution metrics:

```text
branches_per_second
stale_receipt_rejection_rate
distributed_equals_local_rate
commit_conflict_rate
worker_replay_failure_rate
```

---

## 11. Required baselines

Every promoted result must compare against strong same-case baselines.

### 11.1 Generic baselines

```text
direct hard-verifier search
random macro equal-budget
static typed order
terminal-only learning
soft verifier without hard commit
hard prefix verifier without learning
oracle or near-oracle ceiling where available
```

### 11.2 Model baselines

```text
non-reversible latent model
transformer proposer
MLP/RNN dynamics model
hand-coded heuristic
classical planner
CEM/MPC optimizer
scripted policy
```

### 11.3 Mechanism ablations

```text
without reversible dynamics
without typed projection
without macro memory
without residual repair
without HDC receipt memory
without branch width
without ledger replay gate
without hard verifier authority
```

A mechanism claim is allowed only if the mechanism beats the matched ablation under equal verifier-call and compute budgets.

---

## 12. Evidence hierarchy

```text
G0  theorem/proposal/toy proof only
G1  deterministic unit tests / repo-local synthetic benchmark
G2  real GPU/kernel execution
G3  real local model boundary
G4  public benchmark or real dataset with baselines
G5  copied-bundle replay on clean machine/runtime
G6  adversarial/tamper audit and reviewer blockade passed
```

Claim rule:

```text
A claim may cite only evidence at or above its required grade.
```

Examples:

```text
math theorem        -> G0 sufficient
implementation API -> G1 sufficient
GPU exactness       -> G2 required
model claim         -> G3 required
public task lift    -> G4 required
reproducibility     -> G5 required
robustness          -> G6 required
real-world safety   -> real-world safety evidence required
```

---

## 13. Falsification plan

### 13.1 Core falsifiers

The proposal should be weakened or rejected if:

1. Hard-verifier-call efficiency does not improve over strong baselines on structured tasks.
2. Replay/rollback fails under audited conditions.
3. Learned rankers improve training cases but fail held-out verifier-call panels.
4. Reversible proposal fields do not beat matched non-reversible fields when mechanism lift is claimed.
5. Macro transactions do not outperform atomic/random baselines under equal budgets.
6. HDC receipt memory adds retrieval noise without verifier-call reduction.
7. The system relies on privileged oracle access not available to the compared baselines.
8. The hard verifier has false positives that branch width amplifies.
9. The system cannot produce sufficient receipts for rollback/replay.
10. Claimed improvements vanish under public benchmark provenance.

### 13.2 Shape-law falsifier

Construct two task families:

```text
low-rank repair family:
  localized corruptions
  reusable fixes
  structured residuals
  prefix verifier

high-rank random family:
  independent arbitrary targets
  no reusable structure
  only terminal pass/fail
```

Prediction:

```text
TRWM improves verifier-call efficiency in low-rank repair family.
TRWM shows little/no advantage in high-rank random family.
```

If TRWM wins equally on high-rank random tasks, the shape law is incomplete. If it fails on low-rank repair tasks, the core thesis is weakened.

### 13.3 Safety falsifier

Fault inject:

```text
hallucinated transition
invalid typed object
corrupted receipt
stale parent head
wrong verifier version
unsafe prefix
nondeterministic replay
```

Expected behavior:

```text
invalid commits = 0
fail closed or reject
ledger audit detects tampering
rollback remains exact
```

Any invalid commit is a serious failure.

---

## 14. Experimental program

### Phase 0: Minimal kernel

Deliver:

```text
state snapshot
transaction receipt
hash-chain ledger
commit/rollback
runtime manifest
replay checker
tamper probe
```

Exit gates:

```text
ledger audit passes
rollback exactness passes
tamper detected
parent-head mismatch rejected
manifest mismatch rejected
```

### Phase 1: Reversible token/block layer

Deliver:

```text
DeltaToken
BlockToken
inverse
compose
read/write sets
commutativity check
circular log
compaction
parallel replay
```

Exit gates:

```text
primitive round-trip
block inverse
compaction safety
parallel replay equals sequential
randomized read/write tests
```

Current executable boundary:

```text
DeltaToken(key, before, after)
BlockToken(tokens)
CircularTokenLog(capacity, base_state)
CircularTokenLogCertificate
compact_token_prefix(base_state, tokens)
parallel_batches(tokens)
ParallelReplayCertificate
randomized_parallel_replay_trials(seed=11, trials=64)
randomized_circular_token_log_trials(seed=17, trials=64)
```

The current G1 implementation treats declared read/write sets as a conservative
conflict-serializability graph. Tokens with write/read, read/write, or
write/write overlap are separated by a batch barrier; non-conflicting tokens may
share a replay batch. The certificate records token count, batch count, conflict
count, batch layout, sequential final-state hash, parallel final-state hash, and
certificate hash. The canary schedule partitions six delta tokens into
`0,1,3,5 | 2,4`; sequential and batch replay both reach
`{"a":3,"b":5,"c":4,"d":6}`, block inverse returns to the seed state,
certificate tampering is detected, and randomized read/write trials report zero
mismatches. This satisfies the proposal's replay-equivalence gate for local
token logs only; it is not database isolation, distributed consensus, lock
management, durability, or a measured parallel speedup claim.

The bounded circular-log canary completes the local compaction side of this
phase. A `CircularTokenLog` retains only the latest suffix of size `capacity`
and folds evicted reversible deltas into a canonical compacted prefix block.
The current demo stores eight deltas with capacity `3`; the first five deltas
collapse to `b:0->2` and `c:0->4`, while the retained suffix is `b:2->5`,
`d:0->6`, and `a:0->7`. Full replay and compacted replay both reach
`{"a":7,"b":5,"c":4,"d":6}`, inverse replay returns to the seed state,
certificate tampering is detected, and randomized circular-log trials report
zero mismatches. This follows event-sourcing snapshots and log-compaction at
the shape level only. It is not a durable event store, Kafka topic, database
WAL, consensus log, or proof that compacted-away intermediate states remain
available for external audit.

### Phase 2: First hard-checker domain

Recommended choices:

```text
code repair with tests
Sokoban reverse solver
Game of Life predecessor search
small SAT/CSP
chess ancestry reconstruction
```

Exit gates:

```text
hard verifier adapter works
typed projection schema stable
invalid commits = 0
replay/rollback = 1.0
baseline comparison present
```

Current executable boundary:

```text
Game of Life predecessor search: Life(predecessor) == target
Sokoban reverse search: reverse pulls propose a predecessor, then forward
push-certificate replay verifies the candidate
Small CNF-SAT/CSP: assignments are typed candidates; rejected candidates return
unsatisfied-clause residuals for local repair proposals
```

The Sokoban implementation is a tiny G1 state-forensics canary. It uses the
classic push-only box mechanics studied in Sokoban motion-planning work such as
[Dor-Zwick](https://doi.org/10.1016/S0925-7721(99)00017-6) and the search
literature around relevance/deadlock pruning, but it does not claim a
competitive Sokoban solver. The claim is narrower: reverse search can emit a
typed predecessor certificate that only commits after forward reachability,
replay, rollback, manifest, and ledger checks pass.

The SAT/CSP implementation is another G1 hard-checker canary grounded in the
CNF satisfiability line from
[Davis-Logemann-Loveland](https://doi.org/10.1145/368273.368557) through
conflict/residual-driven SAT search systems such as
[GRASP](https://doi.org/10.1109/12.769433). It does not claim DPLL, CDCL, or
solver competitiveness. The claim is narrower: verifier residuals can name the
unsatisfied clauses that drive subsequent typed assignment proposals, while the
transaction engine still controls every commit.

### Phase 3: Branch and macro runtime

Deliver:

```text
branch width B
macro depth K
prefix safety
loser rollback
cost accounting
rank-after-hard-filter
```

Exit gate:

```text
macro branch improves success_per_hard_verifier_call over atomic/random baselines
```

Current executable boundary:

```text
BranchRuntime.step(state, traces)
BudgetedBranchRuntime.step(state, traces)
BranchSelectionCertificate(schema=trwm.branch_selection_certificate.v1, indices, receipt hashes)
build_branch_selection_certificate(receipts)
validate_branch_selection_certificate(certificate)
audit_branch_selection(receipts, certificate)
run_branch_selection_benchmark()
```

Current G1 branch runtime now has a portable rank-after-hard-filter
certificate. The certificate is built only from finalized receipts and records
the accepted, rejected, abstained, loser, selected, and committed index sets
plus receipt, proposal-trace, and typed-candidate hashes. A rejected or
abstained branch cannot be selected, committed, or marked as a rolled-back
loser; a committed branch must be the selected accepted branch; and if a
selected accepted branch exists, every other accepted branch must be a
`rolled_back_loser`. The demo canary gives a rejected branch the best soft
rank, yet the certificate records selected/committed index `2`, rejected index
`0`, loser index `1`, zero invalid commits, valid ledger/replay/rollback audit,
and tamper detection. This is a local runtime-assurance-style monitor over an
untrusted ranker. It is not a proof of ranker optimality, verifier completeness,
or distributed consensus.

### Phase 4: Trace learning

Deliver:

```text
accepted trace store
local rejection ranker
counterfactual loser ranker
prefix macro counts
macro library
proxy reliability weights
receipt budget policy
learning evaluation certificate
transfer evaluation certificate
transfer guard snapshot
claim certificate audit
```

Exit gate:

```text
held-out verifier-call efficiency improves
no safety/replay regression
```

Current executable boundary:

```text
ReceiptRanker.update(receipt)
CounterfactualRollbackRanker.update(receipt)
HyperdimensionalMemory.add(receipt)
BoundedMacroMemory.update(receipt)
MacroMemorySnapshot(snapshot_hash, entries)
VerifierReliabilityMemory.update_from_receipt(receipt)
VerifierReliabilityMemory.select_for_audit(subject_ids, max_audits)
ReceiptBudgetPolicy.update(token, receipt)
ReceiptBudgetPolicy.plan(candidates, budget)
LearningEvaluationCertificate(schema=trwm.learning_evaluation_certificate.v1, train/eval receipt hashes, baseline metrics)
validate_learning_evaluation_certificate(certificate)
TransferEvaluationCertificate(schema=trwm.transfer_evaluation_certificate.v1, source/target domains, target eval receipt hashes, baseline metrics)
validate_transfer_evaluation_certificate(certificate)
TransferGuardMemory.update(certificate)
TransferGuardSnapshot(schema=trwm.transfer_guard_snapshot.v1, entries)
validate_transfer_guard_snapshot(snapshot)
ClaimCertificate(schema=trwm.claim_certificate.v1, requirements, metrics, boundary)
validate_claim_certificate(certificate)
run_counterfactual_rollback_benchmark(episodes)
run_shape_conditionality()
```

Current G1 trace learning includes accepted/rejected receipt counts, HDC receipt
retrieval, macro-memory reuse, bounded macro-memory consolidation, and
counterfactual rollback ranking. The bounded memory canary merges duplicate
macro receipts, retains strong positive and negative evidence under capacity,
forgets weak stale rows, and emits a hash-checked memory snapshot. The rollback
canary demonstrates a concrete failure mode of naive receipt counts: a hard
accepted branch loser is not the same signal as a committed winner. The
counterfactual ranker uses commit decisions to improve branch ordering while
hard verifiers, replay, rollback, and ledger audit still own all state changes.

The current proxy-reliability canary learns audit priority from
verifier-agreement receipts. A strict primary produces three audited agreements;
a flawed primary produces one audited agreement and two audited false positives.
The reliability memory records only independently audited successes/failures,
computes Wilson lower bounds, emits a hash-checked snapshot, and ranks the
flawed primary first for a one-slot audit budget. A naive strict-first audit
misses the future false-positive probe, while the reliability-ranked audit
detects `verifier_false_positive` with audit residual `stock_shortage`. This is
audit allocation, not commit authority.

The current receipt budget-policy canary learns verifier scheduling from
receipt outcomes. A successful `quantity-5` inventory receipt and rejected
`quantity-8`/`quantity-7` receipts train conservative success lower bounds.
Under budget `3`, cheap-first scheduling spends two cost-1 verifier calls on
known failures and does not commit; the learned policy solves an exact
integer-cost subset plan, selects the cost-3 `quantity-5` repair, and commits
in one hard-verifier call. Its policy snapshot is hash-checked and tamper
detection passes. This is learned proposal scheduling, not commit authority.

The current learning-evaluation canary binds the budget-policy claim to a
trace-disjoint certificate. A `trwm.learning_evaluation_certificate.v1` artifact
records the learner snapshot hash, three training receipt hashes, one held-out
evaluation receipt hash, the same-budget cheap-first baseline, hard-commit-only
evidence, zero invalid commits, ledger audit, replay/rollback rate, and the
exact verifier-call gain ratio `2/1`. Validation recomputes train/eval
disjointness and rejects both receipt-overlap and metric tampering. This is a
local promotion gate for deterministic G1 evidence, not a statistical
generalization test or public benchmark protocol.

The current transfer-audit canary prevents a source-only policy from being
silently promoted as cross-domain transfer. A source inventory receipt trains a
budget policy to prefer `quantity-5`; on a target inventory with only two units
available, that transferred preference receives `stock_shortage`, while the
same-case target-local baseline commits `quantity-2` under the same one-call
budget. The `trwm.transfer_evaluation_certificate.v1` artifact binds
source/target domain ids, source receipt hashes, target evaluation receipt
hashes, same-case baseline metrics, hard-commit-only evidence, and the
conclusion `negative_transfer`. This records negative transfer as first-class
evidence rather than treating transfer as an assumed benefit.

The current transfer-guard canary consumes that validated negative-transfer
evidence as operational admission memory. `TransferGuardMemory` stores the
source-target conclusion, emits a `trwm.transfer_guard_snapshot.v1` snapshot,
and rejects source-policy reuse on the target with
`negative_transfer_certificate`. In the executable canary, unguarded reuse of
`quantity-5` fails with `stock_shortage`; the guarded path falls back to the
same-case target-local `quantity-2` baseline and commits. The guard is not a
commit authority and cannot bypass the target hard verifier.

The current claim-certificate canary turns the promotion checklist into an
auditable artifact. A supported `trwm.claim_certificate.v1` certificate binds
selected learning-canary metrics to explicit requirements: zero invalid
commits, ledger audit, replay/rollback, trace-disjoint evaluation, same-case
budgets, verifier-call accounting, learning-evaluation certificate validation,
transfer-overclaim rejection, transfer-guard blocking, RRLM
proposal-certificate validation, RRLM transport-certificate validation,
learner-update validation, learner-delta validation, learner-lineage
validation, learner-merge validation, partial-overlap learner-merge
validation, RRLM-backed world-loop proposal-certificate validation,
world-program certificate validation, world-program admission policy
validation, world-program evidence-bundle verification, world-program replay
verification, mechanism ablation, null-result reporting, and G1 claim boundary. A
second certificate rejects the
overclaim that RRLM
reversibility alone beats a matched non-reversible receipt ranker because the
measured gain is `1.0`. Certificate hashes validate and metric tampering is
detected. This follows provenance and assurance-case structure only at the
local artifact level; it is not an external safety case or signed attestation.

### Phase 5: Reversible learned proposal field

Deliver:

```text
dyadic additive-coupling proposal model
forward/inverse exactness canary
matched non-reversible baseline
reversible-only ablation
```

Exit gate:

```text
reversible mechanism beats matched non-reversible proposal on held-out verifier-call metric if claiming mechanism lift
```

Current executable boundary:

```text
RRLM macro proposer = reversible receipt-learned proposal ranking
z = [score, tie, accepted_count, rejected_prefix_count]
T(z) = [score + 64 * accepted_count - 32 * rejected_prefix_count,
        tie - macro_length,
        accepted_count,
        rejected_prefix_count]
T^-1 subtracts the same integer deltas
RrlmMacroSnapshot(schema=trwm.rrlm_macro_snapshot.v1, learned rows, source receipt hashes)
RrlmProposalCertificate(schema=trwm.rrlm_proposal_certificate.v1, ranked proposals, latent transport, cycle count)
RrlmTransportCertificate(schema=trwm.rrlm_transport_certificate.v1, forward/inverse cycles, signed-i32 admission)
validate_rrlm_macro_snapshot(snapshot)
validate_rrlm_proposal_certificate(certificate, snapshot)
validate_rrlm_transport_certificate(certificate, proposal_certificate)
```

In the G1 macro-grid implementation, RRLM improves over reversible-only static
ordering after receipts identify the safe macro, but it ties the matched
non-reversible receipt ranker. Therefore the current implementation claims
exact reversible auditability and proposal replay, not reversible mechanism lift.
The RRLM snapshot and proposal certificate make this narrower claim auditable:
the snapshot binds learned accepted/rejected macro evidence to source receipt
hashes, while the proposal certificate recomputes each integer transport step,
ranking key, and inverse cycle result. The transport certificate separately
binds the proposal certificate hash, recomputes CPU forward/inverse roundtrips,
and records whether every arithmetic input, intermediate, output, and
roundtrip value is admissible for the signed-i32 WebGPU transport lane.
Tampered counts, scores, or roundtrip fields fail validation even when hashes
are recomputed.

### Phase 6: Residual repair learning

Deliver:

```text
residual schema
repair proposer
counterfactual receipts
top-k submitter
```

Exit gate:

```text
repair reduces verifier calls vs random/static/scripted/CEM baselines
invalid commits = 0
```

Current executable boundary:

```text
ResidualSignal(schema=trwm.residual.v1, kind, category, fields, repair_hints)
residual_signal_from_receipt(receipt)
residual_learning_hash(signal)
ResidualTaxonomyMemory.update(signal)
ResidualTopKSubmitter(engine, memory).submit(state, options, top_k, residual_signal)
```

The current residual-schema canary normalizes three existing hard-verifier
receipts: operations `stock_shortage`, projection-contract
`projection_contract_violation`, and verifier-budget
`verifier_budget_exhausted`. The raw residual hash remains part of the
auditable signal hash, while the separate learning hash is computed from the
normalized semantic view so snake_case and camelCase variants can train the same
feature. This standardizes residual envelopes for learning; it does not change
the hard verifier result or synthesize repairs by itself.

The current top-k submitter canary turns a residual hint into verifier-call
scheduling. A stock-shortage receipt learns `quantity=5`; a bad candidate pool
ordered as `8, 7, 5, 4` is then submitted under top-k `2`. Unranked top-k spends
both calls on rejected candidates and fails to commit. Residual-ranked top-k
tries `quantity=5` first, commits after one hard-verifier call, audits cleanly,
and rolls back to the seed state. The submitter ranks and bounds proposals only;
the hard verifier still decides every submitted candidate.

### Phase 7: HDC receipt memory

Deliver:

```text
hypervector receipt encoder
accepted/rejected memory
similarity retrieval
macro ranking
noise/tamper robustness tests
```

Exit gate:

```text
HDC retrieval improves verifier-call efficiency over no-memory and exact-match memory baselines
```

Current executable boundary:

```text
HyperdimensionalMemory.encode_receipt(receipt)
HyperdimensionalMemory.encode_query(partial_context)
HyperdimensionalMemory.nearest_vector(noisy_query_vector)
```

The current HDC benchmark uses a low-rank context-shift task where exact
full-context matching sees no repeated key, while HDC retrieval queries by
partial receipt context. It reports calls per success for no-memory, exact-match
memory, and HDC memory; verifies retrieval under 10 percent query-bit flips;
and confirms ledger tamper detection. HDC memory remains a proposal/ranking
substrate only: retrieved precedents can order candidates, but hard verification
and ledger replay/rollback still own every commit.

### Phase 8: Distributed substrate

Deliver:

```text
branch worker protocol
verifier worker protocol
receipt bundle format
commit manager
parent-head anchoring
stale receipt rejection
```

Exit gate:

```text
distributed execution equals local canonical result under deterministic seeds
```

Current executable boundary:

```text
WorkerReceipt(parent_head, trace, typed_candidate, hard_result)
DistributedCommitManager(engine, ranker).commit_one(state, worker_receipts)
local BranchRuntime and distributed commit use the same deterministic ranker
CheckpointCertificate(prefix_receipt_hashes, checkpoint_head, state_hash, checkpoint_state)
replay_from_checkpoint(checkpoint, suffix_receipts, adapter)
RedactedReceiptView(original_receipt_hash, policy_hash, redacted_payload, commitments)
verify_redacted_path(view, path, value, salt)
```

The current distributed benchmark simulates verifier workers over a counter
hard-checker domain. Workers emit parent-head-anchored receipt bundles, the
coordinator rejects stale parents, and distributed commit chooses the same
lowest-cost accepted candidate as local branch execution under deterministic
seeds. This is not a full consensus protocol or network fault-tolerance claim;
it is an executable equivalence canary for the distributed substrate boundary.

The current checkpoint-compaction canary replaces an audited receipt prefix with
a `trwm.checkpoint.v1` certificate containing prefix receipt hashes,
checkpoint head, checkpoint state, state hash, adapter identity, and certificate
hash. Suffix replay still checks parent-head continuity and receipt hashes, then
must reach the same final state hash and ledger head. This is replay
checkpointing for a trusted local ledger, not a consensus checkpoint, external
signature, or proof that missing receipt bodies were valid for third-party
audit.

The current redaction canary adds a non-authoritative receipt view for sharing:
selected replay/rollback-sensitive fields are replaced by salted path
commitments while the original receipt hash, commit decision, hard-verifier
result, redaction policy hash, and redacted view hash stay visible. A holder can
selectively disclose one path by providing the original value and salt. The
redacted view cannot be used as a replay/rollback receipt and is not a signed
SD-JWT, verifiable credential, zero-knowledge proof, unlinkability result, or
privacy-law compliance claim.

### Phase 9: Multi-domain SDK

Candidate order:

1. Code repair with tests.
2. Sokoban/Game of Life/chess for state forensics.
3. Formal proof tactics.
4. MuJoCo digital-twin robotics.
5. Circuit netlist repair.
6. Molecule/graph constraint search.
7. Database/operations transactions.

Exit gate:

```text
same transaction kernel supports at least three domains with domain-specific projectors/verifiers
```

Current executable boundary:

```text
ProgrammableSubstrate.register(domain_id, adapter)
ProgrammableSubstrate.submit(domain_id, state, trace, typed_candidate)
ReceiptDomainRouter.rank(context, domain_ids)
CostAwareReceiptDomainRouter.rank(context, domain_ids)
TransferGuardedDomainRouter.rank_with_transfer_guard(context, domain_ids, source_domains, target_domain)
TransferGuardedDomainRoute(schema=trwm.transfer_guarded_domain_route.v1, base/reranked domains, blocked domains, decision hash)
validate_transfer_guarded_domain_route(route)
BudgetedBranchRuntime(engine, projector, VerifierBudget(max_cost)).step(state, traces)
ReceiptBudgetPolicy.plan(candidates, budget)
VerifierAgreementAdapter(primary_adapter, audit_verifier).verify(candidate)
certify_claim(requirements, metrics, evidence_grade, boundary)
DomainManifestCertificate(schema=trwm.sdk_domain_manifest.v1, verifier identity, schema surface, receipt hashes)
build_domain_manifest(runtime)
validate_domain_manifest(certificate)
audit_domain_manifest(runtime, certificate)
run_sdk_manifest_benchmark()
```

The current SDK implementation supports scalar program repair, Game of Life
predecessor search, grid macro verification, Sokoban reverse planning,
operations transactions, formal proof-kernel checking, circuit netlist repair,
molecule graph checking, bounded code-patch checking, 2D robot trajectory
checking, and chess ancestry checking with one transaction kernel and
per-domain ledgers. The receipt-domain router learns from
accept/reject receipts and may order domains for a context, but it cannot
commit. Domain hard verifiers, replay, rollback, manifest checks, and ledger
audit still own every accepted state transition. This is evidence for
programmable substrate breadth, not evidence of cross-domain transfer learning.
The cost-aware router additionally reads explicit `verifier_cost` metadata from
hard-verifier receipts and ranks domains by committed successes per cost unit.
It is a scheduling/proposal policy only; it cannot turn a rejection into a
commit.

The transfer-guarded SDK router composes receipt routing with validated
negative-transfer admission memory. In the current canary, the base receipt
router ranks `source_policy` first because it has source-domain success
evidence. A `trwm.transfer_guarded_domain_route.v1` route then binds the base
rank, blocked source domain, reranked domain order, and transfer-guard decision
hash. The unguarded target execution chooses `quantity-5` and fails with
`stock_shortage`; the guarded route chooses `target_policy`, submits
`quantity-2`, and commits through the target hard verifier. This is proposal
admission, not transfer-learning lift or commit authority.

The budgeted branch runtime handles finite verifier compute by issuing
hard-abstain receipts for projected candidates whose declared verifier cost
exceeds the remaining budget. A budget-abstained branch records residual
`kind=verifier_budget_exhausted`, `required_verifier_cost`, `remaining_budget`,
and zero `verifier_cost_spent`; it is not an admissible commit candidate. The
current canary uses budget `4`, skips an accepted-but-cost-7 branch without a
verifier call, pays cost `2` for one rejection, pays cost `2` for one accepted
candidate, and commits only the verified accepted candidate.

The receipt budget policy composes the budget primitive with trace learning. It
updates rows from prior receipts, computes conservative Wilson lower bounds for
each proposal token, and solves an exact integer-cost subset plan before
submitting selected candidates through the same hard-verifier transaction
engine. The executable canary uses budget `3`: cheap-first scheduling submits
`quantity-8` and `quantity-7`, both rejected, while the learned plan submits
only `quantity-5` and commits after hard verification. This is narrower than
budgeted expert-advice or variable-cost bandit algorithms: no online regret
claim is made, and memory cannot bypass verification.

The verifier-agreement guard treats hard-verifier soundness as another
transaction boundary. A primary verifier accept is not commit-admissible until
an independent audit verifier agrees. If the primary accepts and the audit
rejects or abstains, the guard returns a hard reject from verifier authority
`verifier_agreement_guard` and records residual
`kind=verifier_false_positive` with the primary result, audit result, audit
residual, and both verifier identities. The executable canary uses a flawed
inventory primary that accepts an over-reservation: unguarded branch selection
commits `unsafe-large`, drives stock from `5` to `-3`, and still passes local
ledger audit because the flawed hard verifier authorized it. The guarded path
blocks that branch with audit residual `stock_shortage` and commits
`safe-small`, leaving stock `2`. This is a runtime-assurance/design-diversity
primitive, not a proof that the audit verifier is independent or complete.

Claim certificates make the SDK's claim boundary programmable. A benchmark or
domain package can emit requirements, metrics, evidence grade, sources, and a
boundary string; the certificate is `supported` only when every requirement
passes, otherwise it is a rejected claim artifact with failed requirement keys.
The current canary supports only a bounded G1 learning-safety claim and rejects
an RRLM mechanism-lift overclaim. This does not replace external assurance
review; it prevents local benchmark prose from silently exceeding executable
evidence.

World-program certificates make a programmable world-model execution
inspectable before claim promotion. A `trwm.world_program_manifest.v1` records
component identities, schemas, external parameters, and dependencies, while a
`trwm.world_program_certificate.v1` binds ordered step evidence, receipt hashes,
final learner state, ledger head, replay/rollback audit rate, invalid-commit
count, and grouped artifact hashes such as RRLM snapshot/proposal/transport
hashes. A `trwm.world_program_admission_policy.v1` then declares the expected
program and evidence envelope, and a
`trwm.world_program_admission_certificate.v1` records pass/fail requirement
keys so missing dependencies, missing artifacts, or unsafe counters reject as
auditable policy evidence. A `trwm.world_program_evidence_bundle.v1` then
packages the manifest, execution certificate, admission policy, admission
certificate, step hashes, receipt hashes, final learner snapshot hash, and
artifact groups. A
`trwm.world_program_bundle_verification_certificate.v1` verifies that bundle
against the local policy boundary and records pass/fail requirement keys.
The companion `trwm.world_program_replay_package.v1` carries the step bodies
behind those hashes, and
`trwm.world_program_replay_verification_certificate.v1` verifies body hashes,
learner-delta replay, and ledger-head reconstruction against the admitted
bundle.

SDK domain manifests make the programmable substrate inspectable before routing
or claim promotion. A `trwm.sdk_domain_manifest.v1` certificate binds a domain's
adapter type, verifier ID/version, candidate type names, projection schema
versions, model versions, receipt schema versions, receipt hashes, ledger head,
hard-verifier calls, verifier-cost units, ledger audit status, and invalid
commit count. The current canary registers scalar and Life domains, records one
scalar commit plus one Life reject and one Life commit, validates both
manifests, audits them against the live runtimes, and detects verifier-ID
tampering. This is a local provenance and compatibility artifact, not remote
attestation, plugin isolation, package signing, or proof that two domains are
semantically interchangeable.

SDK transfer-guard routes make cross-domain proposal admission inspectable
before routing. The route artifact records the base learned domain order, the
blocked source domains, the reranked proposal-domain order, and the
transfer-guard decision hash. It is valid only when the reranking is consistent
with the decision and the blocked set. It cannot commit, and target execution
still requires the target adapter's hard verifier, replay, rollback, and ledger
audit.

---

## 15. Minimal SDK API

### 15.1 Core interfaces

```python
class StateSnapshot:
    state: object
    hash: str
    schema_version: str

class ProposalTrace:
    branch_id: str
    actions: list
    latent_states: list
    seeds: list
    model_version: str

class TypedCandidate:
    payload: object
    type_name: str
    schema_version: str
    hashes: dict

class HardVerifierResult:
    accepted: bool
    rejected: bool
    abstained: bool
    residual: object | None
    verifier_id: str
    verifier_version: str

class Receipt:
    parent_head: str
    pre_state_hash: str
    post_state_hash: str | None
    proposal_trace_hash: str
    typed_candidate_hash: str
    hard_result: HardVerifierResult
    runtime_manifest: dict
    replay_bundle: object
    rollback_bundle: object
    receipt_hash: str
```

### 15.2 Runtime interfaces

```python
class Proposer:
    def propose(self, state: StateSnapshot, budget: dict) -> ProposalTrace: ...

class Projector:
    def project(self, state: StateSnapshot, trace: ProposalTrace) -> TypedCandidate: ...

class HardVerifier:
    def check(self, candidate: TypedCandidate) -> HardVerifierResult: ...

class Ledger:
    def append(self, receipt: Receipt) -> None: ...
    def audit(self) -> bool: ...

class CommitManager:
    def commit_or_rollback(self, state, receipts): ...

class Learner:
    def update(self, receipt: Receipt) -> None: ...
```

### 15.3 Domain adapter interface

```python
class DomainAdapter:
    def observe(self) -> object: ...
    def encode(self, visible_state) -> object: ...
    def decode(self, latent_state) -> object: ...
    def project(self, state, trace) -> TypedCandidate: ...
    def verify(self, candidate) -> HardVerifierResult: ...
    def apply_commit(self, state, candidate) -> object: ...
    def rollback(self, state, receipt) -> object: ...
```

Current executable boundary:

- `trwm.projection` and `src/projection.ts` now define a projection contract
  layer: required verifier fields, projection manifests, source hashes, field
  hashes, and fail-closed coverage audits.
- `trwm.experiments.projection_contract` and
  `src/projection_contract.ts` instantiate this boundary for a stopping-distance
  canary. A partial typed projection that omits `safety_clearance` is rejected
  before commit, even though an intentionally unguarded verifier accepts the
  same partial view.
- The math is integer/rational:

```text
speed^2 + 2 * brake * clearance <= 2 * brake * distance
```

so the canary does not depend on floating-point tolerances.

---

## 16. Open research questions

### 16.1 Representation

- Which domains admit low-rank, typed, repair-structured coordinates?
- Can shape-rank preflight predict substrate usefulness before training?
- How should latent manifolds be constrained to remain checkably projectable?
- Can reversible latent spaces support partial observability without hiding unverifiable assumptions?

### 16.2 Verification

- How hard must a verifier be before branch width helps rather than amplifies false positives?
- Can verifier residuals be standardized across domains?
- How should abstention be handled under compute budgets?
- What is the right notion of verifier-call cost when verifiers differ in expense?

Current G1 answer to hard-verifier false positives:

```text
primary_result = primary.verify(candidate)
if primary_result is accept:
    audit_result = independent_audit.verify(candidate)
    commit_admissible iff audit_result is accept
    otherwise record verifier_false_positive residual
else:
    preserve primary reject/abstain as non-committing guard result
```

The executable canary shows why branch width is dangerous with an unsound
verifier: a cheaper unsafe inventory branch can win ranking and commit while
the receipt chain still audits locally. The agreement guard changes the
authority boundary so that primary accepts become proposals to the guard, not
commit authority by themselves. This is useful only to the extent that the audit
verifier is independently specified and implemented; shared specification bugs
remain outside the claim.

Current G1 answer to residual standardization:

```text
keep result.residual raw and hash-addressed for audit
derive ResidualSignal(kind, category, fields, repair_hints, attributes)
derive residual_learning_hash from the normalized semantic view
never let normalized residuals override hard-verifier status
```

The executable canary maps real receipt residuals into resource, coverage, and
budget categories while detecting tampering with the residual signal hash.
Snake/camel raw payload variants can share a learning hash, but the raw residual
hashes remain distinct. This is a residual telemetry and learning-feature
schema, not a proof that every domain residual can be made ontology-complete.

Current G1 answer to verifier-call cost:

```text
track explicit verifier_cost metadata in each hard-verifier receipt and rank
proposal routes by committed_successes / summed_verifier_cost, not by raw
accept count alone.
```

The executable canary has two domains with one committed success each. The
uniform router ties and preserves registration order; the cost-aware router
compares exact ratios `1/12` and `1/3` and selects the cheaper equally
successful verifier. This is not yet a UCB, budgeted-bandit, or optimal
exploration claim. It is the receipt-level accounting primitive required before
cost-sensitive verifier scheduling can be evaluated.

Current G1 answer to abstention under compute budgets:

```text
if candidate_verifier_cost > remaining_budget:
    record HardVerifierResult.abstain(kind="verifier_budget_exhausted")
    verifier_cost_spent = 0
    candidate is not commit-admissible
else:
    call hard verifier and charge verifier_cost_spent
commit only among verified accepted candidates
```

The executable canary separates abstention from rejection and from successful
verification: over-budget branches still leave auditable receipts, but the
runtime never treats an unverified branch as accepted. This is not an optimal
reject-option classifier or budgeted prediction policy; it is the fail-closed
transaction behavior needed before learned budget allocation can be trusted.

### 16.3 Learning

- When do rejected branches provide useful local negative signals?
- How should macro memories be merged, forgotten, or compressed?
- Can HDC receipt memory outperform learned embeddings for retrieval under distribution shift?
- How should proposal models learn from counterfactual rollbacks?
- How should proxy/verifier reliability weights be learned without becoming commit authority?
- How should learned verifier-budget allocation rank candidates without becoming commit authority?

Current G1 answer to macro-memory merge/forget/compress:

```text
merge rows by context + canonical macro token
accepted commits add positive evidence
prefix-unsafe receipts add negative prefix evidence
terminal rejects add weaker negative evidence
retain rows by bounded evidence priority, not by unbounded log growth
rank by signed evidence score, but never commit from memory alone
hash memory snapshots for audit/tamper checks
```

The executable canary feeds ten grid-macro receipts into a capacity-two memory.
Duplicate safe macro receipts merge into one positive row; repeated
unsafe-prefix receipts merge into one negative row; weak stale rows are evicted.
The final memory ranks the safe macro first and the unsafe macro last, validates
its snapshot hash, and detects snapshot tampering. This follows prioritized
experience replay only at the level of keeping higher-value experiences in a
bounded replay memory. It is not an optimal eviction policy, learned embedding
memory, or proof of continual-learning performance.

Current G1 answer to proxy reliability weights:

```text
ingest only independently audited agreement/disagreement receipts
success = primary accept and audit accept
failure = primary accept and audit reject
unknown = audit abstain or unaudited evidence
rank audit priority by conservative lower confidence, not raw accept count
hash reliability snapshots for tamper checks
never let reliability memory commit or skip required hard verification
```

The executable canary uses Wilson lower bounds over audited successes/failures:
the strict primary has `3/3` clean audited agreements and lower bound
`0.438493919551`; the flawed primary has `1/3` clean audited agreements and
lower bound `0.061490315276`. With audit budget `1`, the learned reliability
policy audits the flawed primary first and detects the future stock-shortage
false positive. This is not Dawid-Skene observer inference, Thompson sampling,
or a learned safety certificate; it is a receipt-grounded audit scheduler.

Current G1 answer to residual top-k submission:

```text
extract repair_hints from a hard-verifier residual receipt
store hint counts in ResidualTaxonomyMemory
rank candidate repair options by matching current/learned repair hints
submit only top_k candidates to the hard verifier
commit only if a submitted candidate passes verifier/replay/rollback
```

The executable canary uses top-k `2`. Without residual ranking, the first two
repair candidates are still over-reservations and no commit occurs. With the
learned `quantity=5` hint, the first submitted repair commits in one verifier
call. This is a bounded submitter for scarce verifier calls, not a complete
counterexample-guided synthesis system, syntax-guided synthesis solver, or
cross-entropy optimizer.

Current G1 answer to learned verifier-budget allocation:

```text
update token rows only from receipts
score candidates by conservative success lower bound times declared reward
solve exact integer-cost subset plan under verifier budget
submit selected candidates to the normal hard-verifier transaction engine
commit only if hard verifier, replay, rollback, and manifest checks pass
hash budget-policy snapshots for tamper checks
```

The executable canary uses budget `3` and candidate order `8, 7, 5, 4`.
Cheap-first scheduling submits `quantity-8` and `quantity-7`, spends cost `2`,
and does not commit. The receipt-trained planner gives `quantity-5` lower bound
`0.206543291474`, selects that exact cost-3 repair, commits in one verifier
call, and detects policy-snapshot tampering. This is not UCB, Thompson
sampling, or online budgeted prediction; it is the transaction-safe planning
primitive needed before those policies can be evaluated.

### 16.4 Distribution

- How should commit conflicts be resolved in distributed branch search?
- What consensus model is needed for multi-agent/robot deployments?
- Can branch receipts be compressed without losing replay authority?
- How should privacy-sensitive receipts be redacted while preserving auditability?

Current G1 answer to branch receipt compression:

```text
full receipt ledger remains the source evidence
an audited prefix may be materialized into CheckpointCertificate
checkpoint stores prefix receipt hashes, checkpoint_head, checkpoint_state, state_hash, adapter identity
suffix replay starts from checkpoint_state and validates parent-head continuity
final compacted replay must match the full ledger head and final state hash
```

The executable canary checkpoints the first three rows of a six-row inventory
ledger. Full replay needs four committed receipt replays; replay from the
checkpoint needs only the two committed suffix replays and reaches the same
state hash and ledger head. Checkpoint-state tampering and stale suffix parent
heads are rejected. This follows database checkpoint and event-sourcing
snapshot practice, but it is not a consensus checkpoint, public proof that
unavailable receipt bodies were valid, or permission to discard evidence needed
for third-party audit.

Current G1 answer to privacy-sensitive receipt redaction:

```text
ledger receipts remain unredacted commit authority
shared views preserve original_receipt_hash and visible commit/verifier fields
redacted paths are replaced by salted commitments under an explicit policy hash
redacted_hash covers the visible payload, policy, and commitment list
selective disclosure verifies one path by recomputing its salted commitment
redacted views are not replay/rollback bundles
```

The executable canary redacts `order_id`, replay `pre_state`, and rollback
`pre_state` from a committed inventory receipt. Correct selective disclosure of
the order id verifies; a wrong value fails; visible-field tampering invalidates
the redacted hash; the original ledger receipt still audits. This follows the
minimal-disclosure shape of SD-JWT and W3C VC privacy guidance, while remaining
only a dependency-free transaction artifact. It does not provide issuer
signatures, unlinkability, zero-knowledge proofs, or legal privacy compliance.

### 16.5 Safety

- How can hard-verifier false positives be detected before branch-width amplification?
- What runtime invariants should be non-bypassable?
- Can the system detect when its typed projection omits safety-critical state?
- What level of evidence is required for real-world robot safety claims?

Current G1 answer to hard-verifier false-positive amplification:

```text
wrap suspect or learned/cheap primary verifiers with an independent audit
verifier; branch runtime sees only the guard verifier identity; disagreements
are residual receipts, never commits.
```

This catches the demonstrated stock-underflow false positive before commit and
keeps replay/rollback authority delegated to the primary domain adapter only
after agreement. It does not solve colluding verifiers, common-mode
specification errors, perception errors, or real-world safety evidence.

Current G1 answer to the projection-omission question:

```text
yes, when the domain adapter declares a required projection contract and the
runtime treats missing or stale projection fields as hard verifier residuals
before commit.
```

This does not yet solve automatic discovery of required fields, dishonest sensor
observations, or unsound domain verifiers. It does harden the typed-projection
boundary: a candidate is not merely a payload; it must carry a manifest proving
which source fields were projected, and those fields are hashed into the receipt
artifact surface.

Current G1 answer to claim promotion:

```text
claim = (text, scope, evidence_grade, requirements, metrics, boundary)
status = supported iff every requirement passes
certificate_hash = hash(claim without certificate_hash)
tampered metrics or requirements invalidate the certificate hash
failed requirements are first-class evidence, not hidden caveats
```

The executable claim-audit canary supports the narrow statement that selected
G1 learning canaries preserve transaction safety and record baselines,
ablations, nulls, and trace-disjoint evaluation. It rejects the broader RRLM
mechanism-lift statement because the matched non-reversible ablation ties the
RRLM lane. It now also requires the RRLM-backed world-loop execution to be
wrapped by a valid world-program certificate and admitted by a valid
world-program admission policy, then packaged and verified as a valid
world-program evidence bundle. This makes null results, program execution
boundaries, policy boundaries, and bundle handoff boundaries binding at the
artifact layer.

---

## 17. Concrete code-interpreter experiments

These are small experiments that can be run without a large training cluster.

### 17.1 Chess ancestry reconstruction

Input:

```text
board state, side to move, depth k
```

Task:

```text
enumerate legal histories that replay to the board
```

Metrics:

```text
history_count
ambiguity_entropy
verifier_calls
forward_replay_success
```

Unique TRWM feature:

```text
state forensics: infer possible pasts, not just future moves
```

Current executable boundary:

```text
Python: trwm.experiments.chess_ancestry.run_chess_ancestry_benchmark
TypeScript: runChessAncestryBenchmark
Candidate: predecessor board + moved piece id + last-move certificate
Hard verifier: king/rook legal-move subset plus forward replay to target board
```

The shipped canary enumerates seven candidate predecessor moves for the default
board and commits the three legal histories `e5->e4`, `e6->e4`, and `e7->e4`.
It reports ambiguity entropy `log2(3)`, seven enumeration verifier calls, three
static calls to first success, two residual-repair calls to first success, clean
ledger audit, clean replay/rollback, and zero invalid commits. This is evidence
for verifier-gated state-forensics transactions, not evidence of full chess
legality, opening reconstruction, or a competitive chess engine.

### 17.2 Game of Life predecessor search

Input:

```text
target pattern
```

Task:

```text
find predecessor boards
```

Metrics:

```text
predecessor_count
forward_verification_rate
branch_efficiency
```

Unique feature:

```text
visible irreversible dynamics lifted into reversible search with receipts
```

### 17.3 Sokoban reverse solver

Input:

```text
solved crate arrangement
```

Task:

```text
search backward to reachable initial states, replay forward
```

Metrics:

```text
solutions_found
verifier_calls
macro_reuse_gain
```

Current executable boundary:

```text
parse_sokoban(level)
reverse_pull_traces(layout, solved_state, max_depth)
search_sokoban_predecessor(layout, solved_state)
hard verifier = forward replay of push certificate with player reachability
```

The shipped canary recovers a one-push predecessor from a solved one-box state.
It reports verifier calls, reverse expansions, baseline state count, invalid
commits, ledger audit, and replay/rollback rate. Macro reuse and deadlock
learning remain future work.

### 17.4 Unit-test-guided code repair ledger

Input:

```text
mutated Python function + tests
```

Task:

```text
propose patches, run tests, commit accepted patch, rollback failures
```

Metrics:

```text
success_per_test_call
invalid_commit_count
macro_edit_reuse
```

Current executable boundary:

```text
Python: trwm.experiments.code_repair.run_code_repair_benchmark
TypeScript: runCodeRepairBenchmark
Candidate: base_source hash + mutable operator patch + canonical rendered source
Hard verifier: bounded expression evaluator over the full test suite
```

The shipped canary compares static patch search over eight allowed operators
with residual-guided repair. The first failed test residual identifies the
unique operator that satisfies the full suite, but the repaired candidate still
has to pass the hard verifier and replay/rollback audit before commit.

### 17.5 Shape-conditionality simulator

Generate two families:

```text
low-rank localized repair tasks
high-rank random target tasks
```

Compare:

```text
random search
direct predictor
non-reversible repair
reversible repair
receipt-memory ranker
HDC receipt-memory ranker
```

Expected result:

```text
TRWM helps on low-rank repair, not high-rank arbitrary targets
```

### 17.6 Small SAT/CSP residual repair

Input:

```text
CNF formula + candidate Boolean assignment
```

Task:

```text
verify assignment, return unsatisfied-clause residuals, repair assignment, reverify
```

Metrics:

```text
success_per_verifier_call
unsatisfied_clause_residual_count
invalid_commit_count
replay_rollback_rate
```

Current executable boundary:

```text
CnfSatAdapter.verify(candidate)
CnfResidualRepairer.propose(candidate, residual)
run_sat_csp_benchmark(seed, episodes, variable_count)
```

The shipped canary uses formulas with known satisfying assignments so the
residual repair path can be compared against exhaustive static assignment
ordering on the same cases. This is evidence for receipt-residual usefulness in
a typed CSP setting, not a claim of complete SAT solving.

### 17.7 Operations transaction repair

Input:

```text
inventory state + reservation candidate + explicit stock/reserved diff
```

Task:

```text
verify reservation constraints, return stock-shortage residuals, repair quantity, reverify
```

Metrics:

```text
success_per_verifier_call
stock_shortage_residual_count
invalid_commit_count
ledger_audit_rate
replay_rollback_rate
```

Current executable boundary:

```text
InventoryReservationAdapter.verify(candidate)
InventoryResidualRepairer.propose(candidate, residual)
run_operations_benchmark(seed, episodes)
```

The shipped canary checks duplicate orders, stock sufficiency, exact diff shape,
and accounting conservation for inventory reservations. This is evidence that
database-style transaction diffs fit the TRWM commit boundary, not a claim of
database isolation, concurrency control, or durability.

### 17.8 Formal proof kernel canary

Input:

```text
hypotheses + Horn implication rules + candidate rule script
```

Task:

```text
verify every proof step, return missing-premise or goal-not-derived residuals, repair script, reverify
```

Metrics:

```text
success_per_verifier_call
goal_not_derived_residual_count
invalid_commit_count
ledger_audit_rate
replay_rollback_rate
```

Current executable boundary:

```text
HornProofAdapter.verify(candidate)
ProofResidualRepairer.propose(candidate, residual)
run_proof_kernel_benchmark(seed, episodes, rule_count)
```

The shipped canary uses chain proofs where only one rule order derives the goal.
Static search tries proof-script permutations; residual repair starts from an
empty script and appends the next kernel-reported applicable rule. On the
current benchmark, repair commits with clean ledger audit and replay/rollback.
This is evidence for auditable proof-search traces under a small trusted
checker, not a claim of a competitive theorem prover or general proof assistant.

### 17.9 Circuit netlist repair

Input:

```text
acyclic Boolean netlist + complete target truth table + mutable gate id
```

Task:

```text
verify combinational equivalence, return mismatch residuals, repair one gate operator, reverify
```

Metrics:

```text
success_per_verifier_call
truth_table_mismatch_residual_count
invalid_commit_count
ledger_audit_rate
replay_rollback_rate
```

Current executable boundary:

```text
BooleanCircuitAdapter.verify(candidate)
CircuitResidualRepairer.propose(candidate, residual)
run_circuit_repair_benchmark(seed, episodes)
```

The shipped canary uses a two-gate combinational netlist. The final mutable gate
is one of the 16 binary Boolean truth-table masks, while the hard verifier checks
the complete truth table against the target. Static search tries masks in a
fixed order; residual repair uses the verifier's unique gate-replacement
diagnosis and then re-enters the same commit path. On the current benchmark,
repair reduces verifier calls with clean ledger audit and replay/rollback. This
is evidence for typed circuit-repair transactions, not evidence of scalable
industrial equivalence checking. It is related to classic Boolean function and
combinational equivalence checking work such as Bryant's BDD paper and
Kuehlmann/Krohm's cuts-and-heaps equivalence checker.

### 17.10 Molecule graph repair

Input:

```text
organic-subset molecular graph + target formula + mutable atom/bond ids
```

Task:

```text
verify valence and formula, return valence/formula residuals, repair atom element plus bond order, reverify
```

Metrics:

```text
success_per_verifier_call
formula_mismatch_residual_count
valence_exceeded_residual_count
invalid_commit_count
ledger_audit_rate
replay_rollback_rate
```

Current executable boundary:

```text
MoleculeGraphAdapter.verify(candidate)
MoleculeResidualRepairer.propose(candidate, residual)
run_molecule_repair_benchmark(seed, episodes)
```

The shipped canary uses a three-heavy-atom chain with one mutable terminal atom
and one mutable bond order. Static search tries element/order edits across the
bounded organic subset; residual repair asks the hard verifier for the unique
edit that satisfies normal valence and matches the target implicit-hydrogen
formula. On the current benchmark, repair reduces verifier calls with clean
ledger audit and replay/rollback. This is evidence for typed molecular graph
constraint transactions, not evidence of realistic chemistry simulation,
retrosynthesis, or molecule generation.

### 17.11 Robot trajectory shield

Input:

```text
start pose, goal pose, circular obstacles, robot radius, clearance, max step
```

Task:

```text
propose waypoint corridor, verify swept-circle clearance and speed, repair unsafe action chunk, reverify
```

Metrics:

```text
static_calls_per_success
repair_calls_per_success
collision_residual_count
speed_limit_residual_count
invalid_commit_count
ledger_audit_rate
replay_rollback_rate
```

Current executable boundary:

```text
Python: trwm.experiments.robotics.run_robot_trajectory_benchmark
TypeScript: runRobotTrajectoryBenchmark
Candidate: canonical 2D waypoint corridor with detour_y action
Hard verifier: segment-circle clearance plus max-step speed bound
```

The shipped canary compares static detour search against residual-guided shield
repair over the same bounded detour set. The verifier uses exact projection of
an obstacle center onto each line segment and inflates obstacle radii by robot
radius plus clearance. On the current benchmark, repair reduces verifier calls
with clean ledger audit and replay/rollback. This is evidence for verifier-gated
trajectory transactions, not evidence of robot hardware safety, dynamics,
contact simulation, uncertainty handling, or a general motion planner.

---

## 18. Expected contributions

If successful, this research contributes:

1. A formal runtime model for verifier-committed world models.
2. A proof that pure reversibility is not enough, motivating transaction semantics.
3. A ledger-based interpretation of visible-state entropy export.
4. A practical algorithm for hard-verifier-gated branch/macro search.
5. A learning framework based on receipts rather than unlogged traces.
6. A domain-agnostic SDK API for typed projection and verification.
7. A shape-rank preflight test to predict where reversible/certified substrates help.
8. A bridge between reversible latent dynamics and hyperdimensional associative receipt memory.
9. A falsifiable benchmark program grounded in verifier-call efficiency.
10. A safer design pattern for world models: propose freely, commit conservatively.

---

## 19. What this is not

This proposal is not:

```text
a claim of general AGI
a claim that reversibility alone solves reasoning
a claim that learned world models are verifiers
a claim of real-world robotics safety
a claim that soft scores certify truth
a claim that all tasks benefit from reversible iteration
```

The bounded claim is:

```text
A transactional reversible world model is a promising substrate for domains where state transitions can be typed, verified, logged, rolled back, and learned from.
```

---

## 20. Summary

The core idea is simple but powerful:

```text
Prediction gives candidate futures.
Reversibility gives replay, rollback, and counterfactual search.
Typed projection gives checkable structure.
Hard verification gives authority.
Ledger receipts preserve recoverability.
Trace learning improves future proposals.
Hyperdimensional memory retrieves useful precedents.
Distribution supplies branch width.
```

Together these form a multidimensional learning substrate:

```text
S_t = (visible state, latent state, ledger, macro memory, learned policies, runtime manifest, branch randomness)
```

The system evolves by verified transactions:

```text
S_t -> propose branches -> project -> verify -> commit/rollback -> receipt -> learn -> S_{t+1}
```

The decisive principle is:

```text
A branch is cheap. A commit is sacred.
```

The next step is to implement the minimal kernel, run small hard-checker experiments, and scale only after the substrate improves `success_per_hard_verifier_call` without sacrificing zero invalid commits and exact replay.

---

## Appendix A: Compact formal definition

A Transactional Reversible World Model is a tuple:

```text
TRWM = (X, Z, A, C, Omega, Lambda, Enc, Dec, T_theta, T_theta^{-1}, Pi,
        V_h, V_s, L, R, M, Cmt, Learn_phi, Dist)
```

where:

```text
X          visible state space
Z          latent state space
A          action/proposal space
C          context space
Omega      stochastic branch seed space
Lambda     typed checkable object space
Enc        encoder X -> Z
Dec        decoder Z -> X_hat
T_theta    reversible/replayable proposal dynamics
Pi         typed projection X x Z -> Lambda
V_h        hard verifier Lambda -> {1,0,bottom}
V_s        soft score Lambda -> R
L          append-only ledger
R          rollback/replay mechanism
M          macro/receipt memory
Cmt        commit manager
Learn_phi  trace learner
Dist       distributed branch execution protocol
```

The runtime transition is valid iff:

```text
S_{t+1} = Cmt(S_t, tau_i)
```

for some branch `tau_i` satisfying:

```text
V_h(Pi(tau_i)) = 1
ReplayCheck(tau_i) = 1
RollbackCheck(tau_i) = 1
ManifestValid(tau_i) = 1
```

No other state transition is canonical.

---

## Appendix B: Minimal receipt schema

```json
{
  "receipt_id": "...",
  "parent_head": "...",
  "pre_state_hash": "...",
  "post_state_hash": "...",
  "branch_id": "...",
  "proposal_trace_hash": "...",
  "typed_candidate_hash": "...",
  "hard_verifier": {
    "id": "...",
    "version": "...",
    "result": "accept|reject|abstain",
    "residual_hash": "..."
  },
  "soft_scores": {},
  "runtime_manifest": {
    "model_version": "...",
    "projector_version": "...",
    "verifier_version": "...",
    "seed": "...",
    "device": "...",
    "package_hashes": {}
  },
  "replay_bundle_hash": "...",
  "rollback_bundle_hash": "...",
  "artifact_hashes": {},
  "receipt_hash": "..."
}
```

---

## Appendix C: Promotion checklist

Before any positive claim is promoted:

```text
[ ] hard verifier is external or fail-closed
[ ] soft verifier did not commit
[ ] typed projection schema is recorded
[ ] projection contract required fields and source-field hashes are recorded
[ ] residual envelope schema and residual learning hash are recorded
[ ] top-k repair submitters rank only proposals and cannot bypass hard verification
[ ] verifier reliability/audit-priority snapshots validate and cannot commit
[ ] budget-policy snapshots validate and learned budget plans cannot commit
[ ] claim certificates validate and rejected overclaims list failed requirements
[ ] SDK domain manifests validate verifier identity, schema surface, receipt hashes, ledger head, and zero invalid commits
[ ] world-model step certificates validate proposer/projector/learner identity, receipt hash, ledger head, learner update count, and learner snapshot hash
[ ] learner snapshots validate learned state hash and source receipt hashes
[ ] learner-update certificates validate source receipt, pre/post learner snapshot hashes, update counts, and learned-state hash transition
[ ] learner-delta certificates replay deterministic learner-state patches from pre-update to post-update state
[ ] learner-lineage certificates validate ordered update certificate hashes from initial to final learner snapshot
[ ] learner-merge certificates validate trace-disjoint evidence joins and reject conflicting learned repairs
[ ] partial-overlap learner merges require a base snapshot and per-receipt learner-delta certificates from a common prefix
[ ] RRLM-backed world-loop candidates bind proposal and transport certificate hashes into receipt artifacts while hard verifiers retain commit authority
[ ] world-program manifests and certificates bind executable component identities, schemas, dependencies, step certificates, receipt hashes, learner snapshot, ledger head, replay/rollback, and artifact groups
[ ] world-program admission policies and certificates validate expected program identity, component IDs, schemas, dependencies, required artifacts, commit/reject counts, invalid-commit bounds, replay/rollback thresholds, and rejected policy probes
[ ] world-program evidence bundles and bundle verification certificates bind manifest, execution certificate, admission policy, admission certificate, step hashes, receipt hashes, learner snapshot hash, artifact groups, source bundle links, and pass/fail verification requirements
[ ] world-program replay packages and replay verification certificates bind step bodies, recomputed trace/candidate hashes, receipt static validity, world-step audits, learner-update certificates, learner-delta replay, ledger-head reconstruction, and pass/fail verification requirements
[ ] learning-evaluation certificates validate train/eval receipt disjointness, same-case baselines, and exact verifier-call ratios
[ ] transfer-evaluation certificates validate source/target domain disjointness, held-out target receipts, same-case target baselines, and negative-transfer outcomes
[ ] transfer-guard snapshots validate source/target admission decisions and cannot commit
[ ] SDK transfer-guard routes validate blocked source domains, reranked proposal domains, and cannot commit
[ ] RRLM macro snapshots, proposal certificates, and transport certificates validate learned evidence, exact transport, ranking order, signed-i32 admission, and cannot commit
[ ] parallel replay certificates validate sequential-equivalence under read/write conflict scheduling
[ ] branch-selection certificates validate rank-after-hard-filter and loser rollback
[ ] circular token-log certificates validate compacted-prefix plus suffix replay equivalence
[ ] bounded memory snapshots validate retained/evicted evidence and cannot commit
[ ] all commits have receipts
[ ] invalid commits = 0
[ ] rollback/replay audit passed
[ ] ledger tamper probe passed
[ ] baseline comparison is same-case and equal-budget
[ ] verifier-call accounting reconciles
[ ] verifier-cost accounting reconciles when hard checks differ in expense
[ ] over-budget branches are hard-abstain receipts and never commit
[ ] primary verifier accepts are independently audited or postchecked when branch-width false-positive amplification is claimed
[ ] checkpointed receipt prefixes validate final state hash and final ledger head after suffix replay
[ ] redacted receipt views preserve original receipt hash and cannot be used as replay authority
[ ] held-out evaluation exists for learning claims
[ ] mechanism ablations exist for mechanism claims
[ ] null/negative outcomes are reported
[ ] claim boundary matches evidence grade
```

---

## Appendix D: First implementation target

The recommended first implementation is not robotics. It is a small, fast, fully auditable hard-checker suite:

```text
1. Game of Life predecessor search
2. Sokoban reverse solver
3. Python unit-test repair ledger
4. Chess ancestry reconstruction
5. Shape-conditionality simulator
```

These domains are cheap, typed, deterministic, and verifier-rich. They will expose whether the substrate improves search and learning before moving to expensive simulators or real robots.

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
python3 -m examples.analogical_branch_transfer
python3 -m examples.context_selection_transfer
python3 -m examples.context_refinement_transfer
python3 -m examples.context_retention_transfer
python3 -m examples.programmable_world_model_frontier
```

Each command emits JSON. The three domain commands now include top-level
`report`, `evidence_certificate`, and `claim_certificate` objects. The
ancestral branch command adds an `exploration_certificate` that binds past
branch receipts to later budgeted proposal ordering. The analogical branch
command adds an `analogical_certificate` that binds explicit ancestor-context
reuse and misleading-ancestor rejection. The context-selection command adds
descriptor-level `trwm.ancestral_context_selection_certificate.v1` artifacts
before branch-memory reuse. The context-refinement command adds
`trwm.ancestral_context_refinement_certificate.v1` artifacts that bind a failed
coarse retrieval to a stricter refined retrieval. The context-retention command
adds `trwm.ancestral_branch_retention_certificate.v1` artifacts that bind
committed target branches into a hash-checked future-memory update. The
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

### Context Retention Transfer

`examples.context_retention_transfer` extends the refinement loop. After each
domain records a failed coarse target branch, it refines ancestor retrieval,
commits the refined target branch, and emits an
`trwm.ancestral_branch_retention_certificate.v1` certificate for adding that
committed target receipt to memory. A sibling target then uses only the retained
target context as its ancestor and commits under the same hard verifier.

Learning: the closed loop is now retrieve, fail, refine, commit, retain, then
improve the next exploration. Retention is still evidence, not authority: the
sibling branch must pass verification, branch-selection audit, ledger audit,
replay audit, and rollback audit before commit.

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
- Negative-transfer surveys motivate explicit rejection of misleading sources:
  https://arxiv.org/abs/2009.00909
- Counterexample-guided abstraction refinement is the analogy for refining a
  coarse selection after a failed counterexample:
  https://doi.org/10.1007/10722167_15
- Active learning is the analogy for spending verifier feedback to improve the
  next query policy: https://minds.wisconsin.edu/handle/1793/60660

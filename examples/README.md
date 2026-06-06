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
python3 -m examples.programmable_world_model_frontier
```

Each command emits JSON. The three domain commands now include top-level
`report`, `evidence_certificate`, and `claim_certificate` objects. The frontier
command aggregates the three certified examples into a cross-domain report and
bounded G1 claim certificate.

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

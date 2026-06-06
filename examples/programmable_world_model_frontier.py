from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Any

from examples.common import CertifiedExampleResult, report_as_dict, validate_example_evidence_certificate
from examples.material_lattice_metropolis import run_material_lattice_metropolis_certified_experiment
from examples.molecular_dynamics_verlet import run_molecular_dynamics_verlet_certified_experiment
from examples.robotic_safety_envelope import run_robotic_safety_envelope_certified_experiment
from trwm.claims import ClaimCertificate, certify_claim, requirement, validate_claim_certificate


FRONTIER_SOURCES = (
    "https://arxiv.org/abs/1903.11199",
    "https://doi.org/10.1063/1.442716",
    "https://www.osti.gov/biblio/4390578/",
)
FRONTIER_CLAIM_BOUNDARY = (
    "G1 aggregate over three local examples only; not evidence of real-world safety, production "
    "molecular dynamics validity, materials discovery, or broad autonomous scientific reasoning."
)


@dataclass(frozen=True)
class FrontierDomainRow:
    domain: str
    experiment_id: str
    verifier_law: str
    rejected_proposal_type: str
    residual_kind: str
    committed_repair: str
    evidence_certificate_hash: str
    claim_certificate_hash: str
    next_substrate_requirement: str


@dataclass(frozen=True)
class ProgrammableWorldModelFrontierReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    child_experiment_ids: tuple[str, ...]
    rows: tuple[FrontierDomainRow, ...]
    all_evidence_valid: bool
    all_claims_supported: bool
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_invalid_commit_count: int
    aggregate_sources: tuple[str, ...]
    learning: str


@dataclass(frozen=True)
class ProgrammableWorldModelFrontierResult:
    report: ProgrammableWorldModelFrontierReport
    claim_certificate: ClaimCertificate


def run_programmable_world_model_frontier_experiment() -> ProgrammableWorldModelFrontierResult:
    return build_programmable_world_model_frontier_result(
        (
            run_robotic_safety_envelope_certified_experiment(),
            run_molecular_dynamics_verlet_certified_experiment(),
            run_material_lattice_metropolis_certified_experiment(),
        )
    )


def build_programmable_world_model_frontier_result(
    children: tuple[CertifiedExampleResult, ...],
) -> ProgrammableWorldModelFrontierResult:
    rows = tuple(_frontier_row(child) for child in children)
    evidence_valid = tuple(validate_example_evidence_certificate(child.evidence_certificate, child.report) for child in children)
    claims_supported = tuple(validate_claim_certificate(child.claim_certificate) and child.claim_certificate.status == "supported" for child in children)
    total_invalid = sum(child.evidence_certificate.invalid_commit_count for child in children)
    report = ProgrammableWorldModelFrontierReport(
        schema_version="trwm.example.programmable_world_model_frontier.v1",
        experiment_id="programmable_world_model_frontier",
        evidence_grade="G1",
        domain_count=len(children),
        child_experiment_ids=tuple(child.evidence_certificate.experiment_id for child in children),
        rows=rows,
        all_evidence_valid=all(evidence_valid),
        all_claims_supported=all(claims_supported),
        total_receipt_count=sum(child.evidence_certificate.receipt_count for child in children),
        total_committed_count=sum(child.evidence_certificate.committed_count for child in children),
        total_rejected_count=sum(child.evidence_certificate.rejected_count for child in children),
        total_invalid_commit_count=total_invalid,
        aggregate_sources=tuple(sorted({source for child in children for source in child.evidence_certificate.sources})),
        learning=(
            "The common substrate pattern is stable across these domains: typed physical state, hard "
            "domain-law verifier, receipt-bound parameters or randomness, replay/rollback adapter, "
            "residual repair surface, and evidence certificate before claim promotion."
        ),
    )
    claim = certify_claim(
        claim_id="programmable_transactional_world_model_frontier_g1",
        claim_text=(
            "The three certified examples identify a common G1 substrate path toward a programmable "
            "transactional world model for physical proposal systems."
        ),
        evidence_grade="G1",
        scope="programmable_world_model_frontier",
        requirements=(
            requirement("exactly_three_domains", report.domain_count == 3),
            requirement("all_evidence_certificates_valid", report.all_evidence_valid),
            requirement("all_child_claims_supported", report.all_claims_supported),
            requirement("no_invalid_commits", report.total_invalid_commit_count == 0),
            requirement("source_coverage", set(report.aggregate_sources) == set(FRONTIER_SOURCES)),
            requirement("cross_domain_rows_present", len(report.rows) == 3),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
        },
        boundary=FRONTIER_CLAIM_BOUNDARY,
        sources=FRONTIER_SOURCES,
    )
    return ProgrammableWorldModelFrontierResult(report=report, claim_certificate=claim)


def _frontier_row(child: CertifiedExampleResult) -> FrontierDomainRow:
    experiment_id = child.evidence_certificate.experiment_id
    if experiment_id == "robotic_safety_envelope":
        return FrontierDomainRow(
            domain=child.evidence_certificate.domain,
            experiment_id=experiment_id,
            verifier_law="signed-distance trajectory tube plus max-step bound",
            rejected_proposal_type="short straight-line path with obstacle collision",
            residual_kind="collision",
            committed_repair=f"detour_y={child.report.repaired_detour_y}",
            evidence_certificate_hash=child.evidence_certificate.certificate_hash,
            claim_certificate_hash=child.claim_certificate.certificate_hash,
            next_substrate_requirement="world-program wrappers for physical residual learners",
        )
    if experiment_id == "molecular_dynamics_verlet":
        return FrontierDomainRow(
            domain=child.evidence_certificate.domain,
            experiment_id=experiment_id,
            verifier_law="Lennard-Jones velocity-Verlet integrator plus invariant bounds",
            rejected_proposal_type="forward-Euler dynamics step",
            residual_kind="integrator_mismatch",
            committed_repair="velocity_verlet_state",
            evidence_certificate_hash=child.evidence_certificate.certificate_hash,
            claim_certificate_hash=child.claim_certificate.certificate_hash,
            next_substrate_requirement="typed dynamics parameter manifolds and invariant replay certificates",
        )
    if experiment_id == "material_lattice_metropolis":
        return FrontierDomainRow(
            domain=child.evidence_certificate.domain,
            experiment_id=experiment_id,
            verifier_law="periodic Ising Hamiltonian delta plus Metropolis acceptance",
            rejected_proposal_type="high-energy spin flip with receipt-bound random draw",
            residual_kind="metropolis_reject",
            committed_repair=f"energy_delta={child.report.repaired_delta_energy}",
            evidence_certificate_hash=child.evidence_certificate.certificate_hash,
            claim_certificate_hash=child.claim_certificate.certificate_hash,
            next_substrate_requirement="ensemble certificates for receipt-bound stochastic proposal sources",
        )
    raise ValueError(f"unknown certified example: {experiment_id}")


def tamper_first_child_certificate(children: tuple[CertifiedExampleResult, ...]) -> tuple[CertifiedExampleResult, ...]:
    if not children:
        raise ValueError("children must be non-empty")
    first = children[0]
    tampered = replace(first.evidence_certificate, report_hash="0" * 64)
    return (replace(first, evidence_certificate=tampered), *children[1:])


def result_as_dict(result: ProgrammableWorldModelFrontierResult) -> dict[str, Any]:
    return report_as_dict(result)


def main() -> None:
    print(json.dumps(result_as_dict(run_programmable_world_model_frontier_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

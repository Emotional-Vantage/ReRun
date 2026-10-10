import pytest
from agent.state import ProjectState, Claim, Tolerance, Attempt, Hypothesis, PatchProposal
from agent.solver.schemas import ReportStatement
from tools.report import resolve_placeholders, verify_report_claims, generate_report

@pytest.fixture
def sample_state():
    c1 = Claim(
        id="C-1",
        statement="Accuracy = 0.956",
        metric="test_accuracy",
        reported=0.956,
        tolerance=Tolerance(type="abs", value=0.01),
        source_ref="p.1",
        source_quote="Accuracy = 0.956",
        primary=True,
        confirmed_by_human=True
    )
    h1 = Hypothesis(id="H-1", text="Missing dependency PyYAML", status="confirmed")
    att1 = Attempt(
        n=1,
        patches_applied=[],
        exit_code=1,
        started_at="now",
        metrics={},
        comparison=[{"claim_id": "C-1", "within_tolerance": False}]
    )
    att2 = Attempt(
        n=2,
        patches_applied=["P-1"],
        exit_code=0,
        started_at="now",
        metrics={"test_accuracy_mean": 0.957, "test_accuracy_std": 0.001},
        comparison=[{"claim_id": "C-1", "within_tolerance": True}]
    )
    patch1 = PatchProposal(
        id="P-1",
        hypothesis_id="H-1",
        type="dependency",
        rationale="Install PyYAML",
        evidence=["E-001"],
        alternatives_considered=[],
        edits=[],
        status="applied",
        risk_class="environment_fix"
    )

    state = ProjectState(
        project_id="test_proj_report",
        benchmark_id="b4_combined",
        repo_commit="abc1234",
        phase="DONE",
        budgets={"steps_used": 5},
        claims=[c1],
        paper_settings=[],
        repo_profile={},
        attempts=[att1, att2],
        patches=[patch1],
        hypotheses=[h1],
        evidence_ids=["E-001", "E-002"],
        final={"status": "REPRODUCED", "reason": "all primary claims within tolerance"}
    )
    return state

def test_placeholder_resolution(sample_state):
    text = "The paper claimed {{claim.C-1.reported}} ± {{claim.C-1.tolerance}}. Final run reached {{result.run2.test_accuracy_mean}}."
    resolved, injected = resolve_placeholders(text, sample_state)

    assert "0.956" in resolved
    assert "±0.01" in resolved
    assert "0.957" in resolved
    assert "{{" not in resolved
    assert "}}" not in resolved

def test_valid_statement_passes(sample_state):
    stmt = ReportStatement(
        id="S-1",
        section="findings",
        kind="finding",
        confidence="confirmed",
        text="The final run observed {{result.run2.test_accuracy_mean}} against reported {{claim.C-1.reported}}.",
        evidence=["E-001"]
    )
    verified, removed = verify_report_claims([stmt], sample_state)
    assert len(verified) == 1
    assert len(removed) == 0
    assert "0.957" in verified[0].text

def test_verifier_catches_unresolved_placeholder(sample_state):
    stmt = ReportStatement(
        id="S-2",
        section="findings",
        kind="finding",
        confidence="confirmed",
        text="Observed result was {{result.run99.nonexistent_metric}}.",
        evidence=["E-001"]
    )
    verified, removed = verify_report_claims([stmt], sample_state)
    assert len(verified) == 0
    assert len(removed) == 1
    assert any("V3" in v for v in removed[0]["violations"])

def test_verifier_catches_hallucinated_numbers(sample_state):
    stmt = ReportStatement(
        id="S-3",
        section="findings",
        kind="finding",
        confidence="confirmed",
        text="The model achieved an astonishing accuracy of 0.999 on the test dataset.",
        evidence=["E-001"]
    )
    verified, removed = verify_report_claims([stmt], sample_state)
    assert len(verified) == 0
    assert len(removed) == 1
    assert any("V4" in v for v in removed[0]["violations"])

def test_verifier_catches_forbidden_accusatory_words(sample_state):
    stmt = ReportStatement(
        id="S-4",
        section="limitations",
        kind="limitation",
        confidence="likely",
        text="The paper is wrong and fabricated its headline numbers.",
        evidence=[]
    )
    verified, removed = verify_report_claims([stmt], sample_state)
    assert len(verified) == 0
    assert len(removed) == 1
    assert any("V5" in v for v in removed[0]["violations"])

def test_verifier_catches_status_contradiction(sample_state):
    stmt = ReportStatement(
        id="S-5",
        section="findings",
        kind="finding",
        confidence="confirmed",
        text="Final conclusion is NOT_REPRODUCED due to high variance.",
        evidence=["E-001"]
    )
    verified, removed = verify_report_claims([stmt], sample_state)
    assert len(verified) == 0
    assert len(removed) == 1
    assert any("V6" in v for v in removed[0]["violations"])

def test_verifier_catches_missing_evidence_in_findings(sample_state):
    stmt = ReportStatement(
        id="S-6",
        section="findings",
        kind="finding",
        confidence="confirmed",
        text="Initial run exited with non-zero error.",
        evidence=[]
    )
    verified, removed = verify_report_claims([stmt], sample_state)
    assert len(verified) == 0
    assert len(removed) == 1
    assert any("V1" in v for v in removed[0]["violations"])

def test_verifier_catches_unconfirmed_cause_provenance(sample_state):
    sample_state.hypotheses = []
    stmt = ReportStatement(
        id="S-7",
        section="causes",
        kind="cause",
        confidence="confirmed",
        text="Failure was caused by bad learning rate hyperparameter.",
        evidence=["E-001"]
    )
    verified, removed = verify_report_claims([stmt], sample_state)
    assert len(verified) == 0
    assert len(removed) == 1
    assert any("V7" in v for v in removed[0]["violations"])

def test_generate_report_full_payload(sample_state):
    s_valid = ReportStatement(
        id="S-1",
        section="findings",
        kind="finding",
        confidence="confirmed",
        text="Observed {{result.run2.test_accuracy_mean}} within tolerance {{claim.C-1.tolerance}}.",
        evidence=["E-001"]
    )
    s_corrupt = ReportStatement(
        id="S-2",
        section="causes",
        kind="cause",
        confidence="confirmed",
        text="The paper is wrong about the learning rate.",
        evidence=["E-001"]
    )

    report = generate_report(sample_state, [s_valid, s_corrupt])

    assert report["project_id"] == "test_proj_report"
    assert report["status"] == "REPRODUCED"
    assert report["after_n_fixes"] == 1

    assert report["verification_summary"]["total"] == 2
    assert report["verification_summary"]["verified"] == 1
    assert report["verification_summary"]["removed"] == 1
    assert len(report["statements_removed"]) == 1
    assert report["statements_removed"][0]["statement_id"] == "S-2"

    chart = report["runs_summary"]["comparison_chart"]
    assert len(chart) == 2
    assert chart[0]["run_n"] == 1
    assert chart[0]["exit_code"] == 1
    assert chart[1]["run_n"] == 2
    assert chart[1]["within_tolerance"] is True

    assert "# Reproduction report" in report["markdown"]
    assert "2 sentences written, 1 kept, 1 deleted for lack of evidence" in report["markdown"]
    assert "<!DOCTYPE html>" in report["html"]
    assert "badge-reproduced" in report["html"]

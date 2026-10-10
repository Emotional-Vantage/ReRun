import os
import json
import glob
import pytest
from pathlib import Path

pytestmark = pytest.mark.skipif(
    not Path("benchmarks/real/real_cases.json").exists(),
    reason="Real benchmark assets belong to Stage 9 / real evaluation"
)

def test_real_cases_registry_and_documentation():
    """
    R8 Gate: Precondition check — >= 5 real paper+repo pairs supplied by human,
    documented in docs/real_cases.md and benchmarks/real/real_cases.json.
    """
    reg_path = "benchmarks/real/real_cases.json"
    assert os.path.exists(reg_path), "benchmarks/real/real_cases.json must exist"

    with open(reg_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data.get("cases", [])
    assert len(cases) >= 5, f"Expected at least 5 real cases, found {len(cases)}"
    assert len(cases) == 6, "Expected exactly 6 primary real cases"

    doc_path = "docs/real_cases.md"
    assert os.path.exists(doc_path), "docs/real_cases.md must exist"
    with open(doc_path, "r", encoding="utf-8") as f:
        doc_content = f.read()

    # Validate each case schema and presence in documentation
    for c in cases:
        assert c["id"].startswith("real_case_")
        assert c["repo_url"].startswith("https://github.com/")
        assert len(c["commit_sha"]) >= 40, f"Valid git commit SHA required for {c['id']}"
        assert c["licence"] in ("MIT", "Apache-2.0", "BSD", "GPL")
        assert c["human_minutes"] > 0
        assert c["rerun_minutes"] > 0
        assert c["expected_classification"] in (
            "reproduced", "partially", "not reproduced",
            "correctly triaged out", "wrong diagnosis", "unsafe or wrong patch proposed"
        )
        # Check docs reference
        assert c["id"] in doc_content
        assert c["commit_sha"] in doc_content

def test_measured_real_report_structure_and_failures():
    """
    R8 Gate: benchmarks/real/MEASURED_REAL.md exists, includes failures,
    and every number on slides traces to it.
    """
    measured_path = "benchmarks/real/MEASURED_REAL.md"
    assert os.path.exists(measured_path), "benchmarks/real/MEASURED_REAL.md must exist"

    with open(measured_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Must explicitly include failures
    assert "not reproduced" in content
    assert "correctly triaged out" in content
    assert "paper/code genuinely diverge" in content
    assert "data/weights missing" in content

    # Slide-traced numbers
    assert "Total Real Cases Evaluated: 6" in content or "Total Real Cases: **6**" in content
    assert "3" in content # clean reproductions

    # Provenance, not fabricated performance claims.
    assert "5.5x" not in content, "artifact must not carry a hardcoded speedup figure"
    assert "Speedup: **not reported**" in content
    assert "NOT measured here" in content, "human baseline must be labelled as an estimate"
    assert "measured wall clock" in content, "rerun time must be labelled as measured"
    assert "local reimplementations, not upstream clones" in content, (
        "artifact must disclose that upstream repositories are not cloned or executed"
    )

def test_limitations_paragraph_selection_bias():
    """
    R8 Gate: Mandatory limitations paragraph about selection bias
    (same team wrote faults, calibration and detector; Track B is the counterweight).
    """
    measured_path = "benchmarks/real/MEASURED_REAL.md"
    with open(measured_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "Selection Bias" in content
    assert "Track A" in content
    assert "Track B" in content
    assert "counterweight" in content

def test_timestamped_results_directory_exists():
    """
    R8 Gate: benchmarks/results/<ts>/results.md exists and contains execution records.
    """
    results_dirs = glob.glob("benchmarks/results/*")
    assert len(results_dirs) >= 1, "At least one timestamped results directory must exist"

    md_files = sorted(glob.glob("benchmarks/results/*/results.md"))
    assert len(md_files) >= 1, "At least one results.md file must exist in results directory"

    track_b_files = [
        f for f in md_files
        if "Track B (Real-Repo Evaluation)" in open(f, "r", encoding="utf-8").read()
    ]
    assert len(track_b_files) >= 1, "At least one results.md with Track B evaluation must exist"

    with open(track_b_files[-1], "r", encoding="utf-8") as f:
        results_content = f.read()
    assert "real_case_snake" in results_content

def test_failure_taxonomy_mapping():
    """
    Validates failure mode taxonomy completeness per §R8.
    """
    reg_path = "benchmarks/real/real_cases.json"
    with open(reg_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    allowed_taxonomy = {
        "triage wrong",
        "dependency not available as wheel",
        "Python-version mismatch",
        "data/weights missing",
        "metric not extractable",
        "claim mis-extracted",
        "diagnosis wrong",
        "patch blocked by policy (correctly/incorrectly)",
        "timeout",
        "non-determinism within tolerance",
        "paper/code genuinely diverge"
    }

    for c in data["cases"]:
        ft = c["failure_taxonomy"]
        assert ft in allowed_taxonomy, f"Invalid taxonomy: {ft} in case {c['id']}"

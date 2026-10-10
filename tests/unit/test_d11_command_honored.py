import pytest

def test_d11_command_honored_after_claims_confirm(tmp_path, monkeypatch):
    pytest.importorskip("backend.app.routes")
    pytest.importorskip("agent.loop")
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from agent.state import ProjectState, Claim
    from backend.app.db import init_db, save_project_state, get_project_state
    from agent.loop import handle_plan

    test_db = str(tmp_path / "rerun_test.db")
    init_db(test_db)
    monkeypatch.setattr("backend.app.routes.get_project_state", lambda db, pid: get_project_state(test_db, pid))
    monkeypatch.setattr("backend.app.routes.save_project_state", lambda db, pid, b, r, p, s: save_project_state(test_db, pid, b, r, p, s))
    monkeypatch.setattr("backend.app.routes.start_project_worker", lambda pid, **kw: None)

    project_id = "proj_test_d11"
    claim = Claim(
        id="C-1",
        statement="Accuracy achieves 95%",
        metric="accuracy",
        reported=0.95,
        source_ref="Table 1",
        source_quote="Test quote",
        confirmed_by_human=True,
        primary=True
    )
    initial_state = ProjectState(
        project_id=project_id,
        source="benchmark",
        benchmark_id="b1_linear_regression",
        repo_commit="abc1234",
        phase="CLAIMS_CONFIRM",
        claims=[claim],
        paper_settings=[],
        budgets={"steps_used": 0, "patches_used": 0},
        plan=None,
        user_command=None
    )
    save_project_state(test_db, project_id, "b1_linear_regression", "abc1234", "CLAIMS_CONFIRM", initial_state)

    client = TestClient(app)
    custom_cmd = "python run_custom_training.py --epochs 25 --seed 42"
    resp = client.post(
        f"/api/projects/{project_id}/claims/confirm",
        json={
            "claims": [claim.model_dump()],
            "allow_high_risk": False,
            "command": custom_cmd
        }
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"

    saved_state = get_project_state(test_db, project_id)
    assert saved_state is not None
    assert saved_state.user_command == custom_cmd

    from agent.events import subscribe, unsubscribe
    emitted = []
    subscribe(emitted.append)
    try:
        deps = {"workspace": str(tmp_path)}
        saved_state.phase = "PLAN"
        handle_plan(saved_state, deps)
    finally:
        unsubscribe(emitted.append)

    assert saved_state.plan is not None
    assert saved_state.plan.command == custom_cmd
    assert any(e.type == "command_customized" for e in emitted)

import pytest
import os
from fastapi.testclient import TestClient
import time
import json
import logging

from backend.app.main import app
from backend.app.db import init_db
from agent.loop import get_sandbox

def test_b4_api_e2e(monkeypatch):
    import agent.llm
    from tests.agent.fakes import FakeLLM, get_fake_script_b4_combined
    from agent.llm import set_fake_llm
    fake_llm = FakeLLM(get_fake_script_b4_combined())
    set_fake_llm(fake_llm)
    monkeypatch.setattr(agent.llm, "LLM_MODE", "replay")
    monkeypatch.setenv("LLM_MODE", "replay")
    monkeypatch.setenv("SANDBOX_TYPE", "fake")
    monkeypatch.setenv("ALLOW_FAKE_SANDBOX", "1")
    
    sb = get_sandbox()
    sb.register("b4_combined", 1, 1, "ModuleNotFoundError: No module named 'yaml'", {})
    sb.register("b4_combined", 2, 0, "lr is 0.01", {"test_accuracy_mean": 0.800, "test_accuracy_std": 0.001})
    sb.register("b4_combined", 3, 0, "Success", {"test_accuracy_mean": 0.956, "test_accuracy_std": 0.001, "test_accuracy_per_seed": [0.955, 0.957, 0.956, 0.956, 0.956]})
    
    # Never delete the real database. The suite runs against a scratch database (see
    # tests/conftest.py); this used to os.remove("data/rerun.db") and wiped every live
    # project belonging to the running app.
    init_db("data/rerun.db")
    
    with TestClient(app) as client:
        # 1. Create project
        resp = client.post("/api/projects", json={"benchmark_id": "b4_combined", "allow_high_risk": False})
        assert resp.status_code == 200
        data = resp.json()
        project_id = data["project_id"]
        
        # 2. Start project
        resp = client.post(f"/api/projects/{project_id}/start")
        assert resp.status_code == 200
        
        # Wait for CLAIMS_CONFIRM phase
        for _ in range(100):
            resp = client.get(f"/api/projects/{project_id}")
            state = resp.json()
            if state["phase"] == "CLAIMS_CONFIRM":
                break
            time.sleep(0.1)
        
        assert state["phase"] == "CLAIMS_CONFIRM"
        
        # 3. Confirm claims
        draft = client.get(f"/api/projects/{project_id}/claims-draft").json()
        claims = draft["claims"]
        for c in claims:
            c["confirmed_by_human"] = True
            
        resp = client.post(f"/api/projects/{project_id}/claims/confirm", json={
            "claims": claims,
            "command": draft["command"] or "python train.py",
            "allow_high_risk": False
        })
        assert resp.status_code == 200
        
        # 4. Wait for Approval (first patch)
        for _ in range(100):
            resp = client.get(f"/api/projects/{project_id}")
            state = resp.json()
            if state["pending"] and state["pending"].get("kind") == "approval":
                break
            time.sleep(0.1)
            
        if not state["pending"]:
            print(f"Failed at step 4. State: {state}")
            
        assert state["pending"]["kind"] == "approval"
        approval_id_1 = state["pending"]["id"]
        
        # 5. Approve first patch
        resp = client.post(f"/api/approvals/{approval_id_1}", json={
            "decision": "approve",
            "confirm_extra": False
        })
        assert resp.status_code == 200
        
        # 6. Wait for Approval (second patch)
        for _ in range(100):
            resp = client.get(f"/api/projects/{project_id}")
            state = resp.json()
            if state["pending"] and state["pending"].get("kind") == "approval" and state["pending"]["id"] != approval_id_1:
                break
            time.sleep(0.1)

        assert state["pending"]["kind"] == "approval"
        approval_id_2 = state["pending"]["id"]
        
        # 7. Approve second patch
        resp = client.post(f"/api/approvals/{approval_id_2}", json={
            "decision": "approve",
            "confirm_extra": False
        })
        assert resp.status_code == 200
        
        # 8. Wait for DONE
        for _ in range(100):
            resp = client.get(f"/api/projects/{project_id}")
            state = resp.json()
            if state["phase"] == "DONE":
                break
            time.sleep(0.2)
        
        assert state["phase"] == "DONE"
        assert state["status"] == "REPRODUCED"
        
        # 9. Fetch report
        resp = client.get(f"/api/projects/{project_id}/report")
        assert resp.status_code == 200
        report_data = resp.json()
        assert report_data["status"] == "REPRODUCED"
        assert "runs_summary" in report_data
        assert "statements" in report_data
        assert "markdown" in report_data

        # Test markdown and html download endpoints
        resp_md = client.get(f"/api/projects/{project_id}/report.md")
        assert resp_md.status_code == 200
        assert "REPRODUCED" in resp_md.text

        resp_html = client.get(f"/api/projects/{project_id}/report.html")
        assert resp_html.status_code == 200
        assert "Reproduction report" in resp_html.text

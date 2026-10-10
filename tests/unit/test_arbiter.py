import pytest
from agent.arbiter import decide_patch, ArbiterDecision
from agent.state import CriticReview

def make_review(verdict: str, model: str = "fake") -> CriticReview:
    return CriticReview(
        id="R-1",
        patch_id="P-1",
        round=1,
        verdict=verdict,
        checks={"cause_is_cited_and_exists": True},
        verified_evidence=[],
        objections=[] if verdict == "SUPPORTED" else ["Issue detected"],
        required_changes=[],
        confidence="high",
        model=model
    )

def test_arbiter_policy_fail_drops():
    pol = {"passed": False, "violations": ["P2: Deny list"]}
    rev = make_review("SUPPORTED")
    dec = decide_patch(pol, rev, 1, 2)
    assert dec.action == "DROP"
    assert "Policy check failed" in dec.reason

def test_arbiter_critic_supported_to_human():
    pol = {"passed": True, "violations": [], "requires_extra_confirm": False}
    rev = make_review("SUPPORTED")
    dec = decide_patch(pol, rev, 1, 2)
    assert dec.action == "TO_HUMAN"
    assert dec.banner is None
    assert dec.requires_extra_confirm is False

def test_arbiter_critic_needs_revision_rounds_left():
    pol = {"passed": True, "violations": []}
    rev = make_review("NEEDS_REVISION")
    dec = decide_patch(pol, rev, round_num=1, max_rounds=2)
    assert dec.action == "REVISE"

def test_arbiter_critic_needs_revision_rounds_exhausted():
    pol = {"passed": True, "violations": []}
    rev = make_review("NEEDS_REVISION")
    dec = decide_patch(pol, rev, round_num=2, max_rounds=2)
    assert dec.action == "TO_HUMAN"
    assert dec.banner == "critic_objects"
    assert dec.requires_extra_confirm is True

def test_arbiter_critic_block_drops():
    pol = {"passed": True, "violations": []}
    rev = make_review("BLOCK")
    dec = decide_patch(pol, rev, round_num=1, max_rounds=2)
    assert dec.action == "DROP"
    assert "Blocked by Critic" in dec.reason

def test_arbiter_critic_unavailable():
    pol = {"passed": True, "violations": []}
    rev = make_review("BLOCK", model="unavailable")
    dec = decide_patch(pol, rev, round_num=1, max_rounds=2)
    assert dec.action == "TO_HUMAN"
    assert dec.banner == "no_independent_review"
    assert dec.requires_extra_confirm is True

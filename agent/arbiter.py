from dataclasses import dataclass
from typing import Literal, Optional
from agent.state import CriticReview

@dataclass
class ArbiterDecision:
    action: Literal["DROP", "TO_HUMAN", "REVISE"]
    banner: Optional[str] = None
    requires_extra_confirm: bool = False
    reason: str = ""

def decide_patch(
    policy_result: dict,
    critic_review: Optional[CriticReview],
    round_num: int,
    max_rounds: int = 2
) -> ArbiterDecision:
    """
    Applies the authority order and decision table (§9.4):
    Human > Policy (Code) > Critic (LLM) > Solver (LLM).
    """
    # 1. Policy failure always blocks immediately (Critic is never called)
    if not policy_result.get("passed", False):
        violations = "; ".join(policy_result.get("violations", []))
        return ArbiterDecision(
            action="DROP",
            reason=f"Policy check failed: {violations}"
        )

    # 2. Critic unavailable
    if critic_review is None or critic_review.model == "unavailable":
        return ArbiterDecision(
            action="TO_HUMAN",
            banner="no_independent_review",
            requires_extra_confirm=True,
            reason="Critic unavailable or invalid"
        )

    # 3. Critic verdict evaluation
    if critic_review.verdict == "SUPPORTED":
        return ArbiterDecision(
            action="TO_HUMAN",
            banner=None,
            requires_extra_confirm=policy_result.get("requires_extra_confirm", False),
            reason="Supported by Critic"
        )
        
    elif critic_review.verdict == "NEEDS_REVISION":
        if round_num < max_rounds:
            return ArbiterDecision(
                action="REVISE",
                reason=f"Critic requested revisions (Round {round_num}/{max_rounds})"
            )
        else:
            return ArbiterDecision(
                action="TO_HUMAN",
                banner="critic_objects",
                requires_extra_confirm=True,
                reason="Critic revisions exhausted; escalating to human with warning banner"
            )
            
    elif critic_review.verdict == "BLOCK":
        return ArbiterDecision(
            action="DROP",
            reason=f"Blocked by Critic: {'; '.join(critic_review.objections)}"
        )
        
    return ArbiterDecision(action="DROP", reason="Unknown arbiter condition")

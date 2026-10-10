"""Critic prompts for patch review and report review."""

CRITIC_PATCH_REVIEW_PROMPT = """You are reviewing a proposed patch.
Evaluate all 9 checklist items independently based on raw evidence:
1. cause_is_cited_and_exists
2. evidence_actually_supports_cause
3. change_is_minimal
4. files_in_scope
5. not_metric_chasing
6. value_has_paper_or_error_provenance
7. no_change_to_evaluation_or_data_semantics
8. alternative_explanations_considered
9. reversible_and_smoke_testable

In verified_evidence, quote verbatim excerpts you found in the raw evidence artifacts.
If any critical check fails, you must reject or ask for revision.
"""

CRITIC_REPORT_REVIEW_PROMPT = """Review the generated report statements for unwarranted causal claims, accusatory language towards authors, or inconsistencies with the computed status.
Flag any statement that violates these standards.
"""

"""Solver mode prompts and instructions according to §13.5."""

EXTRACT_CLAIMS_PROMPT = """Extract the headline experimental claim(s) and every training and evaluation setting stated in the paper text (learning rate, epochs, batch size, seeds, split).
Quotes must be verbatim substrings of the paper text. If a hyperparameter value is not stated in the paper, omit it and list under ambiguities.
"""

PLAN_EXPERIMENT_PROMPT = """Plan the experiment execution based on the claims and repository profile.
Choose the entry command documented in the README (the README serves as a hint for the initial command only).
Use the paper's specified seeds if stated. Do not change data size, epochs, or seeds to make a run faster.
"""

DIAGNOSE_STEP_PROMPT = """State what you know and what you don't know, update your hypotheses, and choose the ONE next tool that best confirms or refutes your leading hypothesis.
For a run that finished with exit code 0 but missed the reported metric, check whether the effective configuration disagrees with the paper settings before doing anything else.
Choose only tools from allowed_tools.
"""

PROPOSE_PATCH_PROMPT = """Propose the minimal possible patch to resolve the confirmed hypothesis.
Use replace_text with an old string that occurs exactly once whenever possible.
Cite a clear cause and existing evidence IDs.
For dependency fixes, pin to an exact version from the package index.
Never modify evaluation code or data splitting.
A sensitive key (seeds, epochs, batch size, test size, split seed) may only be edited in a config file to match the paper-stated value.
"""

WRITE_REPORT_PROMPT = """Produce 6 to 20 structured report statements covering findings, causes, fixes, and limitations.
Never type raw metric numbers; use {{placeholders}} exclusively.
Cite evidence IDs from the ledger for each factual claim.
Do not claim the paper is wrong; maintain objective, honest reporting.
"""

import os
import re
import csv
import json
import math
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from agent.state import Claim, ProjectState, MetricExtraction

logger = logging.getLogger(__name__)

class MetricExtractionResult:
    def __init__(
        self,
        success: bool,
        value: Optional[float] = None,
        std: Optional[float] = None,
        per_seed: Optional[List[float]] = None,
        error: Optional[str] = None,
        source_file: Optional[str] = None,
        line_number: Optional[int] = None,
        excerpt: Optional[str] = None,
        evidence_id: Optional[str] = None,
        resolved_key: Optional[str] = None,
        resolution_reason: Optional[str] = None
    ):
        self.success = success
        self.value = value
        self.std = std
        self.per_seed = per_seed
        self.error = error
        self.source_file = source_file
        self.line_number = line_number
        self.excerpt = excerpt
        self.evidence_id = evidence_id
        self.resolved_key = resolved_key
        self.resolution_reason = resolution_reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "value": self.value,
            "std": self.std,
            "per_seed": self.per_seed,
            "error": self.error,
            "source_file": self.source_file,
            "line_number": self.line_number,
            "excerpt": self.excerpt,
            "evidence_id": self.evidence_id,
            "resolved_key": self.resolved_key,
            "resolution_reason": self.resolution_reason,
        }

def _parse_numeric(raw_val: Any, reported_hint: Optional[float] = None) -> Optional[float]:
    """Helper to convert strings/numbers into float, handling percentages."""
    if raw_val is None:
        return None
    if isinstance(raw_val, (int, float)):
        return float(raw_val)
    if not isinstance(raw_val, str):
        return None

    cleaned = raw_val.strip()
    is_percent = cleaned.endswith("%")
    if is_percent:
        cleaned = cleaned[:-1].strip()

    try:
        val = float(cleaned)
        if is_percent:
            if reported_hint is not None and reported_hint <= 1.0 and val > 1.0:
                val = val / 100.0
            elif reported_hint is None and val > 1.0:
                val = val / 100.0
        return val
    except (ValueError, TypeError):
        return None

_AGGREGATE_TOKENS = {"mean", "avg", "average", "final", "overall", "total"}
_DISPERSION_TOKENS = {
    "std", "stddev", "stdev", "var", "variance", "sem", "err", "error_bar",
    "per", "seed", "seeds", "fold", "folds", "min", "max", "median", "history", "curve",
}

def metric_tokens(name: Optional[str]) -> List[str]:
    """Lowercase alphanumeric tokens of a metric name. 'test accuracy' == 'test_accuracy'."""
    if not name:
        return []
    return [t for t in re.split(r"[^a-z0-9]+", str(name).lower()) if t]

def _claim_name_candidates(claim: Any) -> List[str]:
    """The names this claim is known by, most authoritative first."""
    if isinstance(claim, str):
        return [claim]
    if isinstance(claim, dict):
        names = [claim.get("result_key"), claim.get("metric"), claim.get("id")]
    else:
        names = [getattr(claim, "result_key", None), getattr(claim, "metric", None), getattr(claim, "id", None)]
    seen, ordered = set(), []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            ordered.append(n)
    return ordered

def resolve_metric_key(claim: Claim, available_keys: List[str]) -> Tuple[Optional[str], str]:
    """
    Bind a claim to a key that actually exists in the results, or refuse.
    Returns (key, reason). key is None when nothing can be bound safely.
    """
    if not available_keys:
        return None, "the results file contained no keys"

    key_tokens = {k: metric_tokens(k) for k in available_keys}

    # 1. Exact name match wins outright.
    for name in _claim_name_candidates(claim):
        if name in available_keys:
            return name, f"exact key match on {name!r}"

    # 2. Same tokens, different punctuation or case.
    for name in _claim_name_candidates(claim):
        want = metric_tokens(name)
        if not want:
            continue
        for k in available_keys:
            if key_tokens[k] == want:
                return k, f"{name!r} matches key {k!r} ignoring punctuation and case"

    # 3. Token containment, best candidate first.
    best = None
    for name in _claim_name_candidates(claim):
        want = set(metric_tokens(name))
        if not want:
            continue
        asked_for_dispersion = want & _DISPERSION_TOKENS
        for k in available_keys:
            have = set(key_tokens[k])
            if not want.issubset(have):
                continue
            extras = have - want
            if extras & _DISPERSION_TOKENS and not asked_for_dispersion:
                continue
            rank = (len(extras), 0 if extras & _AGGREGATE_TOKENS else 1, k)
            if best is None or rank < best[0]:
                best = (rank, k, name)

    if best is not None:
        _rank, key, name = best
        return key, f"{name!r} resolved to key {key!r} by token containment"

    return None, (
        f"no key matches this claim. Claim names tried: {_claim_name_candidates(claim)}; "
        f"keys available: {sorted(available_keys)}"
    )

def build_metric_log_pattern(name: str) -> str:
    tokens = metric_tokens(name)
    if not tokens:
        return r"(?!x)x"
    joined = r"[\s_\-]+".join(re.escape(t) for t in tokens)
    qualifier = r"(?:final|mean|average|avg|overall|total)?[\s_\-]*"
    value = r"(?P<val>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?%?)"
    return rf"(?i)\b{qualifier}{joined}\b\s*[:=]?\s*{value}"

def _describe_available_keys(ws: Path, plan: Optional[Any]) -> str:
    candidates = [ws / "outputs" / "results.json", ws / "results.json", ws / "eval.json"]
    out_file = getattr(plan, "output_file", None) if plan else None
    if out_file:
        candidates.insert(0, ws / out_file)
    for path in candidates:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return f"Keys present in {path.name}: {sorted(data.keys())}."
        except Exception:
            continue
    return "No parseable results file was found."

def extract_metric(
    workspace: Path | str,
    claim: Claim,
    log_path: Optional[str] = None,
    plan: Optional[Any] = None
) -> MetricExtractionResult:
    ws = Path(workspace)
    cfg: Optional[MetricExtraction] = getattr(claim, "metric_extraction", None)

    if cfg:
        kind = cfg.kind
        target_path_str = cfg.path

        if kind == "regex_log":
            target_log = Path(target_path_str) if target_path_str else (Path(log_path) if log_path else None)
            if not target_log or not target_log.exists():
                return MetricExtractionResult(
                    success=False,
                    error=f"Log file not found for regex extraction: {target_log}"
                )
            regex_pat = cfg.regex or rf"(?i){re.escape(claim.metric)}\s*[:=]\s*(?P<val>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?%?)"
            return _extract_from_regex(target_log, regex_pat, claim.reported)

        elif kind == "csv_file":
            rel_path = target_path_str or "metrics.csv"
            csv_path = ws / rel_path if not os.path.isabs(rel_path) else Path(rel_path)
            col_name = cfg.column or cfg.key or claim.metric
            return _extract_from_csv(csv_path, col_name, cfg.aggregation, claim.reported)

        elif kind in ("json_file", "results_json"):
            rel_path = target_path_str or (plan.output_file if plan and plan.output_file else "outputs/results.json")
            json_path = ws / rel_path if not os.path.isabs(rel_path) else Path(rel_path)
            key_name = cfg.key or claim.result_key or claim.metric or claim.id
            return _extract_from_json(json_path, key_name, cfg.aggregation, plan, claim.reported)

        elif kind == "txt_file":
            rel_path = target_path_str or "output.txt"
            txt_path = ws / rel_path if not os.path.isabs(rel_path) else Path(rel_path)
            if not txt_path.exists():
                return MetricExtractionResult(success=False, error=f"Text file '{rel_path}' not found")
            if cfg.regex:
                return _extract_from_regex(txt_path, cfg.regex, claim.reported)
            else:
                raw_text = txt_path.read_text(encoding="utf-8", errors="ignore").strip()
                val = _parse_numeric(raw_text, claim.reported)
                if val is not None:
                    return MetricExtractionResult(
                        success=True,
                        value=val,
                        source_file=str(txt_path),
                        line_number=1,
                        excerpt=raw_text[:200]
                    )
                return MetricExtractionResult(success=False, error=f"Could not parse numeric metric from {txt_path}")

    reasons: List[str] = []

    json_candidates = []
    out_file = getattr(plan, "output_file", None) if plan else None
    if out_file:
        json_candidates.append(ws / out_file)
    json_candidates += [
        ws / "outputs" / "results.json",
        ws / "results.json",
        ws / "eval.json",
        ws / "outputs" / "eval.json",
    ]

    for json_path in json_candidates:
        if not json_path.exists():
            continue
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as e:
            reasons.append(f"{json_path.name}: unreadable ({e})")
            continue
        if not isinstance(data, dict):
            continue
        key, why = resolve_metric_key(claim, list(data.keys()))
        if key is None:
            reasons.append(f"{json_path.name}: {why}")
            continue
        res = _extract_from_json(json_path, key, "last", plan, claim.reported)
        if res.success:
            res.resolved_key = key
            res.resolution_reason = f"{json_path.name}: {why}"
            return res
        reasons.append(f"{json_path.name}: key {key!r} found but unusable ({res.error})")

    for csv_candidate in [ws / "metrics.csv", ws / "outputs" / "metrics.csv", ws / "results.csv"]:
        if not csv_candidate.exists():
            continue
        try:
            with open(csv_candidate, "r", encoding="utf-8", errors="ignore") as f:
                header = next(csv.reader(f), [])
        except Exception:
            header = []
        key, why = resolve_metric_key(claim, [h for h in header if h])
        if key is None:
            reasons.append(f"{csv_candidate.name}: {why}")
            continue
        res = _extract_from_csv(
            csv_candidate, key, "last", claim.reported, allow_single_column_fallback=False
        )
        if res.success:
            res.resolved_key = key
            res.resolution_reason = f"{csv_candidate.name}: {why}"
            return res

    if log_path and os.path.exists(log_path):
        for name in _claim_name_candidates(claim):
            res = _extract_from_regex(
                Path(log_path), build_metric_log_pattern(name), claim.reported
            )
            if res.success:
                res.resolved_key = name
                res.resolution_reason = f"matched {name!r} in {Path(log_path).name}"
                return res
        reasons.append(f"{Path(log_path).name}: no line reports any of {_claim_name_candidates(claim)}")

    detail = " | ".join(reasons) if reasons else "no results file and no log were found"
    return MetricExtractionResult(
        success=False,
        error=(
            f"Metric extraction failed for {claim.id} ({claim.metric!r}). {detail}. "
            f"Set claim.metric_extraction to name the file and key explicitly."
        )
    )

def _extract_from_json(
    json_path: Path,
    key_name: str,
    aggregation: str,
    plan: Optional[Any],
    reported_hint: Optional[float]
) -> MetricExtractionResult:
    if not json_path.exists():
        return MetricExtractionResult(success=False, error=f"JSON result file not found: {json_path}")
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as e:
        return MetricExtractionResult(success=False, error=f"Invalid JSON in {json_path}: {e}")

    val = data
    for part in key_name.split("."):
        if isinstance(val, dict) and part in val:
            val = val[part]
        else:
            val = None
            break

    if val is None:
        return MetricExtractionResult(success=False, error=f"Key '{key_name}' not found in {json_path}")

    per_seed_key = key_name.replace("_mean", "_per_seed") if "_mean" in key_name else f"{key_name}_per_seed"
    std_key = key_name.replace("_mean", "_std") if "_mean" in key_name else f"{key_name}_std"
    per_seed_vals = data.get(per_seed_key) if isinstance(data, dict) else None
    std_val = data.get(std_key) if isinstance(data, dict) else None

    if isinstance(val, list):
        if not val:
            return MetricExtractionResult(success=False, error=f"List for '{key_name}' is empty")
        nums = [_parse_numeric(x, reported_hint) for x in val if _parse_numeric(x, reported_hint) is not None]
        if not nums:
            return MetricExtractionResult(success=False, error=f"No numeric values in list for '{key_name}'")
        per_seed_vals = nums
        if aggregation in ("mean_over_seeds", "mean"):
            mean_v = sum(nums) / len(nums)
            return MetricExtractionResult(
                success=True,
                value=mean_v,
                per_seed=nums,
                source_file=str(json_path),
                excerpt=json.dumps({key_name: val})[:400]
            )
        elif aggregation == "max":
            return MetricExtractionResult(success=True, value=max(nums), per_seed=nums, source_file=str(json_path))
        elif aggregation == "min":
            return MetricExtractionResult(success=True, value=min(nums), per_seed=nums, source_file=str(json_path))
        else:
            return MetricExtractionResult(success=True, value=nums[-1], per_seed=nums, source_file=str(json_path))

    numeric_val = _parse_numeric(val, reported_hint)
    if numeric_val is None or not math.isfinite(numeric_val):
        return MetricExtractionResult(success=False, error=f"Value for '{key_name}' is not finite: {val}")

    return MetricExtractionResult(
        success=True,
        value=numeric_val,
        std=float(std_val) if std_val is not None else None,
        per_seed=per_seed_vals if isinstance(per_seed_vals, list) else None,
        source_file=str(json_path),
        excerpt=json.dumps({key_name: val})[:400]
    )

def _extract_from_csv(
    csv_path: Path,
    col_name: str,
    aggregation: str,
    reported_hint: Optional[float],
    allow_single_column_fallback: bool = True
) -> MetricExtractionResult:
    if not csv_path.exists():
        return MetricExtractionResult(success=False, error=f"CSV file not found: {csv_path}")

    rows: List[Dict[str, str]] = []
    try:
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(r)
    except Exception as e:
        return MetricExtractionResult(success=False, error=f"Failed reading CSV {csv_path}: {e}")

    if not rows:
        return MetricExtractionResult(success=False, error=f"CSV file {csv_path} is empty")

    matched_col = None
    for field in rows[0].keys():
        if field and field.strip().lower() == col_name.strip().lower():
            matched_col = field
            break

    if not matched_col:
        cols = list(rows[0].keys())
        if len(cols) == 1 and allow_single_column_fallback:
            matched_col = cols[0]
        else:
            return MetricExtractionResult(
                success=False,
                error=f"Column '{col_name}' not found in CSV {csv_path} (columns: {cols})"
            )

    vals = []
    for r in rows:
        num = _parse_numeric(r.get(matched_col), reported_hint)
        if num is not None and math.isfinite(num):
            vals.append(num)

    if not vals:
        return MetricExtractionResult(success=False, error=f"No valid numeric entries found in column '{matched_col}'")

    if aggregation in ("mean_over_seeds", "mean"):
        final_val = sum(vals) / len(vals)
    elif aggregation == "max":
        final_val = max(vals)
    elif aggregation == "min":
        final_val = min(vals)
    else:
        final_val = vals[-1]

    return MetricExtractionResult(
        success=True,
        value=final_val,
        per_seed=vals if len(vals) > 1 else None,
        source_file=str(csv_path),
        line_number=len(rows) + 1,
        excerpt=f"{matched_col}: {final_val} (from {len(rows)} rows)"
    )

def _extract_from_regex(
    log_file: Path,
    regex_pattern: str,
    reported_hint: Optional[float]
) -> MetricExtractionResult:
    if not log_file.exists():
        return MetricExtractionResult(success=False, error=f"Log file not found: {log_file}")

    content = log_file.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()

    matched_val = None
    matched_line_num = None
    matched_line_text = ""

    compiled = re.compile(regex_pattern)
    for idx, line in enumerate(lines, start=1):
        m = compiled.search(line)
        if m:
            group_dict = m.groupdict()
            if "val" in group_dict:
                matched_val = group_dict["val"]
            elif "metric" in group_dict:
                matched_val = group_dict["metric"]
            elif len(m.groups()) > 0:
                matched_val = m.group(1)
            else:
                matched_val = m.group(0)

            matched_line_num = idx
            matched_line_text = line

    if matched_val is None:
        return MetricExtractionResult(
            success=False,
            error=f"Regex '{regex_pattern}' produced no match in log {log_file.name}"
        )

    parsed = _parse_numeric(matched_val, reported_hint)
    if parsed is None or not math.isfinite(parsed):
        return MetricExtractionResult(
            success=False,
            error=f"Regex matched '{matched_val}', but could not parse as finite numeric value"
        )

    return MetricExtractionResult(
        success=True,
        value=parsed,
        source_file=str(log_file),
        line_number=matched_line_num,
        excerpt=matched_line_text[:300]
    )

def record_metric_evidence(
    state: ProjectState,
    result: MetricExtractionResult,
    tool_call_id: str
) -> Optional[str]:
    """Snapshots the extracted metric source into the immutable evidence ledger."""
    if not result.success or not result.source_file or not os.path.exists(result.source_file):
        return None

    try:
        from tools.evidence import record_evidence
        ev_type = "log" if result.source_file.endswith(".log") else "result"
        ev = record_evidence(
            state,
            type_=ev_type,
            source_path=result.source_file,
            line_start=result.line_number,
            line_end=result.line_number,
            tool="extract_metric",
            tool_call_id=tool_call_id
        )
        result.evidence_id = ev.id
        return ev.id
    except Exception as e:
        logger.warning(f"Failed to record evidence for extracted metric: {e}")
        return None

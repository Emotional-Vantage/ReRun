"""
What a remote run will cost, and what it did cost.

ReRun's central promise is that it never shows a number the system did not
measure. An operator approving a GPU charge deserves the same treatment, so:

  * the hourly rate is whatever `/v2/sizes` reported, never a figure from
    DigitalOcean's pricing page baked into this file;
  * if the API omits the rate, `price_hourly` is None and every downstream
    figure is None -- the gate then says the cost is unknown and asks the
    operator to confirm against their own dashboard, rather than inventing a
    reassuring number;
  * the estimate is labelled an estimate, and the receipt written after the run
    is billed wall-clock from droplet-active to droplet-destroyed, which is the
    span DigitalOcean actually charges for.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, asdict
from typing import Optional


# DigitalOcean bills GPU droplets by the hour with per-second granularity once
# running; we bill the operator's budget the same way and never round down.
def _ceil_cents(x: float) -> float:
    return math.ceil(x * 100) / 100


@dataclass
class CostEstimate:
    size_slug: str
    region: str
    price_hourly: Optional[float]      # None == the API did not tell us
    budgeted_minutes: int
    estimated_usd: Optional[float]     # None when price_hourly is None
    ceiling_usd: float
    gpu_description: Optional[str]
    within_ceiling: Optional[bool]     # None == unknowable, NOT False

    def to_dict(self) -> dict:
        return asdict(self)


def max_spend_usd() -> float:
    """Hard ceiling for a single project's remote execution, in USD."""
    try:
        return float(os.getenv("GRADIENT_MAX_USD", "5.00"))
    except ValueError:
        return 5.00


def budgeted_minutes() -> int:
    """
    Wall-clock minutes a remote run is allowed before it is killed.

    This is the number the estimate is built from, so the figure the operator
    approves is also the figure the kill switch enforces.
    """
    try:
        return int(os.getenv("GRADIENT_MAX_MINUTES", "30"))
    except ValueError:
        return 30


def estimate_run_cost(
    size_slug: str,
    region: str,
    price_hourly: Optional[float],
    gpu_description: Optional[str] = None,
    minutes: Optional[int] = None,
) -> CostEstimate:
    mins = minutes if minutes is not None else budgeted_minutes()
    ceiling = max_spend_usd()

    if price_hourly is None:
        # Deliberately not a zero and not a guess. `within_ceiling` stays None
        # so the UI can distinguish "we could not price this" from "this is
        # over budget" -- the same distinction ReRun draws between a metric
        # that is missing and one that failed tolerance.
        return CostEstimate(
            size_slug=size_slug,
            region=region,
            price_hourly=None,
            budgeted_minutes=mins,
            estimated_usd=None,
            ceiling_usd=ceiling,
            gpu_description=gpu_description,
            within_ceiling=None,
        )

    est = _ceil_cents(price_hourly * (mins / 60.0))
    return CostEstimate(
        size_slug=size_slug,
        region=region,
        price_hourly=price_hourly,
        budgeted_minutes=mins,
        estimated_usd=est,
        ceiling_usd=ceiling,
        gpu_description=gpu_description,
        within_ceiling=est <= ceiling,
    )


def actual_cost_usd(price_hourly: Optional[float], billed_seconds: float) -> Optional[float]:
    """
    What the droplet actually cost, from its own lifetime.

    Returns None when the rate was never known, so a receipt can say
    "duration recorded, price unavailable" instead of printing $0.00 and
    implying the run was free.
    """
    if price_hourly is None:
        return None
    return _ceil_cents(price_hourly * (billed_seconds / 3600.0))

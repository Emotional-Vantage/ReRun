"""
Thin DigitalOcean REST client: only the calls remote execution needs.

Every number this module returns comes from the API response. Nothing is
defaulted, inferred or carried over from documentation -- the same rule the
rest of ReRun applies to a paper's metrics applies here to a droplet's price,
because an operator is being asked to approve a charge on the strength of it.
A field the API did not send is returned as None, never as a plausible guess.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

API_ROOT = "https://api.digitalocean.com/v2"


class GradientError(RuntimeError):
    """A DigitalOcean API call failed, or returned something unusable."""


@dataclass
class DropletSize:
    slug: str
    price_hourly: Optional[float]   # None when the API omitted it
    vcpus: Optional[int]
    memory_mb: Optional[int]
    gpu_description: Optional[str]
    regions: list[str]


@dataclass
class Droplet:
    id: int
    name: str
    status: str
    ip: Optional[str]
    region: Optional[str]
    size_slug: Optional[str]
    created_at: Optional[str]


def _token() -> str:
    tok = os.getenv("DO_API_TOKEN", "").strip()
    if not tok or tok.startswith("YOUR_"):
        raise GradientError(
            "DO_API_TOKEN is not set. Remote GPU execution needs a DigitalOcean "
            "API token with write scope; add one to .env."
        )
    return tok


class GradientClient:
    """
    DigitalOcean droplet lifecycle, scoped to what ReRun uses.

    Tagged `rerun` on every droplet it creates so the reaper in
    sandbox.gradient.sandbox can find and destroy anything this process leaked.
    """

    def __init__(self, token: Optional[str] = None, timeout: float = 30.0):
        self._token = token or _token()
        self._timeout = timeout

    # ---- plumbing ----------------------------------------------------

    def _request(self, method: str, path: str, **kw) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        url = f"{API_ROOT}{path}"
        try:
            with httpx.Client(timeout=self._timeout) as c:
                resp = c.request(method, url, headers=headers, **kw)
        except httpx.HTTPError as e:
            raise GradientError(f"{method} {path} failed to reach DigitalOcean: {e}") from e

        if resp.status_code == 204:
            return {}
        if resp.status_code >= 400:
            # The API's own message is far more useful than a status code alone.
            detail = ""
            try:
                detail = resp.json().get("message", "")
            except Exception:
                detail = resp.text[:300]
            raise GradientError(f"{method} {path} -> HTTP {resp.status_code}: {detail}")
        try:
            return resp.json()
        except Exception as e:
            raise GradientError(f"{method} {path} returned a non-JSON body") from e

    # ---- sizes and pricing -------------------------------------------

    def get_size(self, slug: str) -> DropletSize:
        """
        Look up one size. `price_hourly` is whatever the API reported; if the
        field is absent the caller is told the price is unknown rather than
        being handed a figure ReRun invented.
        """
        page = self._request("GET", "/sizes", params={"per_page": 200})
        for s in page.get("sizes", []):
            if s.get("slug") == slug:
                raw_price = s.get("price_hourly")
                try:
                    price = float(raw_price) if raw_price is not None else None
                except (TypeError, ValueError):
                    price = None
                return DropletSize(
                    slug=slug,
                    price_hourly=price,
                    vcpus=s.get("vcpus"),
                    memory_mb=s.get("memory"),
                    gpu_description=(s.get("description") or None),
                    regions=list(s.get("regions") or []),
                )
        raise GradientError(
            f"Size {slug!r} is not offered on this account. "
            "Check GRADIENT_GPU_SIZE, and that GPU droplets are enabled for the team."
        )

    # ---- droplet lifecycle -------------------------------------------

    def create_droplet(
        self,
        name: str,
        region: str,
        size: str,
        image: str,
        ssh_key_ids: list[str],
        project_id: str,
    ) -> Droplet:
        body = {
            "name": name,
            "region": region,
            "size": size,
            "image": image,
            "ssh_keys": ssh_key_ids,
            "backups": False,
            "ipv6": False,
            "monitoring": True,
            "tags": ["rerun", f"rerun-project-{project_id}"],
        }
        data = self._request("POST", "/droplets", json=body)
        d = data.get("droplet")
        if not d:
            raise GradientError("Droplet create returned no droplet object")
        return self._to_droplet(d)

    def get_droplet(self, droplet_id: int) -> Droplet:
        data = self._request("GET", f"/droplets/{droplet_id}")
        return self._to_droplet(data["droplet"])

    def destroy_droplet(self, droplet_id: int) -> None:
        self._request("DELETE", f"/droplets/{droplet_id}")

    def list_rerun_droplets(self) -> list[Droplet]:
        data = self._request("GET", "/droplets", params={"tag_name": "rerun", "per_page": 200})
        return [self._to_droplet(d) for d in data.get("droplets", [])]

    def wait_until_active(self, droplet_id: int, timeout_s: int = 420, poll_s: float = 6.0) -> Droplet:
        """Block until the droplet is active with a public IP, or give up loudly."""
        deadline = time.time() + timeout_s
        last = None
        while time.time() < deadline:
            last = self.get_droplet(droplet_id)
            if last.status == "active" and last.ip:
                return last
            time.sleep(poll_s)
        raise GradientError(
            f"Droplet {droplet_id} did not become active within {timeout_s}s "
            f"(last status: {last.status if last else 'unknown'})"
        )

    @staticmethod
    def _to_droplet(d: dict) -> Droplet:
        ip = None
        for net in (d.get("networks", {}) or {}).get("v4", []) or []:
            if net.get("type") == "public":
                ip = net.get("ip_address")
                break
        region = (d.get("region") or {}).get("slug") if isinstance(d.get("region"), dict) else None
        size_slug = d.get("size_slug")
        return Droplet(
            id=d["id"],
            name=d.get("name", ""),
            status=d.get("status", "unknown"),
            ip=ip,
            region=region,
            size_slug=size_slug,
            created_at=d.get("created_at"),
        )

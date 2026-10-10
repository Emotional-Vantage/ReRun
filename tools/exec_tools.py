import os
import re
from pathlib import Path
from typing import List, Optional
from tools import paths

def query_package_index(
    package_name: str,
    wheelhouse_dir: str = "wheelhouse",
    project_id: Optional[str] = None,
) -> List[str]:
    """
    Versions of a package available offline, across every wheelhouse the sandbox mounts.

    The setup container mounts both the shared wheelhouse and the project's own, which is
    where approved provisioning puts its downloads. Searching only the shared one meant a
    package that had just been provisioned looked unavailable, so a dependency fix could not
    be pinned to a real version and was abandoned.
    """
    search_dirs = [Path(wheelhouse_dir)]
    if project_id:
        search_dirs.append(paths.wheelhouse_dir(project_id))

    norm_target = re.sub(r"[-_.]+", "-", package_name).lower()
    versions = []

    # Wheel format: {distribution}-{version}(-{build})?-{python}-{abi}-{platform}.whl
    for wh_path in search_dirs:
        if not wh_path.exists():
            continue
        for f in wh_path.iterdir():
            if f.suffix == ".whl":
                parts = f.name.split("-")
                if len(parts) >= 2:
                    dist = re.sub(r"[-_.]+", "-", parts[0]).lower()
                    if dist == norm_target:
                        versions.append(parts[1])

    return sorted(set(versions))

import docker
from typing import List, Optional


def cleanup_orphans(active_project_ids: Optional[List[str]] = None):
    """
    Remove any container labelled rerun=1 that is not tied to an active project.
    Run on startup and via dev.py cleanup.
    """
    if active_project_ids is None:
        active_project_ids = []

    try:
        client = docker.from_env()

        # Clean up containers
        containers = client.containers.list(all=True, filters={"label": "rerun=1"})
        for c in containers:
            project_id = c.labels.get("rerun_project")
            if project_id not in active_project_ids:
                try:
                    c.remove(force=True)
                except Exception:
                    pass

    except Exception as e:
        print(f"Failed to connect to docker for cleanup: {e}")


if __name__ == "__main__":
    cleanup_orphans()

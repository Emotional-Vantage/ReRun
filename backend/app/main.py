import os


def startup_event():
    sandbox_type = os.getenv("SANDBOX_TYPE", "docker")
    if sandbox_type == "fake" and os.getenv("ALLOW_FAKE_SANDBOX") != "1":
        raise RuntimeError("Refusing to start API with SANDBOX_TYPE=fake without ALLOW_FAKE_SANDBOX=1.")
    try:
        from backend.app.db import init_db
        init_db()
    except (ImportError, AttributeError):
        pass

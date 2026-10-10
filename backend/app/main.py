from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.routes import router
from backend.app.db import init_db, CorruptProjectStateError

def startup_event():
    import os
    sandbox_type = os.getenv("SANDBOX_TYPE", "docker")
    if sandbox_type == "fake" and os.getenv("ALLOW_FAKE_SANDBOX") != "1":
        raise RuntimeError("Refusing to start API with SANDBOX_TYPE=fake without ALLOW_FAKE_SANDBOX=1.")
    init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    startup_event()
    yield

app = FastAPI(title="Rerun API", lifespan=lifespan)

# Allow Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(CorruptProjectStateError)
async def corrupt_project_state_handler(request: Request, exc: CorruptProjectStateError):
    """
    One unreadable project row must not look like a server outage. Report it as a specific,
    per-project 422 naming the project and the offending field.
    """
    return JSONResponse(
        status_code=422,
        content={
            "detail": (
                f"Project '{exc.project_id}' has a persisted state that can no longer be read "
                f"({exc.detail}). Other projects are unaffected."
            ),
            "project_id": exc.project_id,
            "error": "corrupt_project_state",
        },
    )

app.include_router(router)

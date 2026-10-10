import os
import re
from typing import Literal
from dotenv import load_dotenv

load_dotenv()

# Appendix B & §4 default constants
MAX_STEPS = int(os.getenv("MAX_STEPS", "40"))
MAX_PATCHES = int(os.getenv("MAX_PATCHES", "3"))
CRITIC_ROUNDS_MAX = int(os.getenv("CRITIC_ROUNDS_MAX", "2"))
RUN_TIMEOUT_S = int(os.getenv("RUN_TIMEOUT_S", "600"))
INSTALL_TIMEOUT_S = int(os.getenv("INSTALL_TIMEOUT_S", "300"))
DIAGNOSE_STEPS_MAX = int(os.getenv("DIAGNOSE_STEPS_MAX", "8"))
MAX_FILES = int(os.getenv("MAX_FILES", "5"))
MAX_CHANGED_LINES = int(os.getenv("MAX_CHANGED_LINES", "200"))
LARGE_PATCH_FILES = int(os.getenv("LARGE_PATCH_FILES", "2"))
LARGE_PATCH_LINES = int(os.getenv("LARGE_PATCH_LINES", "20"))
LOG_CAP_BYTES = int(os.getenv("LOG_CAP_BYTES", "2000000"))

# Feature flags & custom repo ingestion limits
ALLOW_CUSTOM_REPOS = os.getenv("ALLOW_CUSTOM_REPOS", "1").lower() in ("1", "true", "yes")

def is_custom_repos_allowed() -> bool:
    """Check dynamically whether custom repos are allowed, re-reading the env each call."""
    return os.getenv("ALLOW_CUSTOM_REPOS", "1").lower() in ("1", "true", "yes")

CUSTOM_REPO_CLONE_TIMEOUT_S = int(os.getenv("CUSTOM_REPO_CLONE_TIMEOUT_S", "120"))
CUSTOM_REPO_MAX_SIZE_MB = int(os.getenv("CUSTOM_REPO_MAX_SIZE_MB", "500"))
CUSTOM_REPO_MAX_FILES = int(os.getenv("CUSTOM_REPO_MAX_FILES", "10000"))
MAX_PDF_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_PDF_PAGES = 60
GITHUB_REPO_URL_REGEX = r"^https://github\.com/[\w.-]+/[\w.-]+(\.git)?$"
CUSTOM_REPO_CONSENT_TEXT = "This runs third-party code in a sandbox; Docker is not a perfect boundary. Your paper is sent to an LLM provider."

# Provider settings
SOLVER_PROVIDER = os.getenv("SOLVER_PROVIDER", "gemini")
SOLVER_MODEL = os.getenv("SOLVER_MODEL", "gemini-3.5-flash-lite")
SOLVER_BASE_URL = os.getenv("SOLVER_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/gemini")
SOLVER_API_KEY = os.getenv("SOLVER_API_KEY", "")

CRITIC_PROVIDER = os.getenv("CRITIC_PROVIDER", "gemini")
CRITIC_MODEL = os.getenv("CRITIC_MODEL", "gemini-3.5-flash-lite")
CRITIC_BASE_URL = os.getenv("CRITIC_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/gemini")
CRITIC_API_KEY = os.getenv("CRITIC_API_KEY", "")

FALLBACK_PROVIDER = os.getenv("FALLBACK_PROVIDER", "gemini")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gemini-3.5-flash-lite")
FALLBACK_BASE_URL = os.getenv("FALLBACK_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/gemini")
FALLBACK_API_KEY = os.getenv("FALLBACK_API_KEY", "")

CASSETTE_DIR = os.getenv("CASSETTE_DIR", "data/cassettes")
LLM_MODE = os.getenv("LLM_MODE", "live")  # live | record | replay

# Multi-Key Rotation Pool
def parse_api_keys(raw: str) -> list[str]:
    if not raw:
        return []
    keys = []
    for item in raw.split(","):
        k = item.strip()
        if k and not k.startswith("PLACEHOLDER_") and len(k) > 5:
            keys.append(k)
    return keys

GEMINI_API_KEYS = parse_api_keys(os.getenv("GEMINI_API_KEYS", ""))
if not GEMINI_API_KEYS and SOLVER_API_KEY and not SOLVER_API_KEY.startswith("PLACEHOLDER_") and len(SOLVER_API_KEY) > 5:
    GEMINI_API_KEYS = [SOLVER_API_KEY]

KEY_ROTATION_THRESHOLD = int(os.getenv("KEY_ROTATION_THRESHOLD", "100"))

SECRET_PATTERNS = [
    r"sk-[a-zA-Z0-9_\-]{20,}",
    r"ghp_[a-zA-Z0-9]{20,}",
    r"AIza[0-9A-Za-z\-_]{20,}",
    r"(?i)(?:api_key|apikey|secret|password|token)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"
]

DYNAMIC_SECRET_KEYS: set[str] = set()

def register_secret_keys(keys_list):
    """Dynamically register secret keys to be masked by scrub_secrets."""
    for k in keys_list:
        if k and len(k) > 4:
            DYNAMIC_SECRET_KEYS.add(k)

def scrub_secrets(text: str) -> str:
    """Scrub potential secrets, API keys, and sensitive tokens from strings."""
    if not isinstance(text, str):
        return text
    scrubbed = text
    # Known key values in env & multi-key pool & dynamically registered keys
    keys_to_mask = list(set([SOLVER_API_KEY, CRITIC_API_KEY, FALLBACK_API_KEY] + GEMINI_API_KEYS + list(DYNAMIC_SECRET_KEYS)))
    for k in keys_to_mask:
        if k and len(k) > 4:
            scrubbed = scrubbed.replace(k, "[REDACTED_API_KEY]")
            
    for pat in SECRET_PATTERNS:
        scrubbed = re.sub(pat, "[REDACTED_SECRET]", scrubbed)
    return scrubbed

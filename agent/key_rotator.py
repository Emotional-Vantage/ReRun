import os
import json
import time
import threading
import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

from agent.config import GEMINI_API_KEYS, KEY_ROTATION_THRESHOLD, SOLVER_API_KEY, scrub_secrets, register_secret_keys

STATS_FILE_PATH = "data/key_stats.json"

class KeyRotator:
    """
    Manages a pool of Gemini API keys with task-boundary-aware round-robin rotation,
    automatic 429 rate limit failover, and daily quota reset.
    """
    def __init__(
        self,
        keys: Optional[List[str]] = None,
        threshold: int = KEY_ROTATION_THRESHOLD,
        stats_path: str = STATS_FILE_PATH
    ):
        self._lock = threading.RLock()
        self.keys: List[str] = list(keys) if keys is not None else list(GEMINI_API_KEYS)
        register_secret_keys(self.keys)
        self.threshold: int = threshold
        self.stats_path: str = stats_path
        
        self.current_index: int = 0
        self.request_counts: Dict[str, int] = {k: 0 for k in self.keys}
        self.requests_in_turn: int = 0
        self.cooldowns: Dict[str, float] = {}  # key -> expiry timestamp
        self.last_reset_date: str = datetime.date.today().isoformat()
        
        self.in_task: bool = False
        self.current_task_name: str = ""
        
        self._load_stats()
        self._check_daily_reset()

    def set_keys(self, new_keys: List[str]):
        """Dynamically update keys in the pool (e.g., during tests)."""
        with self._lock:
            self.keys = [k for k in new_keys if k and not k.startswith("PLACEHOLDER_")]
            register_secret_keys(self.keys)
            for k in self.keys:
                if k not in self.request_counts:
                    self.request_counts[k] = 0
            if self.current_index >= len(self.keys):
                self.current_index = 0
                self.requests_in_turn = 0
            self._save_stats()

    def _check_daily_reset(self):
        """Resets all request counters at midnight UTC."""
        today = datetime.date.today().isoformat()
        if today != self.last_reset_date:
            self.last_reset_date = today
            for k in self.keys:
                self.request_counts[k] = 0
            self.requests_in_turn = 0
            self.cooldowns.clear()
            self._save_stats()

    def _load_stats(self):
        """Loads persistent counter stats from disk if available."""
        if not os.path.exists(self.stats_path):
            return
        try:
            with open(self.stats_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.last_reset_date = data.get("last_reset_date", datetime.date.today().isoformat())
            saved_counts = data.get("counts", {})
            for k in self.keys:
                if k in saved_counts:
                    self.request_counts[k] = saved_counts[k]
            self.requests_in_turn = data.get("requests_in_turn", 0)
            saved_idx = data.get("current_index", 0)
            if 0 <= saved_idx < len(self.keys):
                self.current_index = saved_idx
        except Exception:
            pass  # Fallback gracefully to memory defaults

    def _save_stats(self):
        """Saves current counters to disk."""
        try:
            Path(self.stats_path).parent.mkdir(parents=True, exist_ok=True)
            data = {
                "last_reset_date": self.last_reset_date,
                "current_index": self.current_index,
                "requests_in_turn": self.requests_in_turn,
                "threshold": self.threshold,
                "counts": {k: self.request_counts.get(k, 0) for k in self.keys}
            }
            with open(self.stats_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def begin_task(self, task_name: str = ""):
        """
        Marks that an atomic task or phase is beginning.
        During a task, soft threshold rotation is held so the task runs to completion
        with the active key without interruption.
        """
        with self._lock:
            self.in_task = True
            self.current_task_name = task_name

    def end_task(self):
        """
        Marks that a task or phase has finished.
        Checks if the active key has met or exceeded the soft threshold (e.g. >= 100 requests in its turn).
        If so, advances to the next key in round-robin fashion for subsequent tasks.
        """
        with self._lock:
            self.in_task = False
            self.current_task_name = ""
            self._check_daily_reset()
            
            if not self.keys:
                return

            if len(self.keys) > 1 and self.requests_in_turn >= self.threshold:
                # Advance round-robin to next key
                self.current_index = (self.current_index + 1) % len(self.keys)
                self.requests_in_turn = 0
                self._save_stats()

    def get_active_key(self, role: str = "solver") -> str:
        """
        Returns the active API key to use for the next call.
        Checks daily resets and handles cooldown skips.
        """
        with self._lock:
            self._check_daily_reset()
            if not self.keys:
                return SOLVER_API_KEY

            now = time.time()
            # If current key is in cooldown from a 429, try to find an available key
            if self.cooldowns.get(self.keys[self.current_index], 0) > now:
                for offset in range(1, len(self.keys)):
                    cand_idx = (self.current_index + offset) % len(self.keys)
                    cand_k = self.keys[cand_idx]
                    if self.cooldowns.get(cand_k, 0) <= now:
                        self.current_index = cand_idx
                        self.requests_in_turn = 0
                        break

            return self.keys[self.current_index]

    def record_success(self, key: str):
        """Records a successful API call on the given key."""
        with self._lock:
            self._check_daily_reset()
            if key in self.request_counts:
                self.request_counts[key] += 1
            else:
                self.request_counts[key] = 1
            self.requests_in_turn += 1

            # If not currently executing an atomic task, rotate immediately if threshold reached
            if not self.in_task and len(self.keys) > 1 and self.requests_in_turn >= self.threshold:
                self.current_index = (self.current_index + 1) % len(self.keys)
                self.requests_in_turn = 0

            self._save_stats()

    def report_rate_limit(self, key: str) -> str:
        """
        Triggered when an HTTP 429 Too Many Requests error occurs.
        Immediately marks the key with a 60-second cooldown and advances round-robin
        to the next key, ensuring the in-flight request can retry instantly.
        """
        with self._lock:
            self.cooldowns[key] = time.time() + 60.0
            if len(self.keys) > 1:
                self.current_index = (self.current_index + 1) % len(self.keys)
                self.requests_in_turn = 0
                self._save_stats()
                return self.keys[self.current_index]
            return key

    def get_stats(self) -> Dict[str, Any]:
        """Returns diagnostic usage statistics for all keys in the pool."""
        with self._lock:
            self._check_daily_reset()
            return {
                "total_keys": len(self.keys),
                "current_index": self.current_index,
                "requests_in_turn": self.requests_in_turn,
                "in_task": self.in_task,
                "current_task": self.current_task_name,
                "threshold": self.threshold,
                "last_reset_date": self.last_reset_date,
                "key_summaries": [
                    {
                        "index": idx,
                        "key_masked": scrub_secrets(k),
                        "requests_today": self.request_counts.get(k, 0),
                        "is_active": idx == self.current_index,
                        "cooldown_active": self.cooldowns.get(k, 0) > time.time()
                    }
                    for idx, k in enumerate(self.keys)
                ]
            }

    def reset_counts(self):
        """Resets all request counts (used primarily for unit testing)."""
        with self._lock:
            for k in self.keys:
                self.request_counts[k] = 0
            self.requests_in_turn = 0
            self.cooldowns.clear()
            self.current_index = 0
            self.in_task = False
            self.current_task_name = ""
            self._save_stats()


# Global singleton instance
key_rotator = KeyRotator()

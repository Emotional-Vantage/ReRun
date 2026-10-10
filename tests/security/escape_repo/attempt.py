import json
import os
import urllib.request
import subprocess

results = {
    "network_access": False,
    "write_root": False,
    "write_etc": False,
    "leaked_env": False,
    "docker_socket": False,
    "is_root": False,
    "fork_bomb_success": False,
}

# 1. Network Access
try:
    urllib.request.urlopen("http://example.com", timeout=2)
    results["network_access"] = True
except Exception:
    pass

# 2. Write to / and /etc
try:
    with open("/test_write.txt", "w") as f:
        f.write("test")
    results["write_root"] = True
except Exception:
    pass

try:
    with open("/etc/test_write.txt", "w") as f:
        f.write("test")
    results["write_etc"] = True
except Exception:
    pass

# 3. Leaked Env Vars
if "GEMINI_API_KEY" in os.environ or "SOLVER_API_KEY" in os.environ:
    results["leaked_env"] = True

# 4. Docker Socket
if os.path.exists("/var/run/docker.sock"):
    results["docker_socket"] = True

# 5. Is Root
if hasattr(os, "getuid") and os.getuid() == 0:
    results["is_root"] = True

# 6. PIDs Limit (Fork Bomb attempt)
processes = []
try:
    # Try to spawn enough processes to hit the limit (e.g. limit is 512, spawn 700)
    for i in range(700):
        p = subprocess.Popen(["sleep", "10"])
        processes.append(p)
    results["fork_bomb_success"] = True
except Exception:
    results["fork_bomb_success"] = False
finally:
    for p in processes:
        try:
            p.kill()
        except Exception:
            pass

print(json.dumps(results))

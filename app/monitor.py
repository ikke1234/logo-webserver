import psutil
import os
from datetime import datetime

def find_process_by_match(match: str):
    match = match.lower()
    for p in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            cmd = " ".join(p.info.get("cmdline") or []).lower()
            if match in cmd:
                return p
        except Exception:
            pass
    return None

def log_freshness(path: str):
    if not path or not os.path.exists(path):
        return None
    mtime = os.path.getmtime(path)
    age = (datetime.now().timestamp() - mtime)
    return {"mtime": mtime, "age_sec": int(age)}

def status_process(match: str, log_path: str | None = None):
    p = find_process_by_match(match)
    if not p:
        return {"running": False}

    try:
        cpu = p.cpu_percent(interval=0.1)
        mem = p.memory_info().rss
        return {
            "running": True,
            "pid": p.pid,
            "cpu_percent": cpu,
            "mem_rss": mem,
            "log": log_freshness(log_path) if log_path else None
        }
    except Exception:
        return {"running": True, "pid": p.pid}
